"""
Auditor Agent: compares extracted JSON against the PDF (source text/images) and lists issues.
Used in the feedback loop: Extraction -> Auditor -> Critic -> Extraction (with instructions).
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import config

logger = logging.getLogger(__name__)


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


class AuditorAgent:
    """
    Compares extracted JSON to source document content and returns a list of issues
    (missing data, wrong values, structural problems).
    """

    def __init__(self, use_model: str = "gemini", api_key: str = "", model_name: str = ""):
        self.use_model = use_model
        self._gemini_model = None
        self._claude_client = None
        if use_model == "gemini" and api_key:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel(model_name or "gemini-2.0-flash")
        elif use_model == "claude" and api_key:
            try:
                from anthropic import Anthropic
                self._claude_client = Anthropic(api_key=api_key)
                self._claude_model = model_name or "claude-sonnet-4-20250514"
            except ImportError:
                logger.warning("anthropic not installed; Auditor will use Gemini if available")

    def audit(
        self,
        extracted_json: Dict[str, Any],
        source_text: str,
        schema_description: str,
        document_type: str = "VSP",
        is_last_batch: bool = False,
        image_b64_list: Optional[List[str]] = None,
        pdf_filename: str = "",
        processed_file_id: Optional[int] = None,
        loop_number: int = 0,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns {"issues": List[str], "lessons": List[str]}.
        issues: concrete problems (missing/wrong data) with evidence.
        lessons: optional adaptive lessons for future batches.
        """
        prompt = self._build_audit_prompt(
            extracted_json=extracted_json,
            source_text=source_text,
            schema_description=schema_description,
            document_type=document_type,
            is_last_batch=is_last_batch,
        )
        try:
            usage_metadata = {}
            if self._gemini_model:
                parts = [prompt]
                if image_b64_list:
                    for img_b64 in image_b64_list:
                        parts.append({
                            "mime_type": "image/png",
                            "data": base64.b64decode(img_b64),
                        })
                response = self._gemini_model.generate_content(parts)
                response_text = (response.text or "").strip()
                try:
                    usage = response.usage_metadata
                    usage_metadata = {
                        "model_name": response.model_version or "gemini-unknown",
                        "input_tokens": usage.prompt_token_count,
                        "output_tokens": usage.candidates_token_count,
                        "total_tokens": usage.total_token_count
                    }
                except AttributeError:
                    logger.warning("Auditor (Gemini) missing usage_metadata")
            elif self._claude_client:
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
                model_to_use = getattr(self, "_claude_model", "claude-sonnet-4-20250514")
                response = self._claude_client.messages.create(
                    model=model_to_use,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": content}],
                )
                response_text = (response.content[0].text if response.content else "").strip()
                try:
                    usage = response.usage
                    usage_metadata = {
                        "model_name": model_to_use,
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens
                    }
                except AttributeError:
                    logger.warning("Auditor (Claude) missing usage metadata")
            else:
                return {"issues": [], "lessons": [], "usage_metadata": {}}

            if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[-1].split("```")[0].strip()
            audit_result = json.loads(response_text)
            if isinstance(audit_result, list):
                audit_result = {"issues": audit_result, "lessons": []}
            
            def clean_list(items):
                cleaned = []
                for item in items:
                    if isinstance(item, dict):
                        # Use a reasonable description field or fallback to stringified dict
                        cleaned.append(item.get("issue", item.get("lesson", item.get("description", str(item)))))
                    else:
                        cleaned.append(str(item))
                return cleaned

            final_issues = clean_list(audit_result.get("issues", []))
            final_lessons = clean_list(audit_result.get("lessons", []))

            if pdf_filename and config.LOG_AUDITOR:
                try:
                    log_dir = os.path.join(os.getcwd(), "logs", "auditor")
                    os.makedirs(log_dir, exist_ok=True)
                    log_path = os.path.join(log_dir, f"{pdf_filename}.log")
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"\n--- Audit Timestamp: {datetime.now().isoformat()} ---\n")
                        f.write(f"Issues Found:\n")
                        for i, issue in enumerate(final_issues, 1):
                            f.write(f"{i}. {issue}\n")
                        f.write(f"\nLessons Learned:\n")
                        for i, lesson in enumerate(final_lessons, 1):
                            f.write(f"{i}. {lesson}\n")
                        f.write("\n")
                except Exception as eval_log_e:
                    logger.warning(f"Failed to write auditor log: {eval_log_e}")

            # DB Logging
            if processed_file_id:
                try:
                    from db import db, AuditorCriticLog
                    if db:
                        session = db.get_session()
                        log_entry = AuditorCriticLog(
                            processed_file_id=processed_file_id,
                            request_id=request_id,
                            file_name=pdf_filename,
                            loop_number=loop_number,
                            auditor_issues=final_issues,
                            auditor_lessons=final_lessons,
                            auditor_raw_response=response_text
                        )
                        session.add(log_entry)
                        session.commit()
                        session.close()
                except Exception as db_log_e:
                    logger.error(f"Failed to log auditor results to DB: {db_log_e}")

            return {
                "issues": final_issues,
                "lessons": final_lessons,
                "usage_metadata": usage_metadata,
            }
        except Exception as e:
            logger.error(f"Auditor failed: {e}")
            return {"issues": [], "lessons": []}

    def _build_audit_prompt(
        self,
        extracted_json: Dict[str, Any],
        source_text: str,
        schema_description: str,
        document_type: str,
        is_last_batch: bool,
    ) -> str:
        return f"""You are a Quality Auditor. Compare the EXTRACTED JSON below to the SOURCE DOCUMENT TEXT and list every discrepancy.

### SCHEMA RULES
{schema_description}

### SOURCE DOCUMENT TEXT (and [TABLE] blocks)
{source_text[:120000]}

### EXTRACTED JSON TO AUDIT
{json.dumps(extracted_json, indent=2, cls=SetEncoder)}

### INSTRUCTIONS
1. Find MISSING data: any claim, service line, or field visible in the source but null/missing in JSON.
2. Find WRONG data: values that do not match the source (e.g. wrong amount, wrong date).
3. Find STRUCTURAL errors: e.g. totals row in services list, wrong nesting.
4. Check data continuity: if any field continues to sub-fields, check if the sub-fields are correctly extracted.
5. Check that every field is correctly extracted and associated to right key(eg. field swaps, wrong field extractions)
4. If this is the last batch: check for document-level totals and special tables (e.g. In-Office Finishing, Total VSP Check).
5. Each issue MUST include brief evidence (eg. "Source shows $64.50 but extracted as $6.45" or "Patient SMITH, JOHN has no service_date").

Return ONLY valid JSON:
{{
  "issues": ["issue 1 with evidence", "issue 2 with evidence", ...],
  "lessons": ["optional lesson for future batches", ...]
}}
If 100% accurate, return {{"issues": [], "lessons": []}}.
No preamble. JSON only."""
