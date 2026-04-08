"""
Configuration management for the DocuMind AI backend.
Loads all settings from environment variables for security.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    
    # OpenAI Configuration
    OPENAI_API_KEY: str
    
    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    
    # Application Configuration
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    ADMIN_SECRET_KEY: str  # Required — must be set in .env
    FRONTEND_URL: Optional[str] = None
    
    # Database (PostgreSQL via Supabase)
    DATABASE_URL: str
    
    # OpenAI Model Configuration
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"  # 3072 dimensions
    
    # RAG Configuration
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 15
    CHUNK_METHOD: str = "token"
    SEMANTIC_SPLITTING: bool = True
    
    # Supabase Storage
    STORAGE_BUCKET: str = "documents"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
