"""
Logging structure pour FitMatch.
"""
import logging
import sys
import os

def setup_logging():
    """Configure le logging avec format structure."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("fitmatch")

log = None

def get_logger():
    global log
    if log is None:
        log = setup_logging()
    return log
