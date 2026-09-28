"""FieldProof — Kit profile endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    require_admin,
    require_supervisor_or_admin,
)
from app.database import get_db
from app.models.kit_profile import KitProfile
from app.models.user import User
from app.services.kit_service import kit_to_dict, with_lab

router = APIRouter(prefix="/kits", tags=["kits"])


class Outcome(BaseModel):
    label: str = Field(..., min_length=1)
    category: str = Field(..., pattern="^(POSITIVE|NEGATIVE|positive|negative)$")
    srgb: List[float] = Field(..., min_length=3, max_length=3)
    lab: Optional[List[float]] = None


class KitIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    reagent: Optional[str] = None
    read_time_s: int = Field(15, ge=0, le=3600)
    outcomes: List[Outcome] = Field(..., min_length=1)
    max_delta_e: float = Field(14, gt=0)
    min_margin: float = Field(4, ge=0)
    is_active: bool = True


class KitUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    reagent: Optional[str] = None
    read_time_s: Optional[int] = Field(None, ge=0, le=3600)
    outcomes: Optional[List[Outcome]] = None
    max_delta_e: Optional[float] = Field(None, gt=0)
    min_margin: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ActiveIn(BaseModel):
    is_active: bool


def _get(db: Session, kit_id: int) -> KitProfile:
    kit = db.get(KitProfile, kit_id)
    if kit is None:
        raise HTTPException(404, "Kit not found.")
    return kit


def _outcomes(items: List[Outcome]) -> list:
    # lab is always recomputed from srgb so the two can never disagree
    return with_lab([{**o.model_dump(), "lab": None} for o in items])


@router.get("")
def list_active(db: Session = Depends(get_db), _: User = Depends(get_current_active_user)):
    kits = db.query(KitProfile).filter(KitProfile.is_active.is_(True)).order_by(KitProfile.id).all()
    return [kit_to_dict(k) for k in kits]


@router.get("/all")
def list_all(db: Session = Depends(get_db), _: User = Depends(require_supervisor_or_admin)):
    return [kit_to_dict(k) for k in db.query(KitProfile).order_by(KitProfile.id).all()]


@router.post("", status_code=201)
def create_kit(body: KitIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(KitProfile).filter(KitProfile.code == body.code).first():
        raise HTTPException(400, "A kit with this code already exists.")
    data = body.model_dump()
    data["outcomes"] = _outcomes(body.outcomes)
    kit = KitProfile(**data, version=1)
    db.add(kit)
    db.commit()
    db.refresh(kit)
    return kit_to_dict(kit)


@router.put("/{kit_id}")
def update_kit(
    kit_id: int, body: KitUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    kit = _get(db, kit_id)
    data = body.model_dump(exclude_unset=True)
    if "outcomes" in data and body.outcomes is not None:
        data["outcomes"] = _outcomes(body.outcomes)
    if "code" in data and data["code"] != kit.code:
        if db.query(KitProfile).filter(KitProfile.code == data["code"]).first():
            raise HTTPException(400, "A kit with this code already exists.")
    for k, v in data.items():
        if v is not None:
            setattr(kit, k, v)
    kit.version = (kit.version or 1) + 1
    db.commit()
    db.refresh(kit)
    return kit_to_dict(kit)


@router.patch("/{kit_id}/active")
def set_active(
    kit_id: int, body: ActiveIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    kit = _get(db, kit_id)
    kit.is_active = body.is_active
    db.commit()
    db.refresh(kit)
    return kit_to_dict(kit)
