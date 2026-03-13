import sys
import os
sys.path.append(os.getcwd())
from agents.token_logger import TokenLogger
from db import db, ProcessedFile
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('agents.token_logger')
logger.setLevel(logging.DEBUG)

if db:
    session = db.get_session()
    # Create a dummy processed file record if needed to satisfy foreign key constraint
    dummy = ProcessedFile(file_path="dummy_test", file_type="pdf", request_logs={})
    session.add(dummy)
    session.commit()
    pid = dummy.processed_file_id
    
    from db import db, ExtractionTokenLog
    token_entry = ExtractionTokenLog(
        processed_file_id=pid,
        request_id="test_req",
        file_name="test.pdf",
        step="test_step",
        model_name="test_model",
        input_tokens=10,
        output_tokens=20,
        pages="1-2"
    )
    try:
        session.add(token_entry)
        session.commit()
    except Exception as e:
        print(f"Insertion ERROR: {e}")
        session.rollback()
        
    # Verification
    logs = session.query(ExtractionTokenLog).filter_by(processed_file_id=pid).all()
    if logs:
        print(f"SUCCESS: Log was inserted: {logs[0].file_name}, req_id: {logs[0].request_id}")
    else:
        print("FAILED: Log not found after insertion")
    
    # Clean up
    session.query(ExtractionTokenLog).filter_by(processed_file_id=pid).delete()
    session.query(ProcessedFile).filter_by(processed_file_id=pid).delete()
    session.commit()
    session.close()
