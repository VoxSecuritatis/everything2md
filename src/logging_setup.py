# ================================================================
# logging_setup
# ================================================================
# Objective:
#       Configure a rolling daily log at logs/everything2md.log.
#       Call setup_logging() once at application startup.
#       Call log_result() after each conversion to write a
#       structured PASS/FAIL/WARN line.
# Inputs:
#       - ConversionResult dataclass
# Outputs:
#       - logs/everything2md.log (30-day retention)
# Notes:
#       - Uses TimedRotatingFileHandler at midnight.
#       - Format: timestamp | filename | PASS/FAIL/WARN | message
# ================================================================

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.config import LOGS_DIR
from src.schemas import ConversionResult

_LOG_FILE = LOGS_DIR / "everything2md.log"
_logger = logging.getLogger("everything2md")


def setup_logging() -> None:
    """Initialize the rolling log handler. Safe to call more than once."""
    if _logger.handlers:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        _LOG_FILE,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(handler)


def log_result(result: ConversionResult) -> None:
    """Write a structured log line for one conversion result."""
    label = "PASS" if result.status == "success" else "FAIL"
    fname = result.input_path.name
    stats = f"{result.duration_ms:.0f}ms"
    if result.table_count:
        stats += f", {result.table_count} table{'s' if result.table_count != 1 else ''}"
    if result.image_count:
        stats += f", {result.image_count} image{'s' if result.image_count != 1 else ''}"

    if result.status == "success":
        _logger.info("%s | %s | %s | converted in %s", label, fname, result.direction, stats)
    else:
        _logger.error("%s | %s | %s | %s", label, fname, result.direction, result.error)

    for w in result.warnings:
        _logger.warning("WARN | %s | %s", fname, w)
