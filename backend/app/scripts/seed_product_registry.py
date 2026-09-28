"""
FieldProof — Seed script for ProductRegistry.

Populates the registry the authenticity service looks up. The first five
rows are illustrative — their barcodes and licence numbers are invented. The
Aloo Bhujia row is transcribed from a real pack and is the demo product.
Idempotent: skips rows whose barcode already exists.

Usage (from Backend/):
    python -m app.scripts.seed_product_registry
"""

from __future__ import annotations

from typing import List

from app.database import SessionLocal
from app.models.product_registry import ProductRegistry

SEED_PRODUCTS: List[dict] = [
    {
        "barcode": "8901491101837",
        "product_name": "Maggi 2-Minute Masala Noodles",
        "manufacturer_name": "Nestle India Ltd.",
        "manufacturer_address": "Nestle House, Jacaranda Marg, M Block, DLF City Phase-II, Gurgaon 122002, Haryana",
        "mrp": 14.00,
        "net_quantity": "70 g",
        "fssai_license_number": "10012011000027",
        "gst_number": "06AAACN1160N1ZJ",
        "is_vegetarian": True,
    },
    {
        "barcode": "8901058000191",
        "product_name": "Amul Taaza Toned Milk",
        "manufacturer_name": "Gujarat Cooperative Milk Marketing Federation Ltd.",
        "manufacturer_address": "Amul Dairy Road, Anand 388001, Gujarat",
        "mrp": 27.00,
        "net_quantity": "500 ml",
        "fssai_license_number": "10012022000123",
        "gst_number": "24AAAAG0570A1ZJ",
        "is_vegetarian": True,
    },
    {
        "barcode": "8901063092105",
        "product_name": "Britannia Marie Gold Biscuits",
        "manufacturer_name": "Britannia Industries Ltd.",
        "manufacturer_address": "5/1A, Hungerford Street, Kolkata 700017, West Bengal",
        "mrp": 30.00,
        "net_quantity": "250 g",
        "fssai_license_number": "10014011000456",
        "gst_number": "19AABCB2984B1ZU",
        "is_vegetarian": True,
    },
    {
        "barcode": "8901030865278",
        "product_name": "Parachute Coconut Oil",
        "manufacturer_name": "Marico Limited",
        "manufacturer_address": "Grande Palladium, 175, CST Road, Kalina, Santacruz (East), Mumbai 400098, Maharashtra",
        "mrp": 105.00,
        "net_quantity": "200 ml",
        "fssai_license_number": "10012032000789",
        "gst_number": "27AAACM4507F1ZS",
        "is_vegetarian": True,
    },
    {
        "barcode": "8901719110018",
        "product_name": "Venky's Chicken Nuggets",
        "manufacturer_name": "Venky's (India) Limited",
        "manufacturer_address": "Venkateshwara House, S.No.114/A/2, Pune-Sinhagad Road, Pune 411030, Maharashtra",
        "mrp": 220.00,
        "net_quantity": "500 g",
        "fssai_license_number": "10015031000321",
        "gst_number": "27AAACV0554A1ZU",
        "is_vegetarian": False,
    },
    {
        # Transcribed from the back panel. The pack prints no GSTIN. It prints
        # two FSSAI licences: the "Lic. No." beside the FSSAI logo, and the
        # Nagpur unit's own under its MANUFACTURED BY address.
        "barcode": "8904004400779",
        "product_name": "Haldiram's Aloo Bhujia",
        "manufacturer_name": "Haldiram Snacks Food Private Limited",
        "manufacturer_address": "Unit-Hariomkar, 20 Km Stone, Kh. No. 409/3, 410, 411, Village Gumthala, Tah. Kamptee, Bhandara Road, Nagpur, Maharashtra 441104",
        "mrp": 109.00,
        "net_quantity": "400 g",
        "fssai_license_number": "10014011001919",
        "additional_fssai_license_numbers": "10015022004173",
        "gst_number": None,
        "is_vegetarian": True,
    },
    {
        # Transcribed from the tub's side label; batch and dates are printed on
        # the lid seal ("SEE SEAL"). Net quantity is declared as "200ml / 155g";
        # the volume comes first and is what the app reads. No GSTIN printed:
        # the "CPCB Regn. No." is a plastic-waste registration. The FSSAI logo's
        # licence is the marketer's; the manufacturing unit's is listed too.
        # The marketer's licence ends 476 (it was first typed as ...475; scan
        # #37's photo, enlarged, and scan #32's OCR both read 476).
        "barcode": "8906010913908",
        "product_name": "Ob & Gob Tiramisu & Fudge Ice Cream",
        "manufacturer_name": "Dairy Classic Ice Creams (P) Ltd.",
        "manufacturer_address": "(A) Plot No. 256, 256(P), 257, 258 & 265, KIADB - Harohalli Industrial Area, II Phase, Kanakapura Taluk, Ramanagara District 562112, Karnataka",
        "mrp": 250.00,
        "net_quantity": "200 ml",
        "fssai_license_number": "10012043000476",
        "additional_fssai_license_numbers": "10014043000791",
        "gst_number": None,
        "is_vegetarian": True,
    },
    {
        # Transcribed from the wrapper; barcode digits confirmed by the user
        # (EAN-13 check digit valid). MRP and dates are printed in a block
        # below the declarations ("Pkd.11/JUN/26", "Exp.11/JUN/27"). The
        # manufacturer is the Kaira union; GCMMF is the marketer, whose licence
        # sits beside the FSSAI logo. No GSTIN printed; no veg mark visible on
        # the photographed side, recorded as vegetarian (cocoa, milk solids).
        "barcode": "8901262070454",
        "product_name": "Amul Dark Chocolate",
        "manufacturer_name": "Kaira District Co-operative Milk Producers' Union Ltd.",
        "manufacturer_address": "Anand 388001, Gujarat; at Food Complex Mogar, Mogar 388340, Gujarat",
        "mrp": 45.00,
        "net_quantity": "35 g",
        "fssai_license_number": "10012021000071",
        "additional_fssai_license_numbers": "10014021001010",
        "gst_number": None,
        "is_vegetarian": True,
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        inserted, skipped = 0, 0
        for payload in SEED_PRODUCTS:
            existing = (
                db.query(ProductRegistry)
                .filter(ProductRegistry.barcode == payload["barcode"])
                .first()
            )
            if existing:
                skipped += 1
                continue
            db.add(ProductRegistry(**payload))
            inserted += 1
        db.commit()
        print(f"[seed_product_registry] inserted={inserted} skipped={skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
