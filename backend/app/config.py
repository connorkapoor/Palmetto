"""
Configuration management for Palmetto backend.
Handles environment variables and application settings.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    app_name: str = "Palmetto CAD Feature Recognition"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # File Upload Settings
    max_upload_size: int = 104857600  # 100MB in bytes
    upload_dir: str = "temp/uploads"
    allowed_extensions: List[str] = [".step", ".stp", ".iges", ".igs", ".brep"]

    # Tessellation Settings (for B-Rep to mesh conversion)
    linear_deflection: float = 0.1  # Linear deflection for tessellation
    angular_deflection: float = 0.5  # Angular deflection in radians

    # Claude API Settings
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-5-20251101"
    claude_max_tokens: int = 1024

    # Storage Settings
    session_timeout: int = 3600  # 1 hour in seconds
    max_models_in_memory: int = 10  # Maximum number of models to keep in memory

    # Feature Recognition Settings
    default_confidence_threshold: float = 0.7  # Minimum confidence for feature recognition

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    This function is cached so settings are only loaded once.

    Returns:
        Settings: Application settings instance
    """
    return Settings()


# Convenience function for FastAPI dependency injection
def get_settings_dependency() -> Settings:
    """FastAPI dependency for injecting settings into route handlers."""
    return get_settings()
