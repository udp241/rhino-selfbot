"""
Logging — rotating file + console.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: Path | str = "logs", level: int = logging.INFO) -> logging.Logger:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Rotating file (5MB x 5)
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "selfbot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)

    # Console at WARNING+ so the CLI stays readable
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.WARNING)

    # Replace existing handlers (avoid duplicates on reload)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(ch)

    # discord.py is chatty; pin it to WARNING in the file too
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)

    return logging.getLogger("rhino")
