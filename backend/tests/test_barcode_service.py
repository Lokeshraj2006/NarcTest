"""Server-side barcode reading, on a real phone photo the app's ML Kit missed."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.services.barcode_service import detect_barcode

FIXTURES = Path(__file__).parent / "fixtures"


def test_reads_the_barcode_the_phone_missed():
    # Crop of scan #15: Haldiram's Aloo Bhujia Sev, where ML Kit found nothing.
    found = detect_barcode(cv2.imread(str(FIXTURES / "barcode" / "pack_a_back_barcode.png")))
    assert found is not None
    assert found.data == "8904004400779"
    assert found.format == "ean13"
    assert found.bbox[2] > 100


def test_photo_without_a_barcode_gives_none():
    fabric = cv2.imread(str(FIXTURES / "fssai" / "scan3_patterned_fabric.png"))
    assert detect_barcode(fabric) is None


def test_empty_image_gives_none():
    assert detect_barcode(np.zeros((0, 0, 3), dtype=np.uint8)) is None
    assert detect_barcode(None) is None
