"""
FieldProof — Auth Router

Provides user registration, token generation (login), and current profile endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_admin
from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Public sign-up, for consumers only.

    Inspector and admin accounts carry enforcement powers, so a stranger must
    not be able to give themselves one: the Controller creates them through
    ``POST /auth/users``, and the first admin comes from ``app.scripts.create_user``.
    """
    if user_in.role != UserRole.CONSUMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Public sign-up creates consumer accounts only. Inspector and admin "
                "accounts are created by an administrator."
            ),
        )
    return _create(user_in, db)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account of any role (admin only)",
)
def create_account(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """The Controller creates inspector and admin accounts."""
    return _create(user_in, db)


def _create(user_in: UserCreate, db: Session) -> User:
    if get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )
    if get_user_by_username(db, user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this username already exists.",
        )

    user = create_user(db, user_in)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login and obtain JWT access token",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with username/email and password to receive a JWT Bearer token."""
    user = authenticate_user(
        db,
        username_or_email=credentials.username_or_email,
        password=credentials.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token(subject=user.id, role=role_val)

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve authenticated user profile",
)
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    """Return the profile of the currently authenticated user."""
    return current_user
