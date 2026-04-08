"""
Authentication endpoints and middleware.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.middleware.auth import verify_token, get_current_user
from app.models.user import User
from pydantic import BaseModel
from config import settings

router = APIRouter()
security = HTTPBearer()


class TokenResponse(BaseModel):
    """Token verification response."""
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None


@router.get("/verify", response_model=TokenResponse)
async def verify_auth_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Verify JWT token from Supabase.
    
    **Frontend Endpoint**: `GET /api/v1/auth/verify`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Response**:
    ```json
    {
        "valid": true,
        "user_id": "uuid",
        "email": "user@example.com"
    }
    ```
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided"
        )
    
    try:
        token = credentials.credentials
        
        # Debug: Log token info (first/last 10 chars only for security)
        import logging
        logger = logging.getLogger(__name__)
        if settings.DEBUG:
            logger.debug(f"Verifying token: {token[:10]}...{token[-10:]}")
        
        payload = await verify_token(token)
        
        return TokenResponse(
            valid=True,
            user_id=payload.get("sub"),
            email=payload.get("email")
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    **Frontend Endpoint**: `GET /api/v1/auth/me`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Response**:
    ```json
    {
        "user_id": "uuid",
        "email": "user@example.com",
        "created_at": "2024-01-01T00:00:00Z"
    }
    ```
    """
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


