"""
Configuration management for DocuMind AI.
Environment-driven, modular, and demo-friendly.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # -----------------------------
    # Vector DB (Required for RAG)
    # -----------------------------
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # -----------------------------
    # Application
    # -----------------------------
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    ADMIN_SECRET_KEY: str = "dev_secret"   # fallback for local
    FRONTEND_URL: Optional[str] = None

    # -----------------------------
    # Authentication & Supabase
    # -----------------------------
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_JWT_ALGORITHM: str = "HS256"
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    ALLOW_DEV_AUTH: bool = False           # Strict: explicit opt-in for local dev testing
    ENABLE_RESET_ENDPOINT: bool = False    # Strict: destructive /reset disabled by default

    # -----------------------------
    # Database (SQLite — no setup needed)
    # -----------------------------
    DATABASE_URL: str = "sqlite:///./documind.db"

    # -----------------------------
    # LLM Provider
    # -----------------------------
    MODEL_PROVIDER: str = "ollama"  # "ollama" | "groq"

    # Ollama (local, default)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # Groq (optional)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # -----------------------------
    # RAG Configuration
    # -----------------------------
    CHUNK_SIZE: int = 350
    CHUNK_OVERLAP: int = 60
    TOP_K_RETRIEVAL: int = 2
    CHUNK_METHOD: str = "token"
    SEMANTIC_SPLITTING: bool = True

    # -----------------------------
    # Storage
    # -----------------------------
    STORAGE_BUCKET: str = "documents"
    LOCAL_STORAGE_PATH: str = "./storage"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
