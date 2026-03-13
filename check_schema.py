import sys
import os
import json
# Add current directory to path if needed
sys.path.append(os.getcwd())

from db import db
from sqlalchemy import inspect

if db:
    inspector = inspect(db.engine)
    columns = inspector.get_columns('extraction_token_logs')
    res = []
    for col in columns:
        res.append({
            "name": col['name'],
            "type": str(col['type'])
        })
    print(json.dumps(res, indent=2))
else:
    print("DB connection failed")
