"""
Snipe last-deleted message per channel.

Listens to on_message_delete events and stores the last deleted message
per channel. /snipe <ch_id> retrieves it.

CLI:
    /snipe <ch_id>
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import discord

from utils.branding import info, GREY, WHITE, YELLOW, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


# channel_id -> snipe entry
_sniped: dict[int, dict] = {}


def record_delete(message: discord.Message) -> None:
    """Called from main.py's on_message_delete listener."""
    try:
        author = getattr(message, "author", None)
        channel = getattr(message, "channel", None)
        if author is None or channel is None:
            return  # uncached delete with no payload
        try:
            if author.id == message._state.user.id:
                return  # skip our own deletes
        except Exception:
            pass
        _sniped[channel.id] = {
            "author":      str(author),
            "author_id":   author.id,
            "content":     message.content or "",
            "attachments": [a.url for a in (message.attachments or [])],
            "ts":          int(time.time()),
        }
    except Exception:
        # never let snipe crash the dispatcher
        return


async def snipe(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /snipe <ch_id>")
    cid = int(args[0])
    entry = _sniped.get(cid)
    if not entry:
        info("(nothing sniped)")
        return
    age = int(time.time()) - entry["ts"]
    print(f"  {YELLOW}sniped:{RESET} {WHITE}{entry['author']}{RESET}  "
          f"{GREY}({entry['author_id']}, {age}s ago){RESET}")
    if entry["content"]:
        print(f"  {entry['content']}")
    for a in entry["attachments"]:
        print(f"  {GREY}{a}{RESET}")
