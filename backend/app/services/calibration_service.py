"""
FieldProof — Calibration Service

Barcode detection → mm scale factor computation.
Uses GS1 EAN-13 reference (37.29 mm at 100% magnification) to convert
pixel measurements to real-world millimetres.

This is a plain-Python service with zero FastAPI dependency (pytest-testable).
Implementation: Deliverable 5.
"""

from __future__ import annotations
