"""
FieldProof — FastAPI Dependency Injections & RBAC Guards

Provides reusable dependencies for database sessions, JWT token decoding,
current user extraction, and Role-Based Access Control (RBAC).
"""

from __future__ import annotations

from typing import Callable, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import TokenPayload
from app.services.auth_service import get_user_by_id

# OAuth2 scheme pointing to login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT token and return authenticated User record."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        role_str: str = payload.get("role")
        if user_id_str is None or role_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure user is both authenticated and currently active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def require_roles(*allowed_roles: UserRole | str) -> Callable[[User], User]:
    """
    Factory creating a dependency that enforces RBAC role restrictions.
    Raises HTTP 403 Forbidden if user's role is not within allowed_roles.
    """
    normalized_roles = {
        r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles
    }

    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        user_role_val = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        if user_role_val not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user_role_val}'. Required: {list(normalized_roles)}",
            )
        return current_user

    return role_checker


# Convenience role dependencies for route declarations
require_admin = require_roles(UserRole.ADMIN)
require_inspector = require_roles(UserRole.INSPECTOR)
require_inspector_or_admin = require_roles(UserRole.INSPECTOR, UserRole.ADMIN)
require_authenticated_user = get_current_active_user
