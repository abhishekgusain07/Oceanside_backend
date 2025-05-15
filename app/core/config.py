"""
Application configuration settings loaded from environment variables.
"""
import os
from pathlib import Path
from typing import List, Optional, Literal

from pydantic import field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application metadata
    PROJECT_NAME: str = "FastAPI Backend Template"
    PROJECT_DESCRIPTION: str = "A template FastAPI application with database integration"
    VERSION: str = "0.1.0"
    
    # API Documentation
    API_V1_STR: str = "/api"
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Environment settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Log settings
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False
    
    # Database settings
    DATABASE_URL: Optional[str] = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fastapi_template"
    DATABASE_ECHO: bool = False
    
    # CrewAI Settings
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "google"
    DEFAULT_LLM_MODEL: str = "gemini-1.5-flash"
    DEFAULT_LLM_TEMPERATURE: float = 0.7
    
    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Assemble database connection string from components or use DATABASE_URL if provided."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Test database - used for pytest
    TEST_POSTGRES_DB: str = "test_fastapi_template"
    
    @computed_field
    @property
    def TEST_SQLALCHEMY_DATABASE_URI(self) -> str:
        """Assemble test database connection string."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.TEST_POSTGRES_DB}"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        """Parse CORS origins from comma-separated string or use default list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


# Create a global settings instance
settings = Settings()