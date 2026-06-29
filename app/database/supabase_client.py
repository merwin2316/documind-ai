"""
Database client — local SQLite only.
"""
from config import settings
import logging

logger = logging.getLogger(__name__)

_local_db = None


def get_local_db():
    """Get local SQLite database instance."""
    global _local_db
    if _local_db is None:
        from app.database.local_db import LocalDB
        _local_db = LocalDB()
        logger.info("Local SQLite database initialized")
    return _local_db


def is_local_mode() -> bool:
    """Always returns True — local-only mode."""
    return True
