import hmac
import hashlib
import base64
import json
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, status, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = len(data) % 4
    if padding > 0:
        data += "=" * (4 - padding)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_admin_token(username: str) -> str:
    """
    Generates a cryptographically secure HMAC-SHA256 JWT-compatible token
    for the admin session without requiring external C-libraries.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    expires_at = now + (settings.ADMIN_SESSION_HOURS * 3600)
    
    payload = {
        "sub": username,
        "role": "admin",
        "iat": now,
        "exp": expires_at,
    }

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    
    signature = hmac.new(
        settings.ADMIN_JWT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256
    ).digest()
    sig_b64 = _b64_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_admin_token(token: str) -> Dict[str, Any]:
    """
    Verifies signature and expiration of an admin token.
    Raises HTTPException if invalid or expired.
    """
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        
        header_b64, payload_b64, sig_b64 = parts
        message = f"{header_b64}.{payload_b64}".encode("utf-8")
        
        expected_sig = hmac.new(
            settings.ADMIN_JWT_SECRET.encode("utf-8"),
            message,
            hashlib.sha256
        ).digest()
        
        provided_sig = _b64_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature"
            )

        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check expiration
        now = int(time.time())
        if payload.get("exp", 0) < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired. Please log in again."
            )
            
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


async def get_current_admin(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    authorization: Optional[str] = Header(None),
    token_query: Optional[str] = Query(None, alias="token"),
) -> Dict[str, Any]:
    """
    Dependency for protected admin routes. Checks Authorization header or token query param.
    """
    token_str = None
    if auth and auth.credentials:
        token_str = auth.credentials
    elif authorization and authorization.startswith("Bearer "):
        token_str = authorization[7:].strip()
    elif token_query:
        token_str = token_query.strip()

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return verify_admin_token(token_str)


def create_redirect_admin_token(username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    expires_at = now + (settings.REDIRECT_ADMIN_SESSION_HOURS * 3600)
    payload = {
        "sub": username,
        "role": "redirect_admin",
        "iat": now,
        "exp": expires_at,
    }
    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        settings.REDIRECT_ADMIN_JWT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    return f"{header_b64}.{payload_b64}.{_b64_encode(signature)}"


def verify_redirect_admin_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

        header_b64, payload_b64, sig_b64 = parts
        message = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(
            settings.REDIRECT_ADMIN_JWT_SECRET.encode("utf-8"),
            message,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_sig, _b64_decode(sig_b64)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
        if payload.get("role") != "redirect_admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token role")
        if payload.get("exp", 0) < int(time.time()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")


async def get_current_redirect_admin(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    authorization: Optional[str] = Header(None),
    token_query: Optional[str] = Query(None, alias="token"),
) -> Dict[str, Any]:
    token_str = None
    if auth and auth.credentials:
        token_str = auth.credentials
    elif authorization and authorization.startswith("Bearer "):
        token_str = authorization[7:].strip()
    elif token_query:
        token_str = token_query.strip()

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_redirect_admin_token(token_str)
