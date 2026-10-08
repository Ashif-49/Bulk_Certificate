from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or defaults."""
    
    DATABASE_URL: str = Field(default="sqlite:///./bulk_certs.db", description="Database connection URL")
    STORAGE_DIR: str = Field(default="storage", description="Base directory to store generated certificates")
    MAX_RECIPIENTS: int = Field(default=5000, description="Maximum number of recipients allowed per job")
    WORKER_THREADS: int = Field(default=4, description="Number of worker threads in ThreadPoolExecutor")
    MAX_CSV_SIZE_BYTES: int = Field(default=5 * 1024 * 1024, description="Max CSV upload file size in bytes (5MB)")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure base storage directory exists
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
