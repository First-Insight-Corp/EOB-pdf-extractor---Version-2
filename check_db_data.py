import sys
import os
# Add current directory to path if needed
sys.path.append(os.getcwd())

from db import db, ProcessedFile, ExtractionTokenLog

if db:
    session = db.get_session()
    try:
        processed_count = session.query(ProcessedFile).count()
        token_count = session.query(ExtractionTokenLog).count()
        print(f"Row counts:")
        print(f" - processed_files: {processed_count}")
        print(f" - extraction_token_logs: {token_count}")
        
        if processed_count > 0:
            last_processed = session.query(ProcessedFile).order_by(ProcessedFile.processed_file_id.desc()).first()
            print(f"Last processed_file_id: {last_processed.processed_file_id}")
            print(f"Last request_logs: {last_processed.request_logs}")
    finally:
        session.close()
else:
    print("DB connection failed")
