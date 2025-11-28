"""
Application configuration loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from .env file."""
    
    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_DATABASE: str = "restaurant_db"
    DB_CHARSET: str = "utf8mb4"
    
    # OpenAI configuration
    OPEN_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Tag generation threshold
    TAG_THRESHOLD: float = 0.5
    
    # Recommendation minimum score threshold
    MIN_SCORE_THRESHOLD: float = 0.5
    
    # API configuration
    API_PREFIX: str = ""
    DEBUG: bool = False
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct MySQL database URL for SQLAlchemy."""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}?charset={self.DB_CHARSET}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
