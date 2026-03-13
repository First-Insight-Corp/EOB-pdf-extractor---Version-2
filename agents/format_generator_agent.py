"""
Format Generator Agent: uses Claude to analyze a new PDF and generate
a complete Pydantic format file (formats/{short_name}.py) that is
immediately usable by the extraction pipeline.
"""

import os
import base64
import logging
import importlib.util
import sys
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class FormatGeneratorAgent:
    """
    Uses Claude (claude-sonnet via Anthropic SDK) to inspect a new PDF
    and auto-generate a Pydantic format file based on all existing formats.
    """

    FORMATS_DIR = "formats"

    def __init__(self, anthropic_key: str = "", gemini_key: str = ""):
        self._claude_client = None
        if anthropic_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=anthropic_key)
            except ImportError:
                logger.warning("anthropic package not installed")

        self._gemini_configured = False
        if gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self._gemini_configured = True
            except ImportError:
                logger.warning("google-generativeai package not installed")

        self._existing_formats = self._load_existing_formats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_existing_formats(self) -> dict:
        """Read all existing format files from Database (and disk) and return {name: code} dict."""
        formats = {}
        
        # 1. Try loading from Database
        try:
            from db import db, DocumentFormat
            if db:
                session = db.get_session()
                db_formats = session.query(DocumentFormat).all()
                for fmt in db_formats:
                    formats[fmt.short_name] = fmt.python_code
                session.close()
                logger.info(f"Loaded {len(formats)} formats from database for Claude references.")
        except Exception as e:
            logger.warning(f"Could not load formats from DB for reference: {e}")

        # 2. Add local formats if not already loaded from DB
        if os.path.isdir(self.FORMATS_DIR):
            for fname in os.listdir(self.FORMATS_DIR):
                if fname.endswith(".py") and not fname.startswith("_"):
                    short_name = os.path.splitext(fname)[0]
                    if short_name not in formats:
                        fpath = os.path.join(self.FORMATS_DIR, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                formats[short_name] = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read format {fname}: {e}")
                            
        return formats


    def _build_system_prompt(self, short_name: str, azure_text: str = "") -> str:
        # Limit to 3 most recent examples to avoid context overflow / truncation
        recent_examples = list(self._existing_formats.items())[-3:]
        examples_block = ""
        for fmt_name, fmt_code in recent_examples:
            examples_block += f"\n\n### EXISTING FORMAT: {fmt_name}.py\n```python\n{fmt_code}\n```"

        header = (
            f"You are an expert Python developer specializing in healthcare EDI (EOB/Remittance Advice) documents.\n\n"
            f"Your task is to generate a COMPLETE, VALID Python file called `{short_name}.py` that will be placed "
            f"inside the `formats/` folder of an AI extraction system.\n\n"
            "### SYSTEM CONTEXT\n"
            "The extraction pipeline uses LangChain + Claude/Gemini to extract structured data from PDF documents. "
            "Each format file defines:\n"
            "1. Pydantic models for that specific document type.\n"
            "2. A `SCHEMA_DESCRIPTION` string that guides the AI extractor.\n"
            "3. Helper functions used by the pipeline.\n\n"
        )

        azure_context = ""
        if azure_text:
            azure_context = (
                "### HIGH-QUALITY OCR & TABLE DATA (Azure Document Intelligence)\n"
                "Use the following structured text and table data as Your Primary Source of Truth for "
                "identifying column headers, field relationships, and document structure:\n"
                f"```text\n{azure_text[:20000]}\n```\n\n"
            )

        structure_rules = (
            "### REQUIRED FILE STRUCTURE\n"
            "The generated file MUST EXACTLY contain these components (in this order):\n\n"
            "```python\n"
            "from __future__ import annotations\n"
            "from typing import List, Optional, Any, Dict\n"
            "from pydantic import BaseModel, Field, field_validator\n\n"
            "class ServiceLine(BaseModel): ...\n"
            "class ClaimModel(BaseModel): ...\n"
            "class ResponseModel(BaseModel): ...\n\n"
            "class BatchModel(BaseModel):\n"
            '    claims: List[ClaimModel] = Field(..., description="List of claims found in this batch")\n'
            '    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Batch-level metadata")\n\n'
            "def map_extracted_data(extracted_claims: List[dict], aggregated_metadata: dict) -> dict: ...\n\n"
            'SCHEMA_DESCRIPTION = """..."""\n\n'
            "def section_builder(text: str) -> List[Dict[str, str]]: ...\n\n"
            "def calculate_totals(claims_data: dict) -> dict: ...\n"
            "```\n\n"
            "### CRITICAL DATA FLOW RULES (NEVER VIOLATE - causes null output if wrong)\n\n"
            "How the pipeline works:\n"
            '1. The AI extracts each batch and returns {"claims": [...], "metadata": {...}}.\n'
            "2. All batches are merged: extracted_claims = list of all claim dicts, aggregated_metadata = merged metadata.\n"
            "3. map_extracted_data(extracted_claims, aggregated_metadata) builds the final response dict.\n"
            "4. ResponseModel(**that_dict) validates the result.\n\n"
            "THEREFORE:\n"
            "- map_extracted_data MUST return a FLAT dict whose keys EXACTLY match ResponseModel's field names.\n"
            '  CORRECT:  return {"claims": extracted_claims, "payer_info": ..., "summary": ...}\n'
            '  WRONG:    return {"my_document_page": {"claims": extracted_claims, ...}}  <- ALL NULLS\n'
            "- ResponseModel fields must exactly match the flat keys from map_extracted_data.\n"
            "- calculate_totals receives the OUTPUT of map_extracted_data, so ALWAYS use top-level 'claims' key:\n"
            '  CORRECT:  claims = claims_data.get("claims", [])\n'
            '  WRONG:    claims = claims_data.get("my_document_page", {}).get("claims", [])\n'
            "- aggregated_metadata is FLAT. Never try to unwrap a nested document-type key from it.\n\n"
            "### RULES\n"
            "- All fields must use Optional[...] with Field(None, description='...').\n"
            "- KEEP DESCRIPTIONS CONCISE (max 10 words). List at most 2 example values per field.\n"
            "- SCHEMA_DESCRIPTION should be concise but high-impact (10-15 lines total).\n"
            "- Output ONLY the Python code. No markdown fences. No explanation.\n\n"
        )

        footer = (
            f"### REFERENCE EXAMPLES\n"
            f"Study the existing formats carefully before generating:{examples_block}\n\n"
            f"### TASK\n"
            f"Analyze the PDF images provided. Generate the `{short_name}.py` format file.\n"
            f"The format's document type short name is: `{short_name}`\n"
        )

        return header + azure_context + structure_rules + footer


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_format(
        self,
        pdf_images: List[str],
        short_name: str,
        provider: str = "claude",
        model_name: Optional[str] = None,
        azure_text: str = ""
    ) -> str:
        """
        Send images + examples to Claude/Gemini and return generated code.
        Includes a self-correction loop (up to 3 retries) if syntax errors or
        missing components are detected.
        """
        short_name = short_name.strip().lower().replace(" ", "_")
        system_prompt = self._build_system_prompt(short_name, azure_text)
        
        last_error = ""
        last_code = ""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.warning(f"Self-correction attempt {attempt}/{max_retries-1} for {short_name}...")
                    
                    if "unterminated triple-quoted string" in last_error or "truncated" in last_error:
                        feedback_prompt = (
                            f"IMPORTANT: Your last response was TRUNCATED because it was too long. "
                            f"Generate a SHORTER version of `{short_name}.py`. \n"
                            f"Make the `SCHEMA_DESCRIPTION` very concise (max 10 lines) and ensure the "
                            f"file ends correctly with the `calculate_totals` and `section_builder` functions."
                        )
                    else:
                        feedback_prompt = (
                            f"The last code you generated for `{short_name}` had the following error:\n"
                            f"{last_error}\n\n"
                            f"Please fix the code and provide the full, corrected version. Keep the structure exactly as requested."
                        )
                    if provider == "gemini":
                        code = self._generate_with_gemini(pdf_images, short_name, system_prompt, model_name, feedback_prompt)
                    else:
                        code = self._generate_with_claude(pdf_images, short_name, system_prompt, model_name, feedback_prompt)
                else:
                    if provider == "gemini":
                        code = self._generate_with_gemini(pdf_images, short_name, system_prompt, model_name)
                    else:
                        code = self._generate_with_claude(pdf_images, short_name, system_prompt, model_name)

                # Validate code structure and syntax without saving yet
                self.validate_code(code, short_name)
                return code # Success!

            except ValueError as e:
                last_error = str(e)
                last_code = code
                
                # Debug: save failed code to inspect truncation
                try:
                    debug_path = os.path.join("tmp", f"failed_gen_{short_name}_attempt_{attempt}.py")
                    os.makedirs("tmp", exist_ok=True)
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(code)
                    logger.info(f"Saved failed code to {debug_path} for inspection.")
                except Exception:
                    pass

                if attempt == max_retries - 1:
                    logger.error(f"Format generation failed after {max_retries} attempts: {last_error}")
                    raise

        return "" # Should not reach here

    def validate_code(self, code: str, short_name: str):
        """
        Performs the same validation as save_format but does not write to disk.
        """
        # --- Syntax check via compile ---
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            raise ValueError(f"Generated code has a syntax error: {e}")

        # --- Check mandatory components ---
        required = [
            "class BatchModel",
            "class ClaimModel",
            "def map_extracted_data",
            "SCHEMA_DESCRIPTION",
            "def calculate_totals",
            "def section_builder",
        ]
        missing = [r for r in required if r not in code]
        if missing:
            raise ValueError(
                f"Generated code is missing required components: {missing}"
            )

    def _generate_with_claude(self, pdf_images, short_name, system_prompt, model_name, feedback_prompt: Optional[str] = None) -> str:
        if not self._claude_client:
            raise ValueError("Claude client not initialized. check ANTHROPIC_API_KEY.")
            
        model = model_name or "claude-sonnet-4-20250514"
        messages = []
        
        user_content = []
        for i, img_b64 in enumerate(pdf_images[:5], 1):
            user_content.append({"type": "text", "text": f"### PDF PAGE {i}"})
            user_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })

        if feedback_prompt:
            user_content.append({"type": "text", "text": feedback_prompt})
        else:
            user_content.append({
                "type": "text",
                "text": f"Generate code for `{short_name}`. Output ONLY Python code."
            })

        messages.append({"role": "user", "content": user_content})

        logger.info(f"Claude generating format: {short_name} using {model}")
        response = self._claude_client.messages.create(
            model=model,
            max_tokens=8096,
            system=system_prompt,
            messages=messages,
        )
        return self._clean_code(response.content[0].text if response.content else "")

    def _generate_with_gemini(self, pdf_images, short_name, system_prompt, model_name, feedback_prompt: Optional[str] = None) -> str:
        if not self._gemini_configured:
            raise ValueError("Gemini not configured. Check GEMINI_API_KEY.")
            
        import google.generativeai as genai
        model = genai.GenerativeModel(model_name or "gemini-2.0-flash", system_instruction=system_prompt)
        
        parts = []
        for i, img_b64 in enumerate(pdf_images[:5], 1):
            parts.append(f"### PDF PAGE {i}")
            parts.append({
                "mime_type": "image/png",
                "data": base64.b64decode(img_b64)
            })
            
        if feedback_prompt:
            parts.append(feedback_prompt)
        else:
            parts.append(f"Generate code for `{short_name}`. Output ONLY Python code.")
        
        logger.info(f"Gemini generating format: {short_name} using {model_name or 'gemini-2.0-flash'}")
        response = model.generate_content(parts)
        return self._clean_code(response.text or "")

    def _clean_code(self, code: str) -> str:
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        elif code.startswith("```"):
            code = code[3:].strip()
        if code.endswith("```"):
            code = code[:-3].strip()
        
        # Check for potential truncation (e.g., doesn't end with a closing quote or block)
        # This is a heuristic: if it doesn't end with a closing bracket, quote, or dedented line, it might be truncated.
        typical_suffixes = ("'", '"', ")", "]", "}", "pass", "None", "\n", '"""', "'''")
        if not code.strip().endswith(typical_suffixes) and len(code) > 7000:
             logger.warning("Generated code appears truncated.")
             
        return code

    def save_format(self, code: str, short_name: str) -> str:
        """
        Validate and save the generated Python code to formats/{short_name}.py.
        Raises ValueError if the code fails to import.
        Returns the saved file path.
        """
        short_name = short_name.strip().lower().replace(" ", "_")
        os.makedirs(self.FORMATS_DIR, exist_ok=True)
        file_path = os.path.join(self.FORMATS_DIR, f"{short_name}.py")

        # --- Syntax check via compile ---
        try:
            compile(code, file_path, "exec")
        except SyntaxError as e:
            raise ValueError(f"Generated code has a syntax error: {e}")

        # --- Check mandatory components ---
        required = [
            "class BatchModel",
            "class ClaimModel",
            "def map_extracted_data",
            "SCHEMA_DESCRIPTION",
            "def calculate_totals",
            "def section_builder",
        ]
        missing = [r for r in required if r not in code]
        if missing:
            raise ValueError(
                f"Generated code is missing required components: {missing}"
            )
            
        header = (
            f"# Auto-generated format file for document type: {short_name}\n"
            f"# Generated by FormatGeneratorAgent on {datetime.now().isoformat()}\n\n"
        )
        final_code = header + code

        # --- Save to Database ---
        try:
            from db import db, DocumentFormat
            if db:
                session = db.get_session()
                existing = session.query(DocumentFormat).filter_by(short_name=short_name).first()
                if existing:
                    existing.python_code = final_code
                    logger.info(f"Updated format '{short_name}' in database.")
                else:
                    new_fmt = DocumentFormat(short_name=short_name, python_code=final_code)
                    session.add(new_fmt)
                    logger.info(f"Inserted new format '{short_name}' into database.")
                session.commit()
                session.close()
            else:
                logger.warning("DB not initialized; skipping DB save for new format.")
        except Exception as e:
            logger.error(f"Failed to save generated format to DB: {e}")

        # --- Write to disk (fallback / backup) ---
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        logger.info(f"Format saved to {file_path}")
        # --- Refresh config.SUPPORTED_FORMATS immediately ---
        try:
            from config import config
            config.SUPPORTED_FORMATS = config.get_supported_formats()
            logger.info(f"Updated SUPPORTED_FORMATS: {config.SUPPORTED_FORMATS}")
        except Exception as e:
            logger.warning(f"Could not refresh supported formats: {e}")

        return file_path
