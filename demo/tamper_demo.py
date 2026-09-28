"""
FieldProof - tamper demo helper (for the screen recording).

Changes ONE byte of a stored test photo so you can show that the verify page
turns red ("TAMPERED"), then puts the byte back so the record is genuine again.

Usage (from the SIH26231 folder):
    backend\\venv\\Scripts\\python.exe demo\\tamper_demo.py tamper 3     # break test #3
    backend\\venv\\Scripts\\python.exe demo\\tamper_demo.py restore 3    # fix test #3 again
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import os  # noqa: E402

os.chdir(BACKEND)  # so backend/.env is picked up

from app.database import SessionLocal  # noqa: E402
from app.models import TestRecord  # noqa: E402

BACKUP_SUFFIX = ".original-byte"


def image_path(test_id: int) -> Path:
    db = SessionLocal()
    try:
        rec = db.get(TestRecord, test_id)
        if rec is None:
            sys.exit(f"No test with id {test_id}")
        from app.config import settings

        p = Path(rec.image_path)
        return p if p.is_absolute() else (Path(settings.uploads_dir) / p)
    finally:
        db.close()


def tamper(test_id: int) -> None:
    p = image_path(test_id)
    data = bytearray(p.read_bytes())
    pos = len(data) // 2
    Path(str(p) + BACKUP_SUFFIX).write_text(f"{pos}:{data[pos]}")
    data[pos] = (data[pos] + 1) % 256
    p.write_bytes(bytes(data))
    print(f"Test #{test_id}: changed 1 byte of the photo. Open the verify page - it should say TAMPERED.")


def restore(test_id: int) -> None:
    p = image_path(test_id)
    b = Path(str(p) + BACKUP_SUFFIX)
    if not b.exists():
        sys.exit("Nothing to restore for this test.")
    pos, val = (int(x) for x in b.read_text().split(":"))
    data = bytearray(p.read_bytes())
    data[pos] = val
    p.write_bytes(bytes(data))
    b.unlink()
    print(f"Test #{test_id}: photo restored. The verify page should say genuine again.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("tamper", "restore"):
        sys.exit(__doc__)
    (tamper if sys.argv[1] == "tamper" else restore)(int(sys.argv[2]))
