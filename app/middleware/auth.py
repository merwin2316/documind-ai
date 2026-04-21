"""
Authentication middleware.
- Supabase mode: JWT verification via Supabase API.
- Local mode: Dev user bypass (no auth required).
"""
import jwt
import asyncio
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from app.models.user import User
from config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# Fixed dev user for local/demo mode
DEV_USER_ID = "dev-user-00000000-0000-0000-0000-000000000000"
DEV_USER_EMAIL = "dev@documind.local"


async def verify_token(token: str) -> Dict:
    """
    Verify JWT token.
    - Supabase mode: verifies via Supabase Auth API.
    - Local mode: accepts any token, returns dev user.
    """
    if not settings.use_supabase:
        # Local mode — skip verification, return dev user
        return {"sub": DEV_USER_ID, "email": DEV_USER_EMAIL, "role": "authenticated"}

    # ---- Supabase verification ----
    import httpx

    supabase_url = settings.SUPABASE_URL.rstrip("/")
    auth_url = f"{supabase_url}/auth/v1/user"

    # Try Supabase Python client first
    try:
        from supabase import create_client
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        user_response = client.auth.get_user(token)
        if user_response and user_response.user:
            return {
                "sub": user_response.user.id,
                "email": user_response.user.email,
                "role": getattr(user_response.user, "role", "authenticated") or "authenticated",
            }
    except Exception as e:
        logger.warning(f"Supabase client verification failed: {type(e).__name__}: {e}")

    # Fallback: direct API call
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(2):
                try:
                    response = await client.get(
                        auth_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "apikey": settings.SUPABASE_KEY,
                        },
                        timeout=30.0,
                    )
                    break
                except (httpx.TimeoutException, httpx.ConnectError):
                    if attempt == 0:
                        await asyncio.sleep(1)
                    else:
                        raise

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "sub": user_data.get("id"),
                    "email": user_data.get("email"),
                    "role": user_data.get("role", "authenticated"),
                }
            elif response.status_code in (401, 403):
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            else:
                raise HTTPException(status_code=401, detail=f"Token verification failed ({response.status_code})")

    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Cannot connect to Supabase")
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Supabase API timeout")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    Dependency to get current authenticated user.
    In local mode (no Supabase), returns a dev user automatically.
    """
    from app.database.supabase_client import is_local_mode, get_local_db

    if is_local_mode():
        # Local mode — return dev user without requiring auth header
        db = get_local_db()
        db.upsert_user(DEV_USER_ID, DEV_USER_EMAIL)
        return User(user_id=DEV_USER_ID, email=DEV_USER_EMAIL)

    # Supabase mode — require Bearer token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = await verify_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Get or create user in database
    from app.database.supabase_client import get_supabase_client
    supabase = await get_supabase_client()

    result = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if result.data:
        return User(**result.data[0])

    # Create user
    new_user = {"user_id": user_id, "email": payload.get("email")}
    supabase.table("users").insert(new_user).execute()
    return User(**new_user)
