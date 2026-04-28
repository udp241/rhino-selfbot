"""
Typing indicator. Useful for "I'm here, give me a sec" without
actually sending anything.

CLI:
    /typing <channel_id> [seconds]      -- typing for N seconds (default 10)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error

if TYPE_CHECKING:
    from .handler import CommandHandler


async def typing_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /typing <channel_id> [seconds]")
    cid = int(args[0])

    # Default 10s. Accept bare int OR legacy `--seconds N` for muscle memory.
    seconds = 10
    rest = args[1:]
    if rest:
        if rest[0] == "--seconds" and len(rest) > 1:
            seconds = int(rest[1])
        else:
            try:
                seconds = int(rest[0])
            except ValueError:
                pass
    seconds = max(1, min(seconds, 60))

    client = handler.session
    ch = client.get_channel(cid)
    if ch is None:
        try:
            ch = await client.fetch_channel(cid)
        except discord.HTTPException as e:
            raise RuntimeError(f"channel fetch failed: {e}")

    # Messageable.typing() returns an async context manager that
    # holds the typing indicator for as long as you're inside it.
    if not hasattr(ch, "typing"):
        raise RuntimeError("that channel doesn't support typing")

    info(f"typing for {seconds}s in #{getattr(ch, 'name', cid)}...")
    try:
        async with ch.typing():
            await asyncio.sleep(seconds)
    except discord.HTTPException as e:
        error(f"typing failed: {e}")
        return
    success("done")
