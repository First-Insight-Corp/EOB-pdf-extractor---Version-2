import traceback
import logging

logging.basicConfig(level=logging.ERROR)

try:
    from db import Database
    db = Database()
    print("DB Success")
except Exception as e:
    traceback.print_exc()
