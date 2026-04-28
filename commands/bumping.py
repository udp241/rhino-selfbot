"""
Disboard server bumping.

CLI:
    /bump <ch_id> [count]              -- modern: invokes Disboard's /bump slash command
    /autobump <ch_id> [count]          -- legacy: posts '!d bump' as text every 2 hours
    /stopautobump
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Optional

import discord

from utils.branding import error, success, info, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


_DISBOARD_ID = 302050872383242240

_autobump_task: Optional[asyncio.Task] = None


async def bump(handler: "CommandHandler", args: list[str]) -> None:
    """Invoke Disboard's /bump slash command in a channel."""
    if not args:
        raise ValueError("usage: /bump <ch_id> [count]")
    cid = int(args[0])
    count = int(args[1]) if len(args) > 1 else 1
    if count >= 100:
        raise ValueError("count too high")

    ch = handler.session.get_channel(cid) or await handler.session.fetch_channel(cid)
    g = getattr(ch, "guild", None)
    if g is None:
        raise RuntimeError("must be a guild text channel")

    # Make sure Disboard is in the guild
    try:
        await g.fetch_member(_DISBOARD_ID)
    except discord.NotFound:
        raise RuntimeError("Disboard isn't in that guild")

    cmds = await ch.application_commands()
    bump_cmd = next(
        (c for c in cmds if c.name == "bump" and c.application_id == _DISBOARD_ID),
        None,
    )
    if bump_cmd is None:
        raise RuntimeError("disboard /bump not available in that channel")

    info(f"bumping {g.name} x{count}")
    for i in range(count):
        try:
            await bump_cmd.__call__(channel=ch)
        except Exception as e:
            error(f"bump {i+1}/{count}: {e}")
        if i + 1 < count:
            # Disboard's cooldown is 2 hours; add jitter
            sleep_s = 7200 + random.randint(0, 200)
            info(f"  bumped {i+1}/{count}, sleeping {sleep_s}s")
            await asyncio.sleep(sleep_s)
    success(f"done, bumped {count} times")


async def autobump(handler: "CommandHandler", args: list[str]) -> None:
    """Old-style: posts the literal '!d bump' command every ~2 hours."""
    global _autobump_task
    if not args:
        raise ValueError("usage: /autobump <ch_id> [count]")
    if _autobump_task and not _autobump_task.done():
        info("already running. /stopautobump first")
        return

    cid = int(args[0])
    count = int(args[1]) if len(args) > 1 else 9999
    ch = handler.session.get_channel(cid) or await handler.session.fetch_channel(cid)

    async def _loop():
        for i in range(count):
            try:
                await ch.send("!d bump")
                info(f"autobump {i+1}/{count}")
            except discord.HTTPException as e:
                error(f"autobump {i+1}: {e}")
            await asyncio.sleep(7200 + random.randint(0, 200))

    _autobump_task = asyncio.create_task(_loop())
    success(f"autobump started in #{getattr(ch, 'name', cid)}")


async def stopautobump(handler: "CommandHandler", args: list[str]) -> None:
    global _autobump_task
    if _autobump_task:
        _autobump_task.cancel()
        _autobump_task = None
    success("autobump stopped")
