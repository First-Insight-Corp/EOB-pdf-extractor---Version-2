import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TokenLogger:
    """Utility to log token usage per PDF, per page, and per step."""
    
    @staticmethod
    def log_usage(pdf_filename: str, pages: str, step: str, input_tokens: int, output_tokens: int, model_name: str = "Unknown", processed_file_id: int = None, request_id: str = None):
        if not pdf_filename and not processed_file_id:
            return

        # DB Logging
        if processed_file_id:
            try:
                from db import db, ExtractionTokenLog
                if db:
                    session = db.get_session()
                    token_entry = ExtractionTokenLog(
                        processed_file_id=processed_file_id,
                        request_id=request_id,
                        file_name=pdf_filename,
                        step=step,
                        model_name=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        pages=pages
                    )
                    session.add(token_entry)
                    session.commit()
                    session.close()
            except Exception as e:
                logger.error(f"Failed to log tokens to DB: {e}")

    @staticmethod
    def log_total(pdf_filename: str, total_input: int, total_output: int, total_pages: int = 0, llm_usage_breakdown: dict = None):
        # Token summary metrics now stored in processed_files.request_logs via DB; filesystem logging deprecated
        pass
