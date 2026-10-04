# SPDX-License-Identifier: CC-BY-NC-4.0
"""Process-wide logging: stderr plus %APPDATA%/WindowsAutoclicker/autoclicker.log."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .app_data import app_data_dir

_LOG_NAME = "autoclicker"


def configure_logging() -> None:
    """Idempotent setup for the autoclicker logger tree."""
    logger = logging.getLogger(_LOG_NAME)
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    log_dir = app_data_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "autoclicker.log",
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass
