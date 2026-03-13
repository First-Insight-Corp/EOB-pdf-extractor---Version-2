import os
import logging
from db import db, DocumentFormat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FORMATS_DIR = "formats"

def migrate():
    if not db:
        logger.error("Database connection not available. Migration skipped.")
        return

    if not os.path.exists(FORMATS_DIR):
        logger.error(f"Directory {FORMATS_DIR} does not exist.")
        return

    session = db.get_session()
    
    try:
        count = 0
        for filename in os.listdir(FORMATS_DIR):
            if filename.endswith(".py") and not filename.startswith("_"):
                short_name = filename[:-3]
                filepath = os.path.join(FORMATS_DIR, filename)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    python_code = f.read()
                
                # Check if it already exists
                existing = session.query(DocumentFormat).filter_by(short_name=short_name).first()
                if existing:
                    logger.info(f"Format '{short_name}' already exists. Updating code.")
                    existing.python_code = python_code
                else:
                    logger.info(f"Inserting new format '{short_name}' into database.")
                    new_format = DocumentFormat(short_name=short_name, python_code=python_code)
                    session.add(new_format)
                count += 1
                
        session.commit()
        logger.info(f"Successfully migrated {count} formats into the database.")
    except Exception as e:
        session.rollback()
        logger.error(f"Migration failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
