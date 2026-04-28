"""
Third-party account connections (Twitch, Steam, Spotify, GitHub, ...).

CLI:
    /connections list
    /connections refresh           -- fetch fresh from API
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, GREY, WHITE, YELLOW, GREEN, RED, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


def _print_conn(c) -> None:
    type_ = getattr(c, "type", "?")
    name = getattr(c, "name", "?")
    cid = getattr(c, "id", "?")
    verified = getattr(c, "verified", False)
    visible = getattr(c, "visible", True)
    revoked = getattr(c, "revoked", False)
    friend_sync = getattr(c, "friend_sync", False)
    show_activity = getattr(c, "show_activity", False)

    flags = []
    flags.append(f"{GREEN}verified{RESET}" if verified else f"{RED}unverified{RESET}")
    if revoked: flags.append(f"{RED}revoked{RESET}")
    if not visible: flags.append(f"{GREY}hidden{RESET}")
    if friend_sync: flags.append("friend-sync")
    if show_activity: flags.append("activity-on")

    print(f"  {YELLOW}{str(type_):>10}{RESET}  {WHITE}{name}{RESET}  "
          f"{GREY}({cid}){RESET}  {' '.join(flags)}")


async def connections_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /connections <list|refresh>")
    sub, *_ = args
    client = handler.session

    if sub == "list":
        conns = list(getattr(client, "connections", []))
        if not conns:
            info("(none cached, try 'connections refresh')")
            return
        info(f"Connections ({WHITE}{len(conns)}{RESET}):")
        for c in conns:
            _print_conn(c)
        return

    if sub == "refresh":
        if not hasattr(client, "fetch_connections"):
            raise RuntimeError("fetch_connections not available")
        try:
            conns = await client.fetch_connections()
        except discord.HTTPException as e:
            raise RuntimeError(f"fetch failed: {e}")
        info(f"Connections ({WHITE}{len(conns)}{RESET}):")
        for c in conns:
            _print_conn(c)
        return

    raise ValueError(f"unknown connections subcommand: {sub}")
