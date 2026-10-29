"""
Centralized logging configuration.
All modules use: from app.logger import logger
Zero print() statements in the codebase.
"""

import logging
import sys

from app.config import settings


def setup_logger(name: str = "trade_recorder") -> logging.Logger:
    """Configure and return the application logger."""
    log = logging.getLogger(name)
    log.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Avoid adding duplicate handlers on reload
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(module)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)

    return log


logger = setup_logger()
