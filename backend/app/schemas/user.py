"""
FieldProof — User & Auth Pydantic Schemas

Validates registration, login, token responses, and user profile payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user properties."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=150)
    role: UserRole = UserRole.FIELD_OFFICER
    badge_number: Optional[str] = None
    phone_number: Optional[str] = None


class UserCreate(UserBase):
    """Payload for user registration."""
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """Payload for JSON-based login."""
    username_or_email: str
    password: str


class UserResponse(UserBase):
    """User profile response without sensitive credentials."""
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT Bearer access token response."""
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: int
    username: str
    full_name: str


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str  # user id as string
    role: str
    exp: Optional[int] = None
