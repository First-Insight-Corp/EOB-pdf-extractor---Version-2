import logging
import json
import os
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
        self.storage_dir = os.path.join(os.getcwd(), "knowledge", "learning")
    
    def _get_storage_path(self, format_name: str) -> str:
        os.makedirs(self.storage_dir, exist_ok=True)
        return os.path.join(self.storage_dir, f"{format_name.lower()}_memory.json")

    def load(self, format_name: str):
        """Load persistent memory for a specific format"""
        path = self._get_storage_path(format_name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.lessons = data.get("lessons", [])
                    self.layout_patterns = data.get("layout_patterns", {})
                    # failed_fields is usually transient per-session, but we could persist it if needed
                    # For now, let's just persist lessons and patterns
                    logger.info(f"Loaded {len(self.lessons)} persistent lessons for {format_name}")
            except Exception as e:
                logger.error(f"Failed to load memory for {format_name}: {e}")

    def save(self, format_name: str):
        """Save current memory to persistent storage"""
        path = self._get_storage_path(format_name)
        try:
            data = {
                "lessons": self.lessons,
                "layout_patterns": self.layout_patterns
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved persistent memory for {format_name} to {path}")
        except Exception as e:
            logger.error(f"Failed to save memory for {format_name}: {e}")

    def add_lesson(self, lesson: Any):
        # Handle dict lessons from model
        lesson_text = str(lesson)
        if isinstance(lesson, dict):
            lesson_text = lesson.get('description', lesson.get('lesson', str(lesson)))
            
        if lesson_text not in self.lessons:
            self.lessons.append(lesson_text)
            # Cap lessons to the last 15 to prevent prompt bloat while allowing growth
            if len(self.lessons) > 15:
                self.lessons.pop(0)
            logger.info(f"Learned NEW lesson (total: {len(self.lessons)}): {lesson_text}")
            
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
