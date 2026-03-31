import logging
from typing import Any

logger = logging.getLogger(__name__)

class GlobalLearningMemory:
    """
    Adaptive memory that tracks cross-batch patterns and Auditor feedback.
    Enables the agent to "learn" from Page 1 to improve Page 10, 
    and now persists across different documents of the same format.
    """
    def __init__(self):
        self.lessons = []
        self.layout_patterns = {}
        self.failed_fields = set()
        self.active_state = {} # Persistent state (e.g. current_doctor)
        self.current_format_name = None

    def _load_from_db(self, format_name: str) -> bool:
        try:
            from db import db, LearningKnowledge
            if not db:
                return False

            session = db.get_session()
            try:
                record = session.query(LearningKnowledge).filter_by(format_name=format_name.lower()).first()
            finally:
                session.close()

            if not record:
                return False

            self.lessons = record.lessons or []
            self.layout_patterns = record.layout_patterns or {}
            logger.info(f"Loaded {len(self.lessons)} persistent lessons for {format_name} from database")
            return True
        except Exception as e:
            logger.warning(f"Failed loading memory for {format_name} from database: {e}")
            return False

    def _save_to_db(self, format_name: str) -> bool:
        try:
            from db import db, LearningKnowledge
            if not db:
                return False

            session = db.get_session()
            try:
                normalized_name = format_name.lower()
                record = session.query(LearningKnowledge).filter_by(format_name=normalized_name).first()

                if record:
                    record.lessons = self.lessons
                    record.layout_patterns = self.layout_patterns
                else:
                    record = LearningKnowledge(
                        format_name=normalized_name,
                        lessons=self.lessons,
                        layout_patterns=self.layout_patterns,
                    )
                    session.add(record)

                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

            return True
        except Exception as e:
            logger.warning(f"Failed saving memory for {format_name} to database: {e}")
            return False

    def load(self, format_name: str):
        """Load persistent memory for a specific format from database only."""
        self.current_format_name = format_name.lower()
        self.lessons = []
        self.layout_patterns = {}

        try:
            if self._load_from_db(format_name):
                return

            logger.info(f"No existing memory found for {format_name}; starting fresh")
        except Exception as e:
            logger.error(f"Failed to load memory for {format_name}: {e}")

    def save(self, format_name: str):
        """Save current memory to persistent storage (database only)."""
        self.current_format_name = format_name.lower()
        try:
            if self._save_to_db(format_name):
                logger.info(f"Saved persistent memory for {format_name} to database")
            else:
                logger.warning(f"Could not persist memory for {format_name}: database unavailable")
        except Exception as e:
            logger.error(f"Failed to save memory for {format_name}: {e}")

    def add_lesson(self, lesson: Any):
        # Handle dict lessons from model
        lesson_text = str(lesson)
        if isinstance(lesson, dict):
            lesson_text = lesson.get('description', lesson.get('lesson', str(lesson)))
            
        if lesson_text not in self.lessons:
            self.lessons.append(lesson_text)
            # Cap lessons to the last 25 to prevent prompt bloat while allowing growth.
            if len(self.lessons) > 25:
                self.lessons.pop(0)
            logger.info(f"Learned NEW lesson (total: {len(self.lessons)}): {lesson_text}")

            # Persist immediately so DB stays in sync with in-flight learning.
            if self.current_format_name:
                self.save(self.current_format_name)
            
    def record_failure(self, field_name: str):
        self.failed_fields.add(field_name)
        
    def get_context_injection(self) -> str:
        if not self.lessons and not self.failed_fields:
            return ""
            
        context = "\n### LESSONS LEARNED FROM PREVIOUS DOCUMENTS/PAGES (ADAPTIVE KNOWLEDGE):"
        if self.lessons:
            for i, lesson in enumerate(self.lessons):
                context += f"\n{i+1}. {lesson}"
        
        if self.failed_fields:
            context += f"\nCRITICAL: Previous attempts failed to extract these fields: {list(self.failed_fields)}. Prioritize finding these."
            
        if self.active_state.get('current_doctor'):
            context += f"\nIMPORTANT CONTEXT: The active treating doctor from previous pages is '{self.active_state['current_doctor']}'. If no new doctor name is explicitly stated in a header on the current page, you MUST continue using '{self.active_state['current_doctor']}' for all extracted claims."
            
        return context


def bootstrap_learning_memory_to_db(force_upsert: bool = False, log_details: bool = False) -> int:
    """Deprecated in DB-only mode; retained for backward compatibility."""
    if force_upsert or log_details:
        logger.info(
            "bootstrap_learning_memory_to_db is deprecated: learning memory is now DB-only at runtime"
        )
    return 0
