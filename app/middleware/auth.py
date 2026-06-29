"""
Authentication middleware — Local mode only.
Always returns a fixed dev user for local standalone operation.
"""
import logging
from fastapi import Depends
from app.models.user import User

logger = logging.getLogger(__name__)

# Fixed dev user for local mode
DEV_USER_ID = "dev-user-00000000-0000-0000-0000-000000000000"
DEV_USER_EMAIL = "dev@documind.local"


async def get_current_user() -> User:
    """
    Dependency to get current user.
    Always returns the dev user for local standalone operation.
    """
    from app.database.supabase_client import get_local_db

    db = get_local_db()
    db.upsert_user(DEV_USER_ID, DEV_USER_EMAIL)
    return User(user_id=DEV_USER_ID, email=DEV_USER_EMAIL)
