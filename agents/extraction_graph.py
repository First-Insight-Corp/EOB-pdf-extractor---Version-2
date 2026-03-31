"""
LangGraph-based multi-agent workflow for PDF extraction.

Orchestrates: Extraction Agent → Auditor → (conditional) Critic → re-Extraction
until no issues or max loops. Uses LangGraph for explicit state, nodes, and
conditional edges (framework for best accuracy and debuggability).
"""

import logging
from typing import TypedDict, Any, List, Optional, Tuple

from langgraph.graph import START, END, StateGraph
from agents.token_logger import TokenLogger
from logs_config import get_extraction_logger

logger = get_extraction_logger()


class ExtractionGraphState(TypedDict, total=False):
    """State passed through the Extraction → Auditor → Critic graph."""
    # Inputs (set once per batch)
    batch_text: str
    schema_description: str
    batch_json_schema: str
    response_json_schema: str
    document_type: str
    pdf_filename: str
    pages_str: str
    is_last_batch: bool
    image_b64_list: Optional[List[str]]
    is_continuation: bool
    previous_context: str
    # Memory / consistency: previous batch text and extracted JSON for data consistency
    previous_batch_text: Optional[str]
    previous_batch_json: Optional[dict]
    # Outputs / intermediate
    extracted_json: Optional[dict]
    issues: List[str]
    lessons: List[str]
    improvement_instructions: Optional[str]
    loop_count: int
    max_loops: int
    # Token Tracking
    total_input_tokens: int
    total_output_tokens: int
    llm_usage: dict  # { "model_name": {"input": X, "output": Y} }
    # Detailed Token Tracking per role
    extractor_tokens: dict # { "model_name": {"input": X, "output": Y} }
    auditor_tokens: dict   # { "model_name": {"input": X, "output": Y} }
    critic_tokens: dict    # { "model_name": {"input": X, "output": Y} }
    # DB Link
    processed_file_id: Optional[int]
    request_id: Optional[str]


def build_extraction_graph(extraction_agent, auditor_agent, critic_agent):
    """
    Build and compile the LangGraph workflow.
    Nodes use the provided agents (no framework replacement of LLM logic).
    """
    def _update_llm_usage(current_usage: dict, model_name: str, input_t: int, output_t: int) -> dict:
        new_usage = dict(current_usage or {})
        if model_name not in new_usage:
            new_usage[model_name] = {"input": 0, "output": 0}
        new_usage[model_name]["input"] += input_t
        new_usage[model_name]["output"] += output_t
        return new_usage

    def extraction_node(state: ExtractionGraphState) -> dict:
        loop = state.get("loop_count", 0)
        result = extraction_agent.extract_batch(
            document_type=state["document_type"],
            batch_text=state["batch_text"],
            schema_description=state["schema_description"],
            batch_json_schema=state.get("batch_json_schema", ""),
            response_json_schema=state.get("response_json_schema", ""),
            image_b64_list=state.get("image_b64_list"),
            is_continuation=state.get("is_continuation", False),
            previous_context=state.get("previous_context", ""),
            improvement_instructions=state.get("improvement_instructions"),
            previous_batch_text=state.get("previous_batch_text"),
            previous_batch_json=state.get("previous_batch_json"),
        )
        if "entities" in result and "claims" not in result:
            result["claims"] = result["entities"]
        
        usage = result.get("usage_metadata", {})
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        model_name = usage.get("model_name", "Unknown-Extraction")
        
        # Log usage
        TokenLogger.log_usage(
            pdf_filename=state.get("pdf_filename", ""),
            pages=state.get("pages_str", "Unknown"),
            step=f"Extract_{loop+1}",
            input_tokens=input_t,
            output_tokens=output_t,
            model_name=model_name,
            processed_file_id=state.get("processed_file_id"),
            request_id=state.get("request_id")
        )

        return {
            "extracted_json": result,
            "loop_count": loop + 1,
            "total_input_tokens": state.get("total_input_tokens", 0) + input_t,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_t,
            "llm_usage": _update_llm_usage(state.get("llm_usage", {}), model_name, input_t, output_t),
            "extractor_tokens": _update_llm_usage(state.get("extractor_tokens", {}), model_name, input_t, output_t),
        }

    def auditor_node(state: ExtractionGraphState) -> dict:
        audit_result = auditor_agent.audit(
            extracted_json=state["extracted_json"],
            source_text=state["batch_text"],
            schema_description=state["schema_description"],
            document_type=state["document_type"],
            is_last_batch=state.get("is_last_batch", False),
            image_b64_list=state.get("image_b64_list"),
            pdf_filename=state.get("pdf_filename", ""),
            processed_file_id=state.get("processed_file_id"),
            loop_number=state.get("loop_count", 0),
            request_id=state.get("request_id")
        )
        issues = audit_result.get("issues", [])
        lessons = audit_result.get("lessons", [])
        
        usage = audit_result.get("usage_metadata", {})
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        model_name = usage.get("model_name", "Unknown-Auditor")
        
        TokenLogger.log_usage(
            pdf_filename=state.get("pdf_filename", ""),
            pages=state.get("pages_str", "Unknown"),
            step=f"Audit_{state.get('loop_count', 0)}",
            input_tokens=input_t,
            output_tokens=output_t,
            model_name=model_name,
            processed_file_id=state.get("processed_file_id"),
            request_id=state.get("request_id")
        )

        if hasattr(extraction_agent, "learning_memory"):
            for lesson in lessons:
                extraction_agent.learning_memory.add_lesson(lesson)
        return {
            "issues": issues, 
            "lessons": lessons,
            "total_input_tokens": state.get("total_input_tokens", 0) + input_t,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_t,
            "llm_usage": _update_llm_usage(state.get("llm_usage", {}), model_name, input_t, output_t),
            "auditor_tokens": _update_llm_usage(state.get("auditor_tokens", {}), model_name, input_t, output_t),
        }

    def critic_node(state: ExtractionGraphState) -> dict:
        issues = state.get("issues", [])
        instructions, usage = critic_agent.get_improvement_instructions(
            issues, 
            state.get("schema_description", ""), 
            state.get("pdf_filename", ""),
            processed_file_id=state.get("processed_file_id"),
            loop_number=state.get("loop_count", 0),
            request_id=state.get("request_id")
        )
        
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        model_name = usage.get("model_name", "Unknown-Critic")
        
        TokenLogger.log_usage(
            pdf_filename=state.get("pdf_filename", ""),
            pages=state.get("pages_str", "Unknown"),
            step=f"Critic_{state.get('loop_count', 0)}",
            input_tokens=input_t,
            output_tokens=output_t,
            model_name=model_name,
            processed_file_id=state.get("processed_file_id"),
            request_id=state.get("request_id")
        )

        return {
            "improvement_instructions": instructions,
            "total_input_tokens": state.get("total_input_tokens", 0) + input_t,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_t,
            "llm_usage": _update_llm_usage(state.get("llm_usage", {}), model_name, input_t, output_t),
            "critic_tokens": _update_llm_usage(state.get("critic_tokens", {}), model_name, input_t, output_t),
        }

    def should_continue(state: ExtractionGraphState) -> str:
        issues = state.get("issues", [])
        loop_count = state.get("loop_count", 0)
        max_loops = state.get("max_loops", 4)
        if not issues:
            return "end"
        if loop_count >= max_loops:
            logger.warning("Max Auditor-Critic loops reached; returning current extraction.")
            return "end"
        return "continue"

    graph = StateGraph(ExtractionGraphState)
    graph.add_node("extraction", extraction_node)
    graph.add_node("auditor", auditor_node)
    graph.add_node("critic", critic_node)

    graph.add_edge(START, "extraction")
    graph.add_edge("extraction", "auditor")
    graph.add_conditional_edges(
        "auditor",
        should_continue,
        {"continue": "critic", "end": END},
    )
    graph.add_edge("critic", "extraction")

    return graph.compile()


def run_extraction_workflow(
    compiled_graph,
    batch_text: str,
    schema_description: str,
    batch_json_schema: str,
    response_json_schema: str,
    document_type: str,
    is_last_batch: bool,
    image_b64_list: Optional[List[str]],
    is_continuation: bool,
    previous_context: str,
    pdf_filename: str = "",
    pages_str: str = "",
    max_loops: int = 4,
    previous_batch_text: Optional[str] = None,
    previous_batch_json: Optional[dict] = None,
    processed_file_id: Optional[int] = None,
    request_id: Optional[str] = None,
) -> Tuple[dict, int, int, dict, int, dict]:
    """
    Invoke the LangGraph workflow for one batch.
    previous_batch_text / previous_batch_json: from the immediately prior batch for consistency.
    Returns (extracted_json, input_tokens, output_tokens, llm_usage, loop_count, role_usage).
    """
    initial_state: ExtractionGraphState = {
        "batch_text": batch_text,
        "schema_description": schema_description,
        "batch_json_schema": batch_json_schema,
        "response_json_schema": response_json_schema,
        "document_type": document_type,
        "pdf_filename": pdf_filename,
        "is_last_batch": is_last_batch,
        "image_b64_list": image_b64_list,
        "is_continuation": is_continuation,
        "previous_context": previous_context,
        "pages_str": pages_str,
        "max_loops": max_loops,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "llm_usage": {},
        "extractor_tokens": {},
        "auditor_tokens": {},
        "critic_tokens": {},
        "processed_file_id": processed_file_id,
        "request_id": request_id,
    }
    if previous_batch_text is not None:
        initial_state["previous_batch_text"] = previous_batch_text
    if previous_batch_json is not None:
        initial_state["previous_batch_json"] = previous_batch_json
    
    final_state = compiled_graph.invoke(initial_state)
    return (
        final_state.get("extracted_json") or {}, 
        final_state.get("total_input_tokens", 0), 
        final_state.get("total_output_tokens", 0),
        final_state.get("llm_usage") or {},
        final_state.get("loop_count", 0),
        {
            "extractor": final_state.get("extractor_tokens", {}),
            "auditor": final_state.get("auditor_tokens", {}),
            "critic": final_state.get("critic_tokens", {}),
        }
    )
