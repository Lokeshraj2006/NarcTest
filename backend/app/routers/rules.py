"""
FieldProof — Rule catalogue router.

    GET   /rules            list the 13 seeded compliance rules
    PATCH /rules/{id}       admin toggles a rule or tunes its thresholds

Exposing the catalogue lets the dashboard show exactly which statutory
provision each check enforces, and lets the Controller disable a rule (for
an exempt commodity class) without a redeploy.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_authenticated_user
from app.database import get_db
from app.models.rule import Rule, RuleCategory, RuleSeverity
from app.models.user import User

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleOut(BaseModel):
    id: int
    rule_number: int
    rule_code: str
    rule_name: str
    description: str
    statutory_reference: str
    category: str
    default_severity: str
    requires_cv: bool
    is_active: bool
    config: Dict[str, Any] = Field(default_factory=dict)


class RuleListResponse(BaseModel):
    total: int
    active: int
    cv_dependent: int
    rules: List[RuleOut]


class RuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    default_severity: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


def _serialize(rule: Rule) -> RuleOut:
    try:
        config = json.loads(rule.config_json) if rule.config_json else {}
    except (ValueError, TypeError):
        config = {}
    return RuleOut(
        id=rule.id,
        rule_number=rule.rule_number,
        rule_code=rule.rule_code,
        rule_name=rule.rule_name,
        description=rule.description,
        statutory_reference=rule.statutory_reference,
        category=rule.category.value
        if isinstance(rule.category, RuleCategory)
        else str(rule.category),
        default_severity=rule.default_severity.value
        if isinstance(rule.default_severity, RuleSeverity)
        else str(rule.default_severity),
        requires_cv=rule.requires_cv,
        is_active=rule.is_active,
        config=config if isinstance(config, dict) else {},
    )


@router.get(
    "",
    response_model=RuleListResponse,
    summary="List the 13 Legal Metrology compliance rules",
)
def list_rules(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_authenticated_user),
) -> RuleListResponse:
    query = db.query(Rule).order_by(Rule.rule_number.asc())
    if active_only:
        query = query.filter(Rule.is_active.is_(True))
    rules = query.all()
    return RuleListResponse(
        total=len(rules),
        active=sum(1 for r in rules if r.is_active),
        cv_dependent=sum(1 for r in rules if r.requires_cv),
        rules=[_serialize(r) for r in rules],
    )


@router.patch(
    "/{rule_id}",
    response_model=RuleOut,
    summary="Toggle a rule or tune its thresholds (admin only)",
)
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RuleOut:
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule #{rule_id} not found."
        )

    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.default_severity is not None:
        try:
            rule.default_severity = RuleSeverity(payload.default_severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unknown severity '{payload.default_severity}'. Valid: "
                    f"{[s.value for s in RuleSeverity]}"
                ),
            )
    if payload.config is not None:
        rule.config_json = json.dumps(payload.config)

    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _serialize(rule)
