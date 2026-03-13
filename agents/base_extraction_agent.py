"""
Base interface for PDF-to-JSON extraction agents.
Implementations: Gemini, Claude (Opus 4.6 / Sonnet 4).
Output structure is dynamic and driven by format modules (BatchModel, schema).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import logging
logger = logging.getLogger(__name__)


class BaseExtractionAgent(ABC):
    """
    Extraction Agent: extracts structured JSON from a PDF batch (text + optional images).
    Must return a dict compatible with format's BatchModel (e.g. claims + metadata).
    """

    @abstractmethod
    def extract_batch(
        self,
        document_type: str,
        batch_text: str,
        schema_description: str,
        batch_json_schema: str = "",
        response_json_schema: str = "",
        image_b64_list: Optional[List[str]] = None,
        is_continuation: bool = False,
        previous_context: str = "",
        improvement_instructions: Optional[str] = None,
        previous_batch_text: Optional[str] = None,
        previous_batch_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract one batch of pages into structured JSON.
        - improvement_instructions: re-extraction pass to fix Auditor/Critic issues.
        - previous_batch_text / previous_batch_json: context from the immediately prior batch
          for naming and structural consistency across batches.
        Returns dict with at least: claims or entities, metadata, has_incomplete_entity?, incomplete_entity_context?
        """
        pass

    def reset_memory(self) -> None:
        """Reset cross-batch state for a new document."""
        pass
    
    def load_memory(self, format_name: str) -> None:
        """Load persistent memory for a specific format."""
        pass
    
    def save_memory(self, format_name: str) -> None:
        """Save current memory to persistent storage for a specific format."""
        pass

    def get_learning_context(self) -> str:
        """Return context string to inject into prompts (lessons, active state). Override if needed."""
        return ""
