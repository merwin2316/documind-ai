"""
Authentication middleware for DocuMind AI.
Validates Supabase Auth JWT access tokens securely and extracts verified user identity.
Supports asymmetric signing keys (RS256, ES256) via trusted JWKS,
legacy HMAC-SHA256 (HS256) via JWT Secret, and strict opt-in development authentication.
"""
import logging
import jwt
from typing import Optional, Dict
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import User
from config import settings

logger = logging.getLogger(__name__)

# Security scheme for FastAPI OpenAPI docs
security_scheme = HTTPBearer(auto_error=False)

# Fixed dev user constants (only used when explicitly opted-in)
DEV_USER_ID = "dev-user-00000000-0000-0000-0000-000000000000"
DEV_USER_EMAIL = "dev@documind.local"

# Strictly allowed signing algorithms
ALLOWED_ALGORITHMS = ("HS256", "RS256", "ES256")

# JWKS cache client
_jwks_client: Optional[jwt.PyJWKClient] = None


def _get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """Get or initialize cached JWKS client for RS256/ES256 verification."""
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def verify_jwt_token(token: str) -> Dict[str, Optional[str]]:
    """
    Verify a Supabase JWT access token.
    Enforces signature, algorithm, audience, expiration, issuer, and subject claims.
    Returns dict containing verified 'user_id' and 'email'.
    Raises HTTPException(401) on any verification failure.
    Never falls back to development user upon verification failure.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or empty",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Check explicit local dev opt-in fallback (strictly for standalone offline testing)
    if settings.ENVIRONMENT == "development" and settings.ALLOW_DEV_AUTH:
        if token in ("dev_token", "local", "dev"):
            logger.info("Using opt-in development authentication for local testing")
            return {"user_id": DEV_USER_ID, "email": DEV_USER_EMAIL}

    # 2. Inspect unverified header to determine and restrict algorithm
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        logger.warning(f"Malformed JWT header: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    alg = header.get("alg")
    if not alg or alg not in ALLOWED_ALGORITHMS:
        logger.warning(f"Rejected JWT with untrusted algorithm: '{alg}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported or untrusted signing algorithm: '{alg}'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_aud = settings.SUPABASE_JWT_AUDIENCE or "authenticated"
    expected_iss = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1" if settings.SUPABASE_URL else None

    decode_options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
    }
    kwargs = {
        "algorithms": [alg],
        "options": decode_options,
        "audience": expected_aud,
    }
    if expected_iss:
        decode_options["verify_iss"] = True
        kwargs["issuer"] = expected_iss

    # 3. Verify HS256 (HMAC with Supabase JWT Secret)
    if alg == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            logger.warning("HS256 token received but SUPABASE_JWT_SECRET is not configured")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Symmetric token verification is not configured on this server",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, **kwargs)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token audience is invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issuer is invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError as e:
            logger.warning(f"JWT HS256 error: {type(e).__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {type(e).__name__}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 4. Verify RS256 / ES256 (Asymmetric keys via trusted Supabase JWKS)
    elif alg in ("RS256", "ES256"):
        if not settings.SUPABASE_URL:
            logger.warning(f"{alg} token received but SUPABASE_URL is not configured for JWKS")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Asymmetric token verification requires SUPABASE_URL",
                headers={"WWW-Authenticate": "Bearer"},
            )

        jwks_client = _get_jwks_client(settings.SUPABASE_URL)
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(token, signing_key.key, **kwargs)
        except (jwt.PyJWKClientError, jwt.PyJWTError) as jwks_err:
            logger.warning(f"JWKS verification failed ({type(jwks_err).__name__}): {jwks_err}")
            if isinstance(jwks_err, jwt.ExpiredSignatureError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if isinstance(jwks_err, jwt.InvalidAudienceError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token audience is invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if isinstance(jwks_err, jwt.InvalidIssuerError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token issuer is invalid",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature or claims invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token algorithm",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 5. Validate subject claim (user identity)
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid subject (sub) claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"user_id": sub.strip(), "email": payload.get("email")}


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> User:
    """
    FastAPI dependency to authenticate and extract the current user.
    Extracts Bearer token, verifies claims, persists user record in SQLite,
    and returns a typed User instance. Never trusts user IDs from the client.
    """
    token: Optional[str] = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "Authorization" in request.headers:
        auth_header = request.headers["Authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        # Check if local dev auth is explicitly opted-in
        if settings.ENVIRONMENT == "development" and settings.ALLOW_DEV_AUTH:
            token = "dev_token"
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided",
                headers={"WWW-Authenticate": "Bearer"},
            )

    claims = verify_jwt_token(token)
    user_id = claims["user_id"]
    email = claims.get("email")

    # Ensure user record exists in local database for relational integrity
    from app.database.supabase_client import get_local_db
    db = get_local_db()
    db.upsert_user(user_id, email)

    return User(user_id=user_id, email=email)
