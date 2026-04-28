"""
Quick send — send a message to any channel by ID without switching to it.
Also includes qdel: send + auto-delete after N seconds.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def quicksend(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /qs <channel_id> <message...>")
    try:
        cid = int(args[0])
    except ValueError:
        raise ValueError("channel_id must be a number")
    text = " ".join(args[1:])

    ch = handler.session.get_channel(cid)
    if ch is None:
        try:
            ch = await handler.session.fetch_channel(cid)
        except discord.HTTPException as e:
            raise RuntimeError(f"channel fetch failed: {e}")

    if not hasattr(ch, "send"):
        raise RuntimeError("that channel doesn't support sending messages")

    try:
        await ch.send(text)
    except discord.HTTPException as e:
        raise RuntimeError(f"send failed: {e}")

    where = getattr(ch, "name", None) or str(ch)
    print(f"sent to #{where}")


async def qdel(handler: "CommandHandler", args: list[str]) -> None:
    """Send a message that auto-deletes after N seconds (default 5).
    Useful for sharing a token, password, or other transient info.

    CLI:
        /qdel <ch_id> <text...>                 # default 5s
        /qdel <ch_id> --seconds 10 <text...>    # custom delay
    """
    if len(args) < 2:
        raise ValueError("usage: /qdel <ch_id> [--seconds N] <message...>")

    cid = int(args[0])

    # Pull off optional --seconds N
    rest = list(args[1:])
    delay = 5
    if "--seconds" in rest:
        i = rest.index("--seconds")
        try:
            delay = int(rest[i + 1])
        except (IndexError, ValueError):
            raise ValueError("--seconds needs a number")
        del rest[i:i + 2]

    delay = max(1, min(delay, 300))  # 1s..5min sanity range

    text = " ".join(rest)
    if not text:
        raise ValueError("missing message")

    ch = handler.session.get_channel(cid)
    if ch is None:
        try:
            ch = await handler.session.fetch_channel(cid)
        except discord.HTTPException as e:
            raise RuntimeError(f"channel fetch failed: {e}")

    msg = await ch.send(text)
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except discord.HTTPException:
        # message already gone, channel deleted, etc. — nothing to do
        pass

