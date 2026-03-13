import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TokenLogger:
    """Utility to log token usage per PDF, per page, and per step."""
    
    @staticmethod
    def _get_log_path(pdf_filename: str) -> str:
        log_dir = os.path.join(os.getcwd(), "logs", "tokens")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, f"{pdf_filename}_tokens.log")

    @staticmethod
    def log_usage(pdf_filename: str, pages: str, step: str, input_tokens: int, output_tokens: int, model_name: str = "Unknown", processed_file_id: int = None, request_id: str = None):
        if not pdf_filename and not processed_file_id:
            return
            
        log_path = TokenLogger._get_log_path(pdf_filename)
        total = input_tokens + output_tokens
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = (
            f"[{timestamp}] Req: {request_id or 'N/A'} | Pages: {pages} | Step: {step:<10} | Model: {model_name:<25} | "
            f"Input: {input_tokens:<6} | Output: {output_tokens:<6} | Total: {total:<6}\n"
        )
        
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write token log: {e}")

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
        if not pdf_filename:
            return
            
        log_path = TokenLogger._get_log_path(pdf_filename)
        total = total_input + total_output
        
        summary_lines = [
            "\n" + "="*100,
            f"FINAL TOKEN USAGE SUMMARY FOR: {pdf_filename}",
            f"Total Pages Processed: {total_pages}",
            "-"*100,
            "BREAKDOWN BY MODEL:"
        ]
        
        if llm_usage_breakdown:
            for model, usage in llm_usage_breakdown.items():
                m_in = usage.get("input", 0)
                m_out = usage.get("output", 0)
                m_tot = m_in + m_out
                summary_lines.append(f"  - {model:<25}: Input: {m_in:<8} | Output: {m_out:<8} | Total: {m_tot:<8}")
        else:
            summary_lines.append("  - No model breakdown available.")
            
        summary_lines.extend([
            "-"*100,
            f"GRAND TOTAL INPUT:  {total_input}",
            f"GRAND TOTAL OUTPUT: {total_output}",
            f"GRAND TOTAL TOKENS: {total}",
            "="*100 + "\n"
        ])
        
        summary = "\n".join(summary_lines)
        
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(summary)
        except Exception as e:
            logger.error(f"Failed to write token total summary: {e}")
