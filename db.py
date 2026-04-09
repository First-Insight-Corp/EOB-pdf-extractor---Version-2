import logging
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from config import config
from logs_config import get_database_logger

logger = get_database_logger()

# Base class for SQLAlchemy models
Base = declarative_base()

class DocumentFormat(Base):
    __tablename__ = 'document_formats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_name = Column(String(255), unique=True, nullable=False)
    python_code = Column(Text(length=16777215), nullable=False) # LONGTEXT equivalent
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to processed files
    processed_files = relationship("ProcessedFile", back_populates="template")


class LearningKnowledge(Base):
    __tablename__ = 'learning_knowledge'

    id = Column(Integer, primary_key=True, autoincrement=True)
    format_name = Column(String(255), unique=True, nullable=False)
    lessons = Column(JSON, nullable=False, default=list)
    layout_patterns = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProcessedFile(Base):
    __tablename__ = 'processed_files'

    processed_file_id = Column(Integer, primary_key=True, autoincrement=True)
    date_time = Column(DateTime, default=datetime.utcnow)
    template_id = Column(Integer, ForeignKey('document_formats.id'), nullable=True)
    file_path = Column(String(1024), nullable=True)
    file_type = Column(String(50), default='pdf')
    request_logs = Column(JSON, nullable=False)
    final_response = Column(JSON, nullable=True)
    final_response_raw_text = Column(Text(length=16777215), nullable=True)
    total_cost = Column(Float, default=0.0, nullable=True)
    cost_breakdown = Column(JSON, nullable=True)

    # Relationship to document format
    template = relationship("DocumentFormat", back_populates="processed_files")
    
    # Relationships to logs
    token_logs = relationship("ExtractionTokenLog", back_populates="processed_file")
    agent_logs = relationship("AuditorCriticLog", back_populates="processed_file")

class ExtractionTokenLog(Base):
    __tablename__ = 'extraction_token_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    processed_file_id = Column(Integer, ForeignKey('processed_files.processed_file_id'))
    request_id = Column(String(255), nullable=True)
    file_name = Column(String(1024), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    step = Column(String(255))
    model_name = Column(String(255))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    pages = Column(String(255))

    # Relationship to processed file
    processed_file = relationship("ProcessedFile", back_populates="token_logs")

class AuditorCriticLog(Base):
    __tablename__ = 'auditor_critic_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    processed_file_id = Column(Integer, ForeignKey('processed_files.processed_file_id'))
    request_id = Column(String(255), nullable=True)
    file_name = Column(String(1024), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    loop_number = Column(Integer)
    auditor_issues = Column(JSON)
    auditor_lessons = Column(JSON)
    auditor_raw_response = Column(Text)
    critic_instructions = Column(Text)

    # Relationship to processed file
    processed_file = relationship("ProcessedFile", back_populates="agent_logs")

from urllib.parse import quote_plus

class Database:
    def __init__(self):
        # We use a two-step connection process.
        # First, connect without a specific database to ensure the DB exists.
        self._ensure_database_exists()
        
        encoded_user = quote_plus(config.DB_USER)
        encoded_password = quote_plus(config.DB_PASSWORD)
        
        # Now create the actual engine connected to the specific database
        self.database_url = f"mysql+pymysql://{encoded_user}:{encoded_password}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
        self.engine = create_engine(self.database_url, pool_recycle=3600)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Ensure tables exist
        Base.metadata.create_all(bind=self.engine)
        logger.info(f"Database {config.DB_NAME} initialized and tables created.")

    def _ensure_database_exists(self):
        """Connect to MySQL server and create the database if it doesn't exist."""
        try:
            encoded_user = quote_plus(config.DB_USER)
            encoded_password = quote_plus(config.DB_PASSWORD)
            
            temp_engine = create_engine(
                f"mysql+pymysql://{encoded_user}:{encoded_password}@{config.DB_HOST}:{config.DB_PORT}"
            )
            with temp_engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME}"))
            logger.info(f"Ensured database '{config.DB_NAME}' exists.")
        except Exception as e:
            logger.error(f"Failed to ensure database exists: {e}")
            raise

    def get_session(self):
        return self.SessionLocal()

# Global database instance
try:
    db = Database()
except Exception as e:
    logger.error(f"Could not initialize database: {e}")
    db = None
