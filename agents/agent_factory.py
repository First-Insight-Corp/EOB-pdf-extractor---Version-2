"""
Factory to create Extraction Agent (and optionally Auditor/Critic) based on .env EXTRACTION_AGENT.
"""

import logging
from typing import Optional

from config import config
from logs_config import get_extraction_logger

logger = get_extraction_logger()


def get_extraction_agent():
    """
    Returns the configured Extraction Agent (Gemini or Claude).
    """
    if config.EXTRACTION_AGENT == "claude":
        from agents.claude_extraction_agent import ClaudeExtractionAgent
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("EXTRACTION_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
        return ClaudeExtractionAgent(
            api_key=config.ANTHROPIC_API_KEY,
            model_name=config.CLAUDE_MODEL,
        )
    # default: gemini
    from agents.gemini_agent import MultiModelAgent
    if not config.GEMINI_API_KEY:
        raise ValueError("EXTRACTION_AGENT=gemini but GEMINI_API_KEY not set in .env")
    return MultiModelAgent(
        api_key=config.GEMINI_API_KEY,
        model_name=config.GEMINI_MODEL,
        openai_api_key=config.OPENAI_API_KEY or None,
    )


def get_auditor_agent():
    """Returns an Auditor agent based on config.AUDITOR_AGENT."""
    if config.AUDITOR_AGENT == "claude":
        from agents.auditor_agent import AuditorAgent
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("AUDITOR_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
        return AuditorAgent(
            use_model="claude",
            api_key=config.ANTHROPIC_API_KEY,
            model_name=config.CLAUDE_MODEL,
        )
    # default: gemini
    from agents.auditor_agent import AuditorAgent
    if not config.GEMINI_API_KEY:
        raise ValueError("AUDITOR_AGENT=gemini but GEMINI_API_KEY not set in .env")
    return AuditorAgent(
        use_model="gemini",
        api_key=config.GEMINI_API_KEY,
        model_name=config.GEMINI_MODEL,
    )


def get_critic_agent():
    """Returns a Critic agent based on config.CRITIC_AGENT."""
    if config.CRITIC_AGENT == "claude":
        from agents.critic_agent import CriticAgent
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("CRITIC_AGENT=claude but ANTHROPIC_API_KEY not set in .env")
        return CriticAgent(
            use_model="claude",
            api_key=config.ANTHROPIC_API_KEY,
            model_name=config.CLAUDE_MODEL,
        )
    # default: gemini
    from agents.critic_agent import CriticAgent
    if not config.GEMINI_API_KEY:
        raise ValueError("CRITIC_AGENT=gemini but GEMINI_API_KEY not set in .env")
    return CriticAgent(
        use_model="gemini",
        api_key=config.GEMINI_API_KEY,
        model_name=config.GEMINI_MODEL,
    )
