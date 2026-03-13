"""
Claude (Anthropic) extraction agent for PDF-to-JSON.
Uses Claude Sonnet 4 / Opus 4 for high-accuracy extraction.
"""

import base64
import json
import logging
import time
from typing import List, Dict, Any, Optional

from agents.base_extraction_agent import BaseExtractionAgent

from agents.memory import GlobalLearningMemory

logger = logging.getLogger(__name__)


class ClaudeExtractionAgent(BaseExtractionAgent):
    """Extraction agent using Anthropic Claude (Opus 4 / Sonnet 4)."""

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-20250514"):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")
        self.client = Anthropic(api_key=api_key)
        self.model_name = model_name
        self._conversation_context: List[Dict[str, str]] = []
        self.learning_memory = GlobalLearningMemory()
        logger.info(f"Initialized Claude Extraction Agent with model {model_name}")

    def reset_memory(self, keep_learning: bool = True) -> None:
        self._conversation_context = []
        if not keep_learning:
            self.learning_memory = GlobalLearningMemory()
        logger.info(f"Claude agent memory reset for new task (keep_learning={keep_learning})")

    def load_memory(self, format_name: str) -> None:
        """Load persistent memory for a specific format."""
        self.learning_memory.load(format_name)

    def save_memory(self, format_name: str) -> None:
        """Save current memory to persistent storage for a specific format."""
        self.learning_memory.save(format_name)

    def get_learning_context(self) -> str:
        return self.learning_memory.get_context_injection()

    def extract_batch(
        self,
        document_type: str,
        batch_text: str,
        schema_description: str,
        batch_json_schema: str = "",
        response_json_schema: str = "",
        image_b64_list: Optional[List[str]] = None,
        is_continuation: bool = False,
        previous_context: str = "",
        improvement_instructions: Optional[str] = None,
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(
            document_type=document_type,
            batch_text=batch_text,
            schema_description=schema_description,
            batch_json_schema=batch_json_schema,
            response_json_schema=response_json_schema,
            is_continuation=is_continuation,
            previous_context=previous_context,
            improvement_instructions=improvement_instructions,
            previous_batch_text=previous_batch_text,
            previous_batch_json=previous_batch_json,
        )

        content: List[Any] = [{"type": "text", "text": prompt}]
        if image_b64_list:
            for img_b64 in image_b64_list:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_b64,
                    },
                })

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            text = ""
            try:
                with self.client.messages.stream(
                    model=self.model_name,
                    max_tokens=128000,
                    messages=[{"role": "user", "content": content}],
                ) as stream:
                    response = stream.get_final_message()
                
                text = response.content[0].text if response.content else ""
                text = text.strip()
                
                # Capture token usage
                usage_metadata = {
                    "model_name": self.model_name
                }
                try:
                    usage = response.usage
                    usage_metadata.update({
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens
                    })
                except AttributeError:
                    logger.warning("Claude response missing usage metadata")

                # Robust JSON extraction
                json_text = text
                if "```json" in json_text:
                    json_text = json_text.split("```json")[-1]
                    if "```" in json_text:
                        json_text = json_text.split("```")[0]
                elif "```" in json_text:
                    json_text = json_text.split("```")[-1]
                    if "```" in json_text:
                        json_text = json_text.split("```")[0]
                
                json_text = json_text.strip()
                
                # If JSON is truncated (missing closing brace/bracket), try to append them
                # This is a basic attempt to fix common truncation issues
                if json_text.startswith("{") and not json_text.endswith("}"):
                    json_text += "}"
                elif json_text.startswith("[") and not json_text.endswith("]"):
                    json_text += "]"

                result = json.loads(json_text)
                # Include usage metadata
                result["usage_metadata"] = usage_metadata
                
                # Normalize: support both "entities" and "claims" for format compatibility
                if "entities" in result and "claims" not in result:
                    result["claims"] = result["entities"]
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Claude batch extraction attempt {attempt + 1} failed: {e}")
                
                # Debug logging: dump failing response
                try:
                    import os
                    debug_dir = "debug_logs"
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    debug_file = os.path.join(debug_dir, f"claude_fail_{timestamp}_attempt_{attempt+1}.txt")
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(f"ERROR: {str(e)}\n")
                        f.write(f"MODEL: {self.model_name}\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"RESPONSE_TEXT:\n{text}\n")
                    logger.error(f"Saved failing response to {debug_file}")
                except Exception as log_err:
                    logger.error(f"Failed to save debug log: {log_err}")

                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise last_error

    def _build_prompt(
        self,
        document_type: str,
        batch_text: str,
        schema_description: str,
        batch_json_schema: str,
        response_json_schema: str,
        is_continuation: bool,
        previous_context: str,
        improvement_instructions: Optional[str],
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        continuation_block = ""
        if is_continuation and previous_context:
            continuation_block = f"""
### CONTINUATION CONTEXT
This is a CONTINUATION of previous pages. PENDING CONTEXT FROM PREVIOUS BATCH:
{previous_context}
CRITICAL: The first entity on this page may be the continuation of the last entity from previous pages. Use PENDING CONTEXT to complete it. If continued, MERGE into existing entity; do not create a duplicate.
"""

        previous_batch_block = ""
        if previous_batch_text or previous_batch_json:
            _text = (previous_batch_text[-4000:] if previous_batch_text and len(previous_batch_text) > 4000 else (previous_batch_text or ""))
            _json = json.dumps(previous_batch_json, indent=2) if previous_batch_json else "{}"
            previous_batch_block = f"""
### PREVIOUS BATCH CONTEXT (for data consistency)
Keep field names, structure, and formatting consistent with the **immediately previous batch**. Match the same keys, number formats, and nesting. Do not contradict or duplicate data already extracted in the previous batch.

**Previous batch text (end of previous pages):**
{_text}

**Previous batch extracted JSON (structure and style to match):**
{_json}
"""

        improvement_block = ""
        if improvement_instructions:
            improvement_block = f"""
### CRITICAL: IMPROVEMENT INSTRUCTIONS (from Auditor/Critic)
You must address these issues in this re-extraction. Strictly ix every listed problem.
{improvement_instructions}
"""

        learning_context = self.get_learning_context()

        return f"""You are an expert at 100% accurate data extraction from complex medical remittance PDFs. Extract structured JSON with ZERO data loss.

### RULES
- ZERO DATA LOSS: Do not skip any line, field, or table.
- Tables are marked with [TABLE]...[/TABLE]. Preserve column alignment when mapping to schema.
- Return numeric 0.0 for zero values; do not use null for "0.00" in the document.
- Block-level fields (e.g. patient name, doctor) apply to all items in that block until a new value appears.

### TARGET SCHEMAS
1. ENTITY/CLAIM schema (for items in "claims" array):
{batch_json_schema}

2. METADATA schema (for "metadata" object):
{response_json_schema}

### DOCUMENT-SPECIFIC RULES
{schema_description}
{continuation_block}
{previous_batch_block}
{improvement_block}
{learning_context}

### SOURCE TEXT (with tables preserved)
{batch_text}

Return ONLY valid JSON in this exact shape (use "claims" for the main list):
{{
  "claims": [ ... ],
  "metadata": {{ ... }},
  "has_incomplete_entity": true/false,
  "incomplete_entity_context": {{ "entity_identifier": "...", "name": "...", "partial_data": {{ }} }},
  "processing_notes": "..."
}}
No preamble. JSON only."""
