import sys
import os
import json
import logging

# Ensure current directory is in path
sys.path.append(os.getcwd())

from db import db, DocumentFormat
from format_loader import FormatLoader
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_db_format_loading():
    if not db:
        print("DB not available")
        return

    short_name = "test_db_only_format"
    # Ensure local file does not exist
    local_path = os.path.join("formats", f"{short_name}.py")
    if os.path.exists(local_path):
        os.remove(local_path)
        print(f"Removed existing local file: {local_path}")

    # 1. Insert into DB
    test_code = """
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class ServiceLine(BaseModel):
    description: Optional[str] = None

class ClaimModel(BaseModel):
    services: List[ServiceLine] = []

class ResponseModel(BaseModel):
    claims: List[ClaimModel] = []

class BatchModel(BaseModel):
    claims: List[ClaimModel] = []
    metadata: Dict[str, Any] = {}

SCHEMA_DESCRIPTION = "TEST_DB_ONLY_SCHEMA_VERIFIED"

def map_extracted_data(claims, metadata):
    return {"claims": claims}

def calculate_totals(data):
    return {}

def section_builder(text):
    return []
"""
    session = db.get_session()
    try:
        # Cleanup if exists
        session.query(DocumentFormat).filter_by(short_name=short_name).delete()
        
        new_fmt = DocumentFormat(short_name=short_name, python_code=test_code)
        session.add(new_fmt)
        session.commit()
        print(f"Inserted '{short_name}' into DB.")
    finally:
        session.close()

    # 2. Try to load it
    try:
        # Ensure config recognizes it
        supported = config.get_supported_formats()
        if short_name not in supported:
            print(f"FAILED: {short_name} not in supported formats list!")
            return

        print(f"Loading format: {short_name}")
        components = FormatLoader.load_format(local_path)
        
        # 3. Verify
        if components['SCHEMA_DESCRIPTION'] == "TEST_DB_ONLY_SCHEMA_VERIFIED":
            print("SUCCESS: Format loaded correctly from DB with no local file!")
        else:
            print(f"FAILED: Schema description mismatch: {components['SCHEMA_DESCRIPTION']}")
            
    except Exception as e:
        print(f"ERROR during loading: {e}")
    finally:
        # Cleanup DB
        session = db.get_session()
        session.query(DocumentFormat).filter_by(short_name=short_name).delete()
        session.commit()
        session.close()
        print("Cleaned up test format from DB.")

if __name__ == "__main__":
    test_db_format_loading()
