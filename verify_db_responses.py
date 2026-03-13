import sys
import os
import json
sys.path.append(os.getcwd())
from db import db, ProcessedFile, DocumentFormat

if db:
    session = db.get_session()
    try:
        # 1. Create a dummy record with a final response
        fmt = session.query(DocumentFormat).first()
        if not fmt:
            print("No formats found in DB. Please run a migration or sync first.")
            sys.exit(1)
            
        test_response = {"status": "test", "data": {"claims": [{"id": 1}]}}
        new_record = ProcessedFile(
            template_id=fmt.id,
            file_path="test_verify_db.pdf",
            file_type="pdf",
            request_logs={"status": "success", "no_of_pages": 1},
            final_response=test_response
        )
        session.add(new_record)
        session.commit()
        pid = new_record.processed_file_id
        print(f"Created test record with ID: {pid}")
        
        # 2. Simulate /api/v1/responses logic
        # (Simplified version of what I put in main.py)
        results = session.query(ProcessedFile, DocumentFormat.short_name).\
            join(DocumentFormat, ProcessedFile.template_id == DocumentFormat.id, isouter=True).\
            filter(ProcessedFile.processed_file_id == pid).all()
        
        if results:
            record, fmt_name = results[0]
            print(f"Verified list logic: Found ID {record.processed_file_id} for format {fmt_name}")
        else:
            print("FAILED list logic verification")
            
        # 3. Simulate /api/v1/response/{pid} logic
        record = session.query(ProcessedFile).get(pid)
        if record and record.final_response == test_response:
            print("SUCCESS: Verified detail logic: Response matches!")
        else:
            print(f"FAILED detail logic verification. Record found: {bool(record)}")
            
    finally:
        # Cleanup
        if 'pid' in locals():
            session.query(ProcessedFile).filter_by(processed_file_id=pid).delete()
            session.commit()
            print("Cleaned up test record.")
        session.close()
else:
    print("DB connection failed")
