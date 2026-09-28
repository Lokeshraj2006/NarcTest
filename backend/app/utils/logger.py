"""
FieldProof — Structured Logging

Provides a pre-configured logger with consistent formatting across the app.
"""

from __future__ import annotations

import logging
import sys

from app.config import settings


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a consistent format and level from settings."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger
