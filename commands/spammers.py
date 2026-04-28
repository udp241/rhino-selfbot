"""
Spam-family commands and DM-side cleanup.

Anything that sends multiple messages or affects multiple channels at
once. Default-DM guards are in place where it matters.

CLI:
    /spam <ch_id> <count> <message...>           -- spam any channel (DM or guild)
    /dm <user_id> <message...>
    /dmall <message...>                          -- DMs only your FRIENDS
    /editall <ch_id> <text...>                   -- edit all your past msgs in a channel
    /closealldm
    /botclosedm                                  -- close DMs only with bots
    /groupleaver                                 -- leave all group DMs
    /kickallgc <group_dm_channel_id>             -- kick everyone from a group DM you own
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

from utils.branding import error, success, info, warn, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


# ---- spam -----------------------------------------------------------

async def spam(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 3:
        raise ValueError("usage: /spam <ch_id> <count> <message...>")
    cid = int(args[0])
    count = int(args[1])

    # Tolerate a stray --here so old muscle memory doesn't break anything;
    # it's a no-op now (spam works in any channel by default).
    rest = [a for a in args[2:] if a != "--here"]
    message = " ".join(rest)
    if not message:
        raise ValueError("missing message")

    ch = await _channel(handler.session, cid)

    info(f"spamming x{count} in {ch} (Ctrl+C to stop)")
    for i in range(count):
        try:
            await ch.send(message)
        except discord.HTTPException as e:
            error(f"send {i+1}/{count} failed: {e}")
            await asyncio.sleep(2)
        await asyncio.sleep(0.6)
    success(f"sent {count}")


# ---- dm -------------------------------------------------------------

async def dm(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /dm <user_id> <message...>")
    uid = int(args[0])
    msg = " ".join(args[1:])
    user = handler.session.get_user(uid) or await handler.session.fetch_user(uid)
    try:
        await user.send(msg)
    except discord.Forbidden:
        raise RuntimeError("can't DM that user (privacy settings or no shared server)")
    except discord.HTTPException as e:
        raise RuntimeError(f"dm failed: {e}")
    success(f"dm'd {user}")


# ---- dmall (friends only) ------------------------------------------

async def dmall(handler: "CommandHandler", args: list[str]) -> None:
    """DMs your friends list. NOT all guild members."""
    if not args:
        raise ValueError("usage: /dmall <message...>")
    msg = " ".join(args)
    friends = list(getattr(handler.session, "friends", []))
    if not friends:
        raise RuntimeError("no friends cached")

    info(f"dm'ing {WHITE}{len(friends)}{RESET} friends")
    sent = 0; failed = 0
    for rel in friends:
        try:
            await rel.user.send(msg)
            sent += 1
        except discord.HTTPException:
            failed += 1
        await asyncio.sleep(1.2)
    success(f"sent {sent}, failed {failed}")


# ---- editall --------------------------------------------------------

async def editall(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /editall <ch_id> <text...>")
    cid = int(args[0])
    text = " ".join(args[1:])
    ch = await _channel(handler.session, cid)
    me_id = handler.session.user.id
    edited = 0
    async for msg in ch.history(limit=None):
        if msg.author.id != me_id:
            continue
        try:
            await msg.edit(content=text)
            edited += 1
            if edited % 10 == 0:
                info(f"  ... {edited}")
        except discord.HTTPException:
            pass
        await asyncio.sleep(1.0)
    success(f"edited {edited} messages")


# ---- closedm / groupleaver -----------------------------------------

async def closedm(handler: "CommandHandler", args: list[str]) -> None:
    """Close DMs. By default closes all 1-on-1 DMs.
    Pass `bots` as an arg to close only DMs with bot users.

    CLI:
        /closedm           -- close every 1-on-1 DM
        /closedm bots      -- close only DMs with bots
    """
    bots_only = bool(args and args[0].lower() == "bots")
    closed = 0
    failed = 0
    for ch in list(handler.session.private_channels):
        if not isinstance(ch, discord.DMChannel):
            continue
        if bots_only and not (ch.recipient and ch.recipient.bot):
            continue
        try:
            await ch.close()
            closed += 1
        except discord.HTTPException:
            failed += 1
        await asyncio.sleep(0.6)
    label = "bot DMs only" if bots_only else "all DMs"
    info(f"closed {closed} ({label}), failed {failed}")


async def groupleaver(handler: "CommandHandler", args: list[str]) -> None:
    left = 0; failed = 0
    for ch in list(handler.session.private_channels):
        if isinstance(ch, discord.GroupChannel):
            try:
                await ch.leave()
                left += 1
            except discord.HTTPException:
                failed += 1
            await asyncio.sleep(0.8)
    info(f"left {left} group DMs, failed {failed}")


async def kickallgc(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /kickallgc <group_dm_channel_id>")
    cid = int(args[0])
    ch = handler.session.get_channel(cid)
    if not isinstance(ch, discord.GroupChannel):
        raise RuntimeError("not a group DM channel")
    if ch.owner_id != handler.session.user.id:
        raise RuntimeError("you don't own that group DM")
    kicked = 0
    for r in list(ch.recipients):
        try:
            await ch.remove_recipients(r)
            kicked += 1
        except discord.HTTPException:
            pass
        await asyncio.sleep(0.5)
    success(f"kicked {kicked} from {ch.name or cid}")
