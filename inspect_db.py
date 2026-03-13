import sys
import os
# Add current directory to path if needed
sys.path.append(os.getcwd())

from db import db
from sqlalchemy import inspect

def check_table(table_name):
    if db:
        inspector = inspect(db.engine)
        if not inspector.has_table(table_name):
            print(f"Table {table_name} does not exist.")
            return
        columns = inspector.get_columns(table_name)
        print(f"--- Columns in {table_name} ---")
        for col in columns:
            print(f"{col['name']}: {col['type']}")
    else:
        print("DB connection failed")

if __name__ == "__main__":
    check_table('processed_files')
    print()
    check_table('extraction_token_logs')
