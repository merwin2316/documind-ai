"""
Database client — Supabase or local SQLite based on configuration.
"""
from config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_supabase_client = None
_local_db = None


async def get_supabase_client():
    """
    Get Supabase client if configured.
    Returns None if Supabase is not configured (local mode).
    """
    global _supabase_client

    if not settings.use_supabase:
        return None

    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY,
        )
        logger.info("Supabase client initialized")

    return _supabase_client


def get_local_db():
    """Get local SQLite database instance (for demo/dev mode)."""
    global _local_db
    if _local_db is None:
        from app.database.local_db import LocalDB
        _local_db = LocalDB()
        logger.info("Local SQLite database initialized")
    return _local_db


def is_local_mode() -> bool:
    """Check if running in local/demo mode (no Supabase)."""
    return not settings.use_supabase
