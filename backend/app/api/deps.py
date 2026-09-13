"""
Authentication dependencies for FastAPI endpoints.
Validates session tokens and provides current user context.
"""
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
from backend.app.core.security import verify_session_token
from backend.app.core.db_repository import db_repository


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Requires a valid Bearer session token.
    Raises 401 Unauthorized if missing, malformed, expired, or user not found.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]
    claims = verify_session_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db_repository.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Returns the user if a valid Bearer token is provided.
    Returns None if no token or an invalid token is provided without failing the request.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    claims = verify_session_token(token)
    if not claims:
        return None
    user_id = claims.get("sub")
    if not user_id:
        return None
    return db_repository.get_user_by_id(user_id)
