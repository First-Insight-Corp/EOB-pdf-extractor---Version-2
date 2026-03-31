"""
Centralized Logging Configuration for PDF Claims Extraction
Handles all logging to single file with rotation, suitable for production monitoring
"""

import os
import logging
import logging.handlers
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Log file path with date
log_filename = os.path.join(LOGS_DIR, f"pdf_extractor_{datetime.now().strftime('%Y%m%d')}.log")

# Configure root logger with file handler
def setup_logging(app_name="PDF_Extractor", log_level=logging.INFO):
    """
    Configure centralized logging to file
    
    Args:
        app_name: Name of the application for log identification
        log_level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter with detailed information
    formatter = logging.Formatter(
        fmt='%(asctime)s - [%(name)s] - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Rotating file handler - max 10MB per file, keep 10 backup files
    file_handler = logging.handlers.RotatingFileHandler(
        log_filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Also add console handler for immediate feedback during development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Log startup information
    logger = logging.getLogger(app_name)
    logger.info(f"=== {app_name} Started ===")
    logger.info(f"Log file: {log_filename}")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    
    return logger


def get_logger(module_name):
    """
    Get a logger for a specific module
    
    Args:
        module_name: Name of the module (typically __name__)
    
    Returns:
        Logger instance for the module
    """
    return logging.getLogger(module_name)


# Application-level loggers for tracking different processes
def get_pdf_processor_logger():
    """Get logger for PDF processing pipeline"""
    return get_logger("PDF.Processor")


def get_extraction_logger():
    """Get logger for extraction agents"""
    return get_logger("Extraction.Agent")


def get_api_logger():
    """Get logger for API endpoints"""
    return get_logger("API.Endpoints")


def get_database_logger():
    """Get logger for database operations"""
    return get_logger("Database.Operations")


def log_pdf_processing(pdf_filename, doc_type, total_pages, request_id):
    """Log PDF processing start"""
    logger = get_logger("PDF.Pipeline")
    logger.info(f"[{request_id}] Starting PDF processing: {pdf_filename}")
    logger.info(f"[{request_id}] Document Type: {doc_type}")
    logger.info(f"[{request_id}] Total Pages: {total_pages}")


def log_chunk_processing(chunk_num, total_chunks, start_page, end_page, request_id):
    """Log chunk processing"""
    logger = get_logger("PDF.Pipeline")
    logger.info(f"[{request_id}] Processing Chunk {chunk_num}/{total_chunks}: Pages {start_page}-{end_page}")


def log_extraction_step(step_name, status, request_id, additional_info=None):
    """Log extraction pipeline steps"""
    logger = get_extraction_logger()
    msg = f"[{request_id}] {step_name}: {status}"
    if additional_info:
        msg += f" - {additional_info}"
    logger.info(msg)


def log_api_request(endpoint, method, request_id):
    """Log API request"""
    logger = get_api_logger()
    logger.info(f"[{request_id}] API Request: {method} {endpoint}")


def log_db_operation(operation, table_name, status, request_id=None):
    """Log database operations"""
    logger = get_database_logger()
    if request_id:
        logger.info(f"[{request_id}] DB {operation} on {table_name}: {status}")
    else:
        logger.info(f"DB {operation} on {table_name}: {status}")


if __name__ == "__main__":
    # Test logging configuration
    logger = setup_logging()
    logger.info("Logging system initialized successfully")
    logger.debug("Debug message test")
    logger.warning("Warning message test")
    logger.error("Error message test")
    print(f"\nLog file created at: {log_filename}")
