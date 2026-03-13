import sys
import os
sys.path.append(os.getcwd())
from db import db
from sqlalchemy import text

if db:
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE extraction_token_logs ADD COLUMN request_id VARCHAR(255) NULL"))
            print("Added request_id to extraction_token_logs")
        except Exception as e:
            print(f"Failed to add request_id: {e}")
            
        try:
            conn.execute(text("ALTER TABLE extraction_token_logs ADD COLUMN file_name VARCHAR(1024) NULL"))
            print("Added file_name to extraction_token_logs")
        except Exception as e:
            print(f"Failed to add file_name: {e}")

        try:
            conn.execute(text("ALTER TABLE auditor_critic_logs ADD COLUMN request_id VARCHAR(255) NULL"))
            print("Added request_id to auditor_critic_logs")
        except Exception as e:
            print(f"Failed to add request_id: {e}")

        try:
            conn.execute(text("ALTER TABLE auditor_critic_logs ADD COLUMN file_name VARCHAR(1024) NULL"))
            print("Added file_name to auditor_critic_logs")
        except Exception as e:
            print(f"Failed to add file_name: {e}")
            
        conn.commit()
