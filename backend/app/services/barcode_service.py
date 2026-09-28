"""
FieldProof — Server-side barcode reading.

The phone reads the barcode with ML Kit, which sometimes misses a small or
glossy one that is plainly in the photo. When a scan arrives without one,
the backend decodes it from the uploaded image with ZBar (pyzbar), so the
registry check and the Rule 9 scale still run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from pyzbar.pyzbar import ZBarSymbol, decode

# Retail symbologies with a fixed printed width, named as cv_service expects.
_FORMATS = {
    "EAN13": "ean13",
    "EAN8": "ean8",
    "UPCA": "upca",
    "UPCE": "upce",
}
_SYMBOLS = [ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.UPCE]


@dataclass
class DetectedBarcode:
    data: str
    format: str
    bbox: List[float]  # x, y, width, height in image pixels


def detect_barcode(image: Optional[np.ndarray]) -> Optional[DetectedBarcode]:
    """The widest retail barcode in the image, or None."""
    if image is None or image.size == 0:
        return None
    found = [r for r in decode(image, symbols=_SYMBOLS) if r.type in _FORMATS]
    if not found:
        return None
    best = max(found, key=lambda r: r.rect.width)
    left, top, width, height = best.rect
    return DetectedBarcode(
        data=best.data.decode("ascii", errors="ignore"),
        format=_FORMATS[best.type],
        bbox=[float(left), float(top), float(width), float(height)],
    )
