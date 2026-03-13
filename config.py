"""
Configuration file for PDF Claims Extraction API
Store all API keys and configuration settings here
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
class APIConfig:
    """API Configuration settings"""

    # Extraction Agent: "gemini" or "claude" (switch in .env)
    _ea = os.getenv("EXTRACTION_AGENT", "gemini").lower().strip()
    EXTRACTION_AGENT = _ea if _ea in ("gemini", "claude") else "gemini"

    # Auditor Agent: "gemini" or "claude"
    _aa = os.getenv("AUDITOR_AGENT", "gemini").lower().strip()
    AUDITOR_AGENT = _aa if _aa in ("gemini", "claude") else "gemini"

    # Critic Agent: "gemini" or "claude"
    _ca = os.getenv("CRITIC_AGENT", "gemini").lower().strip()
    CRITIC_AGENT = _ca if _ca in ("gemini", "claude") else "gemini"

    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    # Claude (Anthropic) API Configuration - for EXTRACTION_AGENT=claude
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")  # Opus 4 / Sonnet 4

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Format Generator Configuration
    _fga = os.getenv("FORMAT_GEN_AGENT", "claude").lower().strip()
    FORMAT_GEN_AGENT = _fga if _fga in ("gemini", "claude") else "claude"
    
    _fgm_default = CLAUDE_MODEL if FORMAT_GEN_AGENT == "claude" else GEMINI_MODEL
    FORMAT_GEN_MODEL = os.getenv("FORMAT_GEN_MODEL", _fgm_default)

    # Azure Document Intelligence Configuration (primary for table-aware text extraction)
    AZURE_DI_KEY = os.getenv("AZURE_DI_KEY", "")
    AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT", "")

    # Logging Preferences (Auditor and Critic logs)
    LOG_AUDITOR = os.getenv("LOG_AUDITOR", "true").lower() == "true"
    LOG_CRITIC = os.getenv("LOG_CRITIC", "true").lower() == "true"

    # Database Configuration
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "eob_db")


    # Server Configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # Processing Configuration
    MAX_PAGES_PER_BATCH = int(os.getenv("MAX_PAGES_PER_BATCH", 5))
    MAX_PAGES_PER_CHUNK = int(os.getenv("MAX_PAGES_PER_CHUNK", 20))  # Threshold for physical PDF splitting
    MAX_REFINEMENT_RETRIES = int(os.getenv("MAX_REFINEMENT_RETRIES", 3))
    MAX_AUDITOR_CRITIC_LOOPS = int(os.getenv("MAX_AUDITOR_CRITIC_LOOPS", 4))  # Extraction → Auditor → Critic → re-extract
    PDF_DPI = int(os.getenv("PDF_DPI", 300))
    
    # Directory Configuration
    UPLOAD_DIR = "uploads"
    RESPONSE_DIR = "responses"
    FORMATS_DIR = "formats"
    
    # Supported document types: discovered from DB and formats/*.py
    @classmethod
    def get_supported_formats(cls) -> list:
        formats = set()
        local_files = {}

        # 1. Discover local files first
        if os.path.isdir(cls.FORMATS_DIR):
            for f in os.listdir(cls.FORMATS_DIR):
                if f.endswith(".py") and not f.startswith("_"):
                    short_name = os.path.splitext(f)[0]
                    local_files[short_name] = os.path.join(cls.FORMATS_DIR, f)
                    formats.add(short_name)

        # 2. Get from Database and Sync
        try:
            from db import db, DocumentFormat
            if db:
                session = db.get_session()
                # Use a cleaner query to get all short_names
                db_formats = session.query(DocumentFormat).all()
                db_short_names = {fmt.short_name for fmt in db_formats}
                
                # Update total set from DB (DB is source of truth)
                for name in db_short_names:
                    formats.add(name)

                # Sync local files -> DB if missing (One-way sync to DB)
                synced_count = 0
                for short_name, fpath in local_files.items():
                    if short_name not in db_short_names:
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                code = f.read()
                                new_fmt = DocumentFormat(short_name=short_name, python_code=code)
                                session.add(new_fmt)
                                synced_count += 1
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error(f"Failed to read local format {fpath} for sync: {e}")
                
                if synced_count > 0:
                    session.commit()
                    import logging
                    logging.getLogger(__name__).info(f"Auto-synced {synced_count} local formats to database.")
                
                session.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not sync/load formats from DB: {e}")
                    
        return sorted(list(formats))
    
    SUPPORTED_FORMATS = []  # set below after class body
    
    @classmethod
    def validate(cls):
        """Validate configuration for all configured agents"""
        # Validate Extractor
        if cls.EXTRACTION_AGENT == "gemini" and not cls.GEMINI_API_KEY:
            raise ValueError("EXTRACTION_AGENT=gemini but GEMINI_API_KEY not set in .env")
        if cls.EXTRACTION_AGENT == "claude" and not cls.ANTHROPIC_API_KEY:
            raise ValueError("EXTRACTION_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
            
        # Validate Auditor
        if cls.AUDITOR_AGENT == "gemini" and not cls.GEMINI_API_KEY:
            raise ValueError("AUDITOR_AGENT=gemini but GEMINI_API_KEY not set in .env")
        if cls.AUDITOR_AGENT == "claude" and not cls.ANTHROPIC_API_KEY:
            raise ValueError("AUDITOR_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
            
        # Validate Critic
        if cls.CRITIC_AGENT == "gemini" and not cls.GEMINI_API_KEY:
            raise ValueError("CRITIC_AGENT=gemini but GEMINI_API_KEY not set in .env")
        if cls.CRITIC_AGENT == "claude" and not cls.ANTHROPIC_API_KEY:
            raise ValueError("CRITIC_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
        # Create directories if they don't exist
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
        os.makedirs(cls.RESPONSE_DIR, exist_ok=True)
        os.makedirs(cls.FORMATS_DIR, exist_ok=True)
        return True
    
    @classmethod
    def get_format_file(cls, document_type: str) -> str:
        """Get format file path for document type. Returns path even if file isn't on disk (content may be in DB)."""
        return os.path.join(cls.FORMATS_DIR, f"{document_type.lower()}.py")


# Create singleton instance
config = APIConfig()
# Discover supported formats from formats/ directory
config.SUPPORTED_FORMATS = config.get_supported_formats() or ["vsp", "eyemed"]
