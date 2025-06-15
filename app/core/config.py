"""
Application configuration management.
"""
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator, computed_field, Field
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


    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Base URL of the Next.js frontend application"
    )
    
    # WebSocket URL for signaling
    WEBSOCKET_URL: str = Field(
        default="ws://localhost:8000",
        description="Base WebSocket URL for signaling server"
    )
    
    # Session configuration
    MAX_SESSION_PARTICIPANTS: int = Field(
        default=10,
        description="Default maximum participants per session"
    )
    
    # Recording configuration
    RECORDING_CHUNK_DURATION_SECONDS: int = Field(
        default=30,
        description="Duration of each recording chunk in seconds"
    )
    
    # Cloud storage settings (you'll need these for the upload URLs)
    CLOUD_STORAGE_PROVIDER: str = Field(
        default="s3",
        description="Cloud storage provider (s3, gcs, etc.)"
    )
    
    CLOUD_STORAGE_BUCKET: str = Field(
        default="your-recordings-bucket",
        description="Cloud storage bucket name"
    )
    
    CLOUD_STORAGE_REGION: str = Field(
        default="us-east-1",
        description="Cloud storage region"
    )
    
    # AWS S3 credentials (if using S3)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        description="AWS access key ID"
    )
    
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None,
        description="AWS secret access key"
    )
    
    # Upload URL expiration
    UPLOAD_URL_EXPIRATION_MINUTES: int = Field(
        default=60,
        description="How long upload URLs remain valid (in minutes)"
    )
    
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
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fastapi_template"
    DATABASE_ECHO: bool = False
    
    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get the SQLAlchemy database URI."""
        if self.DATABASE_URL and self.DATABASE_URL != "sqlite:///./app.db":
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @computed_field
    @property
    def TEST_SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get the test database URI."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}_test"
    
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