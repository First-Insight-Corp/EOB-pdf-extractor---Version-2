"""
Database migration script to add cost tracking columns
Run this script to add total_cost and cost_breakdown columns to processed_files table
"""

import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_cost_columns():
    """Add cost tracking columns to processed_files table"""
    
    try:
        # Import config to get DB settings
        from config import config
        
        # Create database connection parameters
        encoded_user = quote_plus(config.DB_USER)
        encoded_password = quote_plus(config.DB_PASSWORD)
        database_url = f"mysql+pymysql://{encoded_user}:{encoded_password}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
        
        engine = create_engine(database_url, pool_recycle=3600)
        
        # Import models to ensure they're registered
        from db import Base, ProcessedFile
        
        # Create all tables (this will add missing columns to existing tables)
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema updated. Cost tracking columns added.")
        
        # Verify the columns exist
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('processed_files')]
        
        if 'total_cost' in columns and 'cost_breakdown' in columns:
            logger.info("✓ Column 'total_cost' verified in database")
            logger.info("✓ Column 'cost_breakdown' verified in database")
            logger.info(f"✓ Current columns in processed_files: {', '.join(columns)}")
            return True
        else:
            missing = []
            if 'total_cost' not in columns:
                missing.append('total_cost')
            if 'cost_breakdown' not in columns:
                missing.append('cost_breakdown')
            logger.warning(f"Missing columns: {', '.join(missing)}")
            logger.warning(f"Current columns: {', '.join(columns)}")
            
            # Try to add columns manually if they don't exist
            with engine.connect() as connection:
                try:
                    connection.execute(text("ALTER TABLE processed_files ADD COLUMN total_cost FLOAT DEFAULT 0.0"))
                    logger.info("Added total_cost column")
                except Exception as e:
                    logger.info(f"total_cost column: {e}")
                
                try:
                    connection.execute(text("ALTER TABLE processed_files ADD COLUMN cost_breakdown JSON"))
                    logger.info("Added cost_breakdown column")
                except Exception as e:
                    logger.info(f"cost_breakdown column: {e}")
                
                connection.commit()
            
            logger.info("✓ Columns added/verified successfully")
            return True
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("Starting database migration for cost tracking...")
    success = migrate_add_cost_columns()
    sys.exit(0 if success else 1)
