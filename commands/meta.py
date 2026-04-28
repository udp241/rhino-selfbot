"""
Bot meta: uptime, ping, cls.
"""

from __future__ import annotations

import datetime
import os
import platform
import sys
from typing import TYPE_CHECKING

from utils.branding import info, GREY, WHITE, RESET, banner

if TYPE_CHECKING:
    from .handler import CommandHandler


# Set in main.py at startup
START_TIME = datetime.datetime.now(datetime.timezone.utc)


async def uptime(handler: "CommandHandler", args: list[str]) -> None:
    delta = datetime.datetime.now(datetime.timezone.utc) - START_TIME
    s = int(delta.total_seconds())
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    info(f"uptime: {WHITE}{' '.join(parts)}{RESET}")


async def ping(handler: "CommandHandler", args: list[str]) -> None:
    latency_ms = handler.session.latency * 1000
    info(f"latency: {WHITE}{latency_ms:.0f}ms{RESET}")


async def cls(handler: "CommandHandler", args: list[str]) -> None:
    """Clear the local terminal screen."""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        # ANSI clear + reset cursor
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()
    print(banner())
