import sys
import os
sys.path.append(os.getcwd())
from db import db, AuditorCriticLog, ProcessedFile

if db:
    session = db.get_session()
    # Create dummy processed file
    dummy = ProcessedFile(file_path="dummy_auditor_test", file_type="pdf", request_logs={})
    session.add(dummy)
    session.commit()
    pid = dummy.processed_file_id
    
    # Try inserting an AuditorCriticLog
    log_entry = AuditorCriticLog(
        processed_file_id=pid,
        request_id="test_req",
        file_name="test.pdf",
        loop_number=1,
        auditor_issues=["issue 1"],
        auditor_lessons=["lesson 1"],
        auditor_raw_response="test response",
        critic_instructions="test instructions"
    )
    
    try:
        session.add(log_entry)
        session.commit()
        print("SUCCESS: AuditorCriticLog inserted!")
    except Exception as e:
        print(f"Insertion ERROR: {e}")
        session.rollback()
        
    # Verification
    logs = session.query(AuditorCriticLog).filter_by(processed_file_id=pid).all()
    if logs:
        print(f"Verified read: file_name={logs[0].file_name}, req_id={logs[0].request_id}")
    else:
        print("FAILED: Log not found after insertion")
        
    # Clean up
    session.query(AuditorCriticLog).filter_by(processed_file_id=pid).delete()
    session.query(ProcessedFile).filter_by(processed_file_id=pid).delete()
    session.commit()
    session.close()
