"""
FieldProof — Seed the 13 compliance rules into Postgres.

Storing the rule catalogue as data (rather than constants in compliance_rules.py)
lets the admin dashboard list them, toggle them, and tune thresholds
without a redeploy.

Idempotent: rules are matched on `rule_number` and updated in place, so
re-running after editing this file refreshes the catalogue without
creating duplicates or orphaning existing RuleCheck rows.

Usage (from Backend/):
    python -m app.scripts.seed_rules
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.database import SessionLocal
from app.models.rule import Rule, RuleCategory, RuleSeverity

# Statutory references follow the Legal Metrology (Packaged Commodities)
# Rules, 2011 unless stated otherwise, checked on 2026-09-26 against the
# consolidated text as amended up to 2017 (six had been cited wrongly).
LMPC = "Legal Metrology (Packaged Commodities) Rules, 2011"

RULES: List[Dict[str, Any]] = [
    {
        "rule_number": 1,
        "rule_code": "MANUFACTURER_DETAILS",
        "rule_name": "Manufacturer / packer / importer name and address",
        "description": (
            "Every package must declare the name and complete address of the "
            "manufacturer, packer, or importer responsible for the commodity."
        ),
        "statutory_reference": f"Rule 6(1)(a), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MAJOR,
        "requires_cv": False,
        "config": {"min_address_length": 10},
    },
    {
        "rule_number": 2,
        "rule_code": "COUNTRY_OF_ORIGIN",
        "rule_name": "Country of origin",
        "description": (
            "Imported packages must declare the country of origin, manufacture "
            "or assembly of the commodity."
        ),
        "statutory_reference": f"Rule 6(1)(aa), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MODERATE,
        "requires_cv": False,
        "config": {"required_for_imported_only": True},
    },
    {
        "rule_number": 3,
        "rule_code": "GENERIC_NAME",
        "rule_name": "Common or generic name of commodity",
        "description": (
            "The package must declare the common or generic name of the "
            "commodity contained in it."
        ),
        "statutory_reference": f"Rule 6(1)(b), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MAJOR,
        "requires_cv": False,
        "config": {"min_length": 3},
    },
    {
        "rule_number": 4,
        "rule_code": "NET_QUANTITY",
        "rule_name": "Net quantity declaration",
        "description": (
            "Net quantity must be declared in standard units of weight, "
            "measure, or number, using the correct unit symbols."
        ),
        "statutory_reference": f"Rule 6(1)(c), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.CRITICAL,
        "requires_cv": False,
        "config": {
            "valid_units": ["g", "kg", "mg", "ml", "l", "cm", "m", "N"],
        },
    },
    {
        "rule_number": 5,
        "rule_code": "MRP_DECLARATION",
        "rule_name": "Retail sale price (MRP)",
        "description": (
            "The maximum retail price must be declared as "
            "'MRP Rs. <amount> inclusive of all taxes'."
        ),
        "statutory_reference": f"Rule 6(1)(e), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.CRITICAL,
        "requires_cv": False,
        "config": {"require_inclusive_of_taxes_text": True},
    },
    {
        "rule_number": 6,
        "rule_code": "MFG_DATE",
        "rule_name": "Month and year of manufacture / packing",
        "description": (
            "The month and year in which the commodity was manufactured, "
            "pre-packed, or imported must be declared."
        ),
        "statutory_reference": f"Rule 6(1)(d), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MAJOR,
        "requires_cv": False,
        "config": {},
    },
    {
        "rule_number": 7,
        "rule_code": "EXPIRY_DATE",
        "rule_name": "Best before / use by date",
        "description": (
            "A commodity that may become unfit for consumption after a time "
            "must declare its 'best before' or 'use by' date."
        ),
        "statutory_reference": f"Rule 6(1)(da), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MAJOR,
        "requires_cv": False,
        "config": {"flag_if_expired": True},
    },
    {
        "rule_number": 8,
        "rule_code": "CONSUMER_CARE",
        "rule_name": "Consumer care contact details",
        "description": (
            "The package must carry the name, address, telephone number, and "
            "email of the person who can be contacted for consumer complaints."
        ),
        "statutory_reference": f"Rule 6(2), {LMPC}",
        "category": RuleCategory.DECLARATION,
        "default_severity": RuleSeverity.MODERATE,
        "requires_cv": False,
        "config": {"require_phone_or_email": True},
    },
    {
        "rule_number": 9,
        "rule_code": "FONT_SIZE",
        "rule_name": "Minimum font size of declarations",
        "description": (
            "Declarations must meet the minimum letter height prescribed for "
            "the package's principal display panel area."
        ),
        "statutory_reference": f"Rule 7(2) and Table I, {LMPC}",
        "category": RuleCategory.PRESENTATION,
        "default_severity": RuleSeverity.MODERATE,
        "requires_cv": True,
        "config": {"min_height_mm_default": 1.0, "reference": "EAN-13 barcode width 37.29mm"},
    },
    {
        "rule_number": 10,
        "rule_code": "READABILITY",
        "rule_name": "Legibility and contrast of declarations",
        "description": (
            "Declarations must be legible and prominent, and the numerals of "
            "the MRP and net quantity must contrast conspicuously with the "
            "background."
        ),
        "statutory_reference": f"Rule 9(1), {LMPC}",
        "category": RuleCategory.PRESENTATION,
        "default_severity": RuleSeverity.MODERATE,
        "requires_cv": True,
        "config": {"min_contrast_ratio": 4.5},
    },
    {
        "rule_number": 11,
        "rule_code": "PLACEMENT",
        "rule_name": "Placement on principal display panel",
        "description": (
            "Every mandatory declaration must appear on the principal display "
            "panel. Checked by how closely the declarations are grouped, a "
            "proxy for finding the panel."
        ),
        "statutory_reference": f"Rule 8(1), {LMPC}",
        "category": RuleCategory.PRESENTATION,
        "default_severity": RuleSeverity.MINOR,
        "requires_cv": True,
        "config": {},
    },
    {
        "rule_number": 12,
        "rule_code": "LMPC_REGISTRATION",
        "rule_name": "LMPC registration number",
        "description": (
            "Manufacturers, packers, and importers must be registered with the "
            "Director of Legal Metrology and declare the registration number."
        ),
        "statutory_reference": f"Rule 27, {LMPC}",
        "category": RuleCategory.STATUTORY,
        "default_severity": RuleSeverity.MAJOR,
        "requires_cv": False,
        "config": {"required_for": ["importer", "packer"]},
    },
    {
        "rule_number": 13,
        "rule_code": "GSTIN_FORMAT",
        "rule_name": "GSTIN format and checksum",
        "description": (
            "The printed GSTIN must be a structurally valid 15-character "
            "identifier with a correct Mod-36 checksum. Format and checksum "
            "only — this does NOT confirm live registration with the GST "
            "Council, which would require their API."
        ),
        "statutory_reference": "Rule 46, Central Goods and Services Tax Rules, 2017",
        "category": RuleCategory.STATUTORY,
        "default_severity": RuleSeverity.MINOR,
        "requires_cv": False,
        "config": {"live_registry_check": False},
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        inserted, updated = 0, 0
        for payload in RULES:
            config = payload.pop("config", {})
            existing = (
                db.query(Rule)
                .filter(Rule.rule_number == payload["rule_number"])
                .first()
            )
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                existing.config_json = json.dumps(config)
                updated += 1
            else:
                db.add(Rule(**payload, config_json=json.dumps(config)))
                inserted += 1
            payload["config"] = config  # restore so re-running in-process works
        db.commit()
        total = db.query(Rule).count()
        cv = db.query(Rule).filter(Rule.requires_cv.is_(True)).count()
        print(
            f"[seed_rules] inserted={inserted} updated={updated} "
            f"total={total} (cv_dependent={cv})"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
