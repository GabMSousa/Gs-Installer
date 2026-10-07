"""File and console logging with seven-day retention."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path


def configure_logging(log_dir: Path, level: str = "INFO", retention_days: int = 7) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now().timestamp() - timedelta(days=retention_days).total_seconds()
    for path in log_dir.glob("ninitetool_*.log"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    filename = log_dir / f"ninitetool_{datetime.now():%Y-%m-%d}.log"
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(filename, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )


__all__ = ["configure_logging"]
