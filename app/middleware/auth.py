"""
Authentication middleware for Supabase JWT verification.
"""
import jwt
import asyncio
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from app.database.supabase_client import get_supabase_client
from app.models.user import User
from config import settings

security = HTTPBearer(auto_error=False)


async def verify_token(token: str) -> Dict:
    """
    Verify Supabase JWT token using Supabase API endpoint.
    
    Uses Supabase API to verify tokens (supports both legacy HS256 and new ECC keys).
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    import httpx
    import logging
    logger = logging.getLogger(__name__)
    
    # Ensure Supabase URL is correctly formatted
    supabase_url = settings.SUPABASE_URL.rstrip('/').rstrip('/auth/v1').rstrip('/rest/v1')
    if not supabase_url.startswith('http'):
        supabase_url = f"https://{supabase_url}"
    
    auth_url = f"{supabase_url}/auth/v1/user"
    logger.info(f"Verifying token with Supabase API at: {auth_url}")
    
    # Use Supabase API to verify token (works with both HS256 and ECC keys)
    # Try Supabase Python client first (more reliable, handles timeouts better)
    try:
        from supabase import create_client
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        user_response = supabase_client.auth.get_user(token)
        if user_response and user_response.user:
            logger.info("Token verified successfully via Supabase Python client")
            return {
                "sub": user_response.user.id,
                "email": user_response.user.email,
                "role": getattr(user_response.user, 'role', 'authenticated') or "authenticated"
            }
    except Exception as client_error:
        logger.warning(f"Supabase Python client verification failed: {type(client_error).__name__}: {str(client_error)}")
        # Fall through to API call method
    
    # Fallback: Use direct API call with increased timeout and retry logic
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Retry logic: try up to 2 times
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await client.get(
                        auth_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "apikey": settings.SUPABASE_KEY,
                            "Content-Type": "application/json"
                        },
                        timeout=30.0  # Increased from 15 to 30 seconds
                    )
                    last_error = None
                    break  # Success, exit retry loop
                except httpx.TimeoutException as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Supabase API timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                    else:
                        raise
                except httpx.ConnectError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Supabase API connection error (attempt {attempt + 1}/{max_retries}), retrying...")
                        await asyncio.sleep(1)
                    else:
                        raise
            
            if last_error:
                raise last_error
            
            logger.debug(f"Supabase API response status: {response.status_code}")
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info("Token verified successfully via Supabase API")
                return {
                    "sub": user_data.get("id"),
                    "email": user_data.get("email"),
                    "role": user_data.get("role", "authenticated")
                }
            elif response.status_code == 401:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message") or error_data.get("error_description") or error_data.get("msg") or "Invalid or expired token"
                except:
                    error_msg = "Invalid or expired token"
                logger.warning(f"Supabase API returned 401: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_msg
                )
            elif response.status_code == 403:
                # 403 typically means invalid token or bad JWT (often "unrecognized JWT kid")
                try:
                    error_data = response.json()
                    error_msg = error_data.get("msg") or error_data.get("message") or "Token verification failed"
                    logger.error(f"Supabase API returned 403: {error_msg}")
                    # If it's a key ID issue, suggest checking token freshness
                    if "unrecognized JWT kid" in error_msg or "kid" in error_msg.lower():
                        error_msg = "Token verification failed: Invalid or expired token. Please log out and log in again to get a fresh token."
                except:
                    error_msg = "Token verification failed (403 Forbidden)"
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_msg
                )
            else:
                error_text = response.text[:500] if response.text else "No error message"
                logger.error(f"Supabase API returned status {response.status_code}: {error_text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token verification failed with status {response.status_code}: {error_text}"
                )
                    
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to Supabase at {auth_url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Supabase: {str(e)}"
        )
    except httpx.TimeoutException as e:
        logger.error(f"Supabase API timeout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase API timeout. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            ...
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = await verify_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get or create user in database
    supabase = await get_supabase_client()
    
    # Try to get user from database
    result = supabase.table("users").select("*").eq("user_id", user_id).execute()
    
    if result.data:
        user_data = result.data[0]
        return User(**user_data)
    
    # Create user if doesn't exist
    new_user = {
        "user_id": user_id,
        "email": payload.get("email"),
        "created_at": payload.get("iat")
    }
    
    supabase.table("users").insert(new_user).execute()
    return User(**new_user)

