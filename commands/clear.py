"""
Unified message cleaner — deletes your own messages from any channel.

Replaces the old `cleandm` and `selfpurge` split. One command, works in:
  - Guild text channels and threads
  - DMs (1-on-1)
  - Group DMs

CLI:
    /clear <ch_id_or_user_id>            -- delete all your msgs there
    /clear <id> 50                       -- delete last 50 of yours
    /clear <id> --limit 100
    /clear <id> --before <message_id>
    /clear <id> --dry-run

Prefix (in Discord):
    $clear                               -- this channel, all your msgs
    $clear 50                            -- this channel, last 50 of yours
    $clear --dry-run
    $clear <#otherchannel>               -- target a different channel

Resolution rules:
  - If <id> is a known channel (any type), use it.
  - Else, treat as user ID -> open/find DM with that user.

Same rate-limit-respecting delete loop as the old V2 versions.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


PER_DELETE_SLEEP = 1.1  # conservative; per-channel delete bucket


async def _resolve_target(client: discord.Client, target_id: int):
    """
    Try as channel id first (any type — text, DM, group, thread).
    Fall back to user id -> open/get DM channel.

    Returns a channel object with .history() and msg.delete()-able messages,
    or None if nothing resolved.
    """
    # 1. Channel cache
    ch = client.get_channel(target_id)
    if ch is not None:
        return ch

    # 2. Channel fetch (works for guild channels we can see, threads, etc.)
    try:
        ch = await client.fetch_channel(target_id)
        return ch
    except discord.NotFound:
        pass
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass

    # 3. Fall back: treat as user id, open/find DM
    try:
        user = await client.fetch_user(target_id)
    except (discord.NotFound, discord.HTTPException):
        return None

    if getattr(user, "dm_channel", None):
        return user.dm_channel
    try:
        return await user.create_dm()
    except discord.HTTPException:
        return None


def _parse_args(args: list[str]) -> dict:
    if not args:
        raise ValueError(
            "usage: /clear <ch_id_or_user_id> [N|--limit N] [--before MID] [--dry-run]"
        )

    out = {
        "target": int(args[0]),
        "before": None,
        "limit": None,
        "dry_run": False,
    }

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--before":
            out["before"] = int(args[i + 1])
            i += 2
        elif a == "--limit":
            out["limit"] = int(args[i + 1])
            i += 2
        elif a == "--dry-run":
            out["dry_run"] = True
            i += 1
        elif a.isdigit():
            # Bare integer = shorthand for --limit  (V2 'clear N' style)
            out["limit"] = int(a)
            i += 1
        else:
            raise ValueError(f"unknown flag: {a}")

    return out


async def clear(handler: "CommandHandler", args: list[str]) -> None:
    parsed = _parse_args(args)
    client = handler.session
    me_id = client.user.id

    channel = await _resolve_target(client, parsed["target"])
    if channel is None:
        raise RuntimeError(f"could not resolve channel/user for id {parsed['target']}")

    if not hasattr(channel, "history"):
        raise RuntimeError(f"channel type {type(channel).__name__} can't be cleared")

    # Pretty label for output
    if isinstance(channel, discord.DMChannel):
        recip = getattr(channel, "recipient", None)
        where = f"DM with {recip}" if recip else f"DM {channel.id}"
    elif isinstance(channel, discord.GroupChannel):
        where = f"group DM '{channel.name}'" if channel.name else f"group DM {channel.id}"
    elif hasattr(channel, "name"):
        where = f"#{channel.name}"
    else:
        where = str(channel.id)

    print(f"Cleaning your messages in {where}")
    if parsed["dry_run"]:
        print("[dry-run] no messages will actually be deleted")

    last_marker = discord.Object(id=parsed["before"]) if parsed["before"] else None
    limit_total = parsed["limit"]

    deleted = 0
    scanned = 0
    failed = 0

    try:
        while True:
            if limit_total is not None and deleted >= limit_total:
                break

            kwargs = {"limit": 100}
            if last_marker is not None:
                kwargs["before"] = last_marker

            batch: list[discord.Message] = []
            try:
                async for msg in channel.history(**kwargs):
                    batch.append(msg)
            except discord.HTTPException as e:
                print(f"history fetch failed: {e}")
                await asyncio.sleep(5)
                continue

            if not batch:
                break

            last_marker = batch[-1]  # oldest in batch -> next "before"

            for msg in batch:
                scanned += 1
                if msg.author.id != me_id:
                    continue
                if limit_total is not None and deleted >= limit_total:
                    break

                if parsed["dry_run"]:
                    preview = (msg.content or "")[:60]
                    print(f"  [dry-run] would delete {msg.id}: {preview!r}")
                    deleted += 1
                    continue

                try:
                    await msg.delete()
                    deleted += 1
                    if deleted % 10 == 0:
                        print(f"  ... deleted {deleted} so far")
                except discord.NotFound:
                    pass  # already gone
                except discord.Forbidden:
                    failed += 1
                except discord.HTTPException as e:
                    failed += 1
                    print(f"  delete {msg.id} failed: {e}")
                    await asyncio.sleep(2)

                await asyncio.sleep(PER_DELETE_SLEEP)

    except asyncio.CancelledError:
        print("Cancelled.")
        raise

    print("-" * 40)
    print(f"Scanned: {scanned}  |  Deleted: {deleted}  |  Failed: {failed}")
