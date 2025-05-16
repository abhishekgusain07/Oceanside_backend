"""
Configuration settings for CrewAI.

This module provides access to CrewAI-specific settings from environment variables.
"""
import os
from typing import Optional, Literal

from app.core.config import settings


class CrewAISettings:
    """Settings for CrewAI operations."""
    
    def __init__(self):
        """Set API keys in environment."""
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        
        if settings.GEMINI_API_KEY:
            os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
    
    @property
    def OPENAI_API_KEY(self) -> str:
        """Get the OpenAI API key."""
        return settings.OPENAI_API_KEY or ""
    
    @property
    def GEMINI_API_KEY(self) -> str:
        """Get the Google API key."""
        return settings.GEMINI_API_KEY or ""
    
    @property
    def DEFAULT_LLM_PROVIDER(self) -> str:
        """Get the default LLM provider."""
        return settings.DEFAULT_LLM_PROVIDER
    
    @property
    def DEFAULT_LLM_MODEL(self) -> str:
        """Get the default LLM model."""
        return settings.DEFAULT_LLM_MODEL
    
    @property
    def DEFAULT_LLM_TEMPERATURE(self) -> float:
        """Get the default LLM temperature."""
        return settings.DEFAULT_LLM_TEMPERATURE


# Create a singleton instance
crewai_settings = CrewAISettings() 