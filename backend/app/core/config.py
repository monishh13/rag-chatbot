"""
Application configuration using Pydantic Settings.
Loads values from .env file with sensible defaults.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3"

    # ChromaDB Configuration
    chroma_db_path: str = "./chroma_db"
    chroma_collection_name: str = "sws_documents"

    # Embedding Model
    embedding_model: str = "all-MiniLM-L6-v2"

    # Chunking Configuration
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Retrieval Configuration
    top_k: int = 5
    similarity_threshold: float = 1.2

    # Documents Path
    docs_path: str = "./docs"

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/rag_chatbot.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
