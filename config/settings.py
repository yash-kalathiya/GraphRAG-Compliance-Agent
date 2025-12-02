"""
Configuration management for GraphRAG Legal Auditor.

This module uses Pydantic Settings for type-safe configuration
with automatic environment variable loading and validation.

Environment variables can be set in:
- Shell environment
- .env file in project root
- .env.local for local overrides

Example:
    >>> from config.settings import settings
    >>> print(settings.NEO4J_URI)
    bolt://localhost:7687
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    All settings can be overridden via environment variables.
    The prefix is not used, so NEO4J_URI maps directly to NEO4J_URI env var.
    
    Attributes:
        NEO4J_URI: Neo4j connection URI (bolt:// or neo4j://).
        NEO4J_USER: Database username.
        NEO4J_PASSWORD: Database password.
        OPENAI_API_KEY: OpenAI API key for LLM calls.
        MODEL_NAME: LLM model to use for extraction.
        LANCEDB_URI: Path to LanceDB vector store.
        LOG_LEVEL: Logging verbosity level.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Neo4j Configuration
    NEO4J_URI: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI"
    )
    NEO4J_USER: str = Field(
        default="neo4j",
        description="Neo4j username"
    )
    NEO4J_PASSWORD: str = Field(
        default="password",
        description="Neo4j password"
    )
    
    # LLM Configuration
    OPENAI_API_KEY: str = Field(
        default="sk-placeholder",
        description="OpenAI API key"
    )
    MODEL_NAME: str = Field(
        default="gpt-4-turbo-preview",
        description="LLM model name"
    )
    
    # Vector Store
    LANCEDB_URI: str = Field(
        default="data/lancedb",
        description="Path to LanceDB storage"
    )
    
    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging verbosity"
    )
    
    @field_validator("NEO4J_URI")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        """Ensure Neo4j URI has valid scheme."""
        if not v.startswith(("bolt://", "neo4j://", "neo4j+s://")):
            raise ValueError(
                "NEO4J_URI must start with bolt://, neo4j://, or neo4j+s://"
            )
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.OPENAI_API_KEY != "sk-placeholder"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Singleton Settings instance.
    """
    return Settings()


# Global settings instance
settings = get_settings()
