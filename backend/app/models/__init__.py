"""FieldProof — SQLAlchemy models registry."""

from __future__ import annotations

from app.models.kit_profile import KitProfile
from app.models.review import Review
from app.models.test_record import TestRecord
from app.models.user import User, UserRole

__all__ = ["User", "UserRole", "KitProfile", "TestRecord", "Review"]
