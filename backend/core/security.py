"""Security: JWT creation/decoding and FastAPI auth dependency callables."""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import secrets

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from core.config import JWT_SECRET
from db.session import db

security = HTTPBearer(auto_error=False)  # auto_error=False allows cookie-only auth
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token expiry times
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour for access tokens
REFRESH_TOKEN_EXPIRE_DAYS = 30    # 30 days for refresh tokens

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(payload: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived access token (default 1 hour)."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = dict(payload)
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token (30 days)."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_urlsafe(16)  # Unique token ID for revocation
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        # Validate token type
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail=f"Invalid token type. Expected {token_type}")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def decode_token_no_type_check(token: str) -> Dict[str, Any]:
    """Decode token without type checking (for backward compatibility)."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependency callables
# ---------------------------------------------------------------------------

def _extract_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Extract token from either Authorization header or HttpOnly cookie."""
    # First check Authorization header
    if credentials and credentials.credentials:
        return credentials.credentials
    # Then check HttpOnly cookie
    cookie_token = request.cookies.get("aa_access_token")
    if cookie_token:
        return cookie_token
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_token(token)
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    # Token version check — invalidates tokens issued before last password change
    jwt_version = payload.get("token_version", 0)
    db_version = user.get("token_version", 0)
    if jwt_version != db_version:
        raise HTTPException(status_code=401, detail="Session has expired. Please log in again.")
    # Set request-scoped audit context so all audit writes are auto-tagged with this user's tenant
    from services.audit_service import set_audit_tenant
    set_audit_tenant(user.get("tenant_id"))
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not (user.get("is_admin") or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_super_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


async def optional_get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated (via header or cookie), otherwise return None."""
    token = _extract_token(request, None)
    if not token:
        # Check Authorization header manually
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
        else:
            return None
    
    try:
        payload = decode_token(token)
        user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
        if user and user.get("is_active", True):
            from services.audit_service import set_audit_tenant
            set_audit_tenant(user.get("tenant_id"))
            return user
    except Exception:
        pass
    return None
