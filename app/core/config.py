from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Project metadata
    PROJECT_NAME: str = "Patshal.ai"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Patshal.ai API"

    # API configuration
    API_V1_STR: str = "/api/v1"

    # CORS settings
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Environment
    DEBUG: bool = False

    # Groq
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # OpenRouter
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-70b-versatile"

    # Default platform
    DEFAULT_LLM_PLATFORM: str = "groq"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
