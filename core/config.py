"""
Application configuration loaded from environment variables.
Uses pydantic-settings with python-dotenv for .env file loading.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    Priority (highest to lowest):
    1. Environment variables
    2. .env file
    3. Default values
    """
    
    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_DATABASE: str = "restaurant_db"
    DB_CHARSET: str = "utf8mb4"
    
    # OpenAI configuration
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Search Engine configuration
    SEARCH_DATA_DIR: str = "data"
    SEARCH_TOP_K_BM25: int = 60
    SEARCH_TOP_K_E5: int = 60
    SEARCH_W_BM25: float = 0.1
    SEARCH_W_E5: float = 0.9
    SEARCH_W_H: float = 1.0
    SEARCH_W_T: float = 0.3
    SEARCH_W_TYPE: float = 0.5
    SEARCH_W_CE: float = 2.0
    SEARCH_TOP_N: int = 20
    SEARCH_TRANSLATE_TOP_N: int = 10
    
    # Tag generation threshold
    TAG_THRESHOLD: float = 0.5
    
    # Recommendation minimum score threshold
    MIN_SCORE_THRESHOLD: float = 0.5
    
    # User preference scale (DB stores 0~MAX)
    USER_PREF_MAX: float = 5.0
    
    # API configuration
    API_PREFIX: str = ""
    DEBUG: bool = False
    
    # Server configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct MySQL database URL for SQLAlchemy."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
            f"?charset={self.DB_CHARSET}"
        )
    
    def validate_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.startswith("sk-"))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields in .env
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Global settings instance for easy import
settings = get_settings()
