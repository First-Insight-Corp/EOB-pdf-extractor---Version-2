import sys
import os
import traceback
sys.path.append(os.getcwd())

from db import db, ProcessedFile, ExtractionTokenLog
from sqlalchemy import inspect
import json

if db:
    session = db.get_session()
    try:
        processed_count = session.query(ProcessedFile).count()
        token_count = session.query(ExtractionTokenLog).count()
        output = f"Row counts:\n - processed_files: {processed_count}\n - extraction_token_logs: {token_count}\n"
        
        if processed_count > 0:
            last_processed = session.query(ProcessedFile).order_by(ProcessedFile.processed_file_id.desc()).first()
            output += f"Last processed_file_id: {last_processed.processed_file_id}\n"
            output += f"Last request_logs: {last_processed.request_logs}\n"
        
        with open('data_out.txt', 'w', encoding='utf-8') as f:
            f.write(output)

        inspector = inspect(db.engine)
        columns = inspector.get_columns('extraction_token_logs')
        res = []
        for col in columns:
            res.append({
                "name": col['name'],
                "type": str(col['type'])
            })
        with open('schema_out.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(res, indent=2))
        
        print("Done")
    except Exception as e:
        with open('data_out.txt', 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())
    finally:
        session.close()
else:
    with open('data_out.txt', 'w', encoding='utf-8') as f:
        f.write("DB connection failed\n")
