"""
Application configuration management.
"""
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator
import secrets
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings.
    """
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FastAPI Template"
    PROJECT_DESCRIPTION: str = "A modern FastAPI template with best practices"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # CORS
    ALLOWED_ORIGINS: List[AnyHttpUrl] = []
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # API Documentation
    DOCS_URL: Optional[str] = "/docs"
    REDOC_URL: Optional[str] = "/redoc"
    OPENAPI_URL: Optional[str] = "/openapi.json"
    
    # Database
    DATABASE_URL: str = "sqlite:///./app.db"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Cache
    CACHE_TTL: int = 300  # 5 minutes
    
    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    def is_development(self) -> bool:
        """Check if the application is running in development mode."""
        return self.ENVIRONMENT.lower() == "development"
    
    def is_production(self) -> bool:
        """Check if the application is running in production mode."""
        return self.ENVIRONMENT.lower() == "production"
    
    def is_testing(self) -> bool:
        """Check if the application is running in testing mode."""
        return self.ENVIRONMENT.lower() == "testing"

@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings.
    
    Returns:
        Settings: Application settings
    """
    return Settings()

settings = get_settings()