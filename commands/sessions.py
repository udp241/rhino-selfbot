"""
View active gateway sessions across devices.

CLI:
    /sessions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.branding import info, GREEN, GREY, WHITE, YELLOW, CYAN_DIM, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def sessions_cmd(handler: "CommandHandler", args: list[str]) -> None:
    client = handler.session
    sessions = list(getattr(client, "sessions", []))

    if not sessions:
        info("(no sessions found)")
        return

    info(f"Active sessions ({WHITE}{len(sessions)}{RESET}):")
    for s in sessions:
        # session_id, status, client_info{client, os, version}, active(bool)
        sid = getattr(s, "session_id", "?")
        status = getattr(s, "status", "?")
        active = getattr(s, "active", False)

        ci = getattr(s, "client_info", None) or {}
        if hasattr(ci, "client"):
            kind = getattr(ci, "client", "?")
            os_name = getattr(ci, "os", "?")
            version = getattr(ci, "version", "?")
        elif isinstance(ci, dict):
            kind = ci.get("client", "?")
            os_name = ci.get("os", "?")
            version = ci.get("version", "?")
        else:
            kind = os_name = version = "?"

        marker = f"{GREEN}*{RESET}" if active else " "
        print(f"  {marker}  {YELLOW}{kind}{RESET} on {WHITE}{os_name}{RESET} v{version}")
        print(f"     status: {status}    {GREY}sid: {sid}{RESET}")
