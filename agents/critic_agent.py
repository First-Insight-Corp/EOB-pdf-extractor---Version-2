"""
Critic Agent: turns Auditor issues into concrete improvement instructions for the Extraction Agent.
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import config
from logs_config import get_extraction_logger

logger = get_extraction_logger()


class CriticAgent:
    """
    Converts a list of issues (from Auditor) into clear, actionable instructions
    for the Extraction Agent to fix in a re-extraction pass.
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
                pass

    def get_improvement_instructions(
        self,
        issues: List[str],
        schema_description: str = "",
        pdf_filename: str = "",
        processed_file_id: Optional[int] = None,
        loop_number: int = 0,
        request_id: Optional[str] = None
    ) -> tuple[str, dict[str, Any]]:
        """
        Returns (improvement_instructions, usage_metadata).
        """
        if not issues:
            return "", {}
        prompt = f"""You are a Critic. The Extraction Agent produced JSON that the Auditor flagged with these issues:

{chr(10).join("- " + str(i) for i in issues)}

### SCHEMA CONTEXT
{schema_description}

Your task: Write clear, numbered instructions for the Extraction Agent so it can fix ALL issues in one re-extraction pass. Be specific (which field, which table, where to look). Do not output JSON—output only the instruction text that will be pasted into the next extraction prompt.
"""
        try:
            usage_metadata = {}
            if self._gemini_model:
                response = self._gemini_model.generate_content(prompt)
                instruction_text = (response.text or "").strip()
                try:
                    usage = response.usage_metadata
                    usage_metadata = {
                        "model_name": response.model_version or "gemini-unknown",
                        "input_tokens": usage.prompt_token_count,
                        "output_tokens": usage.candidates_token_count,
                        "total_tokens": usage.total_token_count
                    }
                except AttributeError:
                    logger.warning("Critic (Gemini) missing usage_metadata")
            elif self._claude_client:
                model_to_use = getattr(self, "_claude_model", "claude-sonnet-4-20250514")
                response = self._claude_client.messages.create(
                    model=model_to_use,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                instruction_text = (response.content[0].text if response.content else "").strip()
                try:
                    usage = response.usage
                    usage_metadata = {
                        "model_name": model_to_use,
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens
                    }
                except AttributeError:
                    logger.warning("Critic (Claude) missing usage metadata")
            else:
                instruction_text = "Address these issues:\n" + "\n".join(f"- {i}" for i in issues)

            # DB Logging
            if processed_file_id:
                try:
                    from db import db, AuditorCriticLog
                    from sqlalchemy import desc
                    if db:
                        session = db.get_session()
                        # Find the log entry created by Auditor for this loop
                        log_entry = session.query(AuditorCriticLog).filter_by(
                            processed_file_id=processed_file_id,
                            loop_number=loop_number
                        ).order_by(desc(AuditorCriticLog.timestamp)).first()
                        
                        if log_entry:
                            log_entry.critic_instructions = instruction_text
                            session.commit()
                        else:
                            # Fallback if auditor didn't create a record (shouldn't happen)
                            log_entry = AuditorCriticLog(
                                processed_file_id=processed_file_id,
                                request_id=request_id,
                                file_name=pdf_filename,
                                loop_number=loop_number,
                                critic_instructions=instruction_text
                            )
                            session.add(log_entry)
                            session.commit()
                        session.close()
                except Exception as db_log_e:
                    logger.error(f"Failed to log critic results to DB: {db_log_e}")

            return instruction_text, usage_metadata
        except Exception as e:
            logger.error(f"Critic failed: {e}")
        # Fallback: return issues as bullet list
        return "Address these issues:\n" + "\n".join(f"- {i}" for i in issues), {}
