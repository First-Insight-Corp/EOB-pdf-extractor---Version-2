import sys
import os
sys.path.append(os.getcwd())
from db import db
from sqlalchemy import text

if db:
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE processed_files ADD COLUMN final_response JSON NULL"))
            conn.commit()
            print("Successfully added final_response column to processed_files table.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("Column final_response already exists.")
            else:
                print(f"Failed to add final_response column: {e}")
else:
    print("Database connection not available.")
