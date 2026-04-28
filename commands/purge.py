"""
Self-purge in guild channels. Deletes ONLY messages you authored in a
specific server text channel. Same rate-limit-respecting pattern as the
DM cleaner.

CLI:
    /selfpurge <channel_id> [--before <msg_id>] [--limit N] [--dry-run]
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def selfpurge(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError(
            "usage: /selfpurge <channel_id> [--before <msg_id>] [--limit N] [--dry-run]"
        )

    channel_id = int(args[0])
    before_id: Optional[int] = None
    limit_total: Optional[int] = None
    dry_run = False

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--before":
            before_id = int(args[i + 1]); i += 2
        elif a == "--limit":
            limit_total = int(args[i + 1]); i += 2
        elif a == "--dry-run":
            dry_run = True; i += 1
        elif a.isdigit():
            # Bare integer = shorthand for --limit  (V2 'clear N' style)
            limit_total = int(a); i += 1
        else:
            raise ValueError(f"unknown flag: {a}")

    client = handler.session
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.HTTPException as e:
            raise RuntimeError(f"channel fetch failed: {e}")

    me_id = client.user.id
    last_marker = discord.Object(id=before_id) if before_id else None

    deleted = 0
    scanned = 0
    failed = 0
    PER_DELETE_SLEEP = 1.1

    where = f"#{channel.name}" if hasattr(channel, "name") else str(channel_id)
    print(f"Purging your messages in {where}")
    if dry_run:
        print("[dry-run] no messages will actually be deleted")

    while True:
        if limit_total is not None and deleted >= limit_total:
            break
        kwargs = {"limit": 100}
        if last_marker is not None:
            kwargs["before"] = last_marker

        batch: list[discord.Message] = []
        try:
            async for m in channel.history(**kwargs):
                batch.append(m)
        except discord.HTTPException as e:
            print(f"history fetch failed: {e}")
            await asyncio.sleep(5)
            continue

        if not batch:
            break
        last_marker = batch[-1]

        for msg in batch:
            scanned += 1
            if msg.author.id != me_id:
                continue
            if limit_total is not None and deleted >= limit_total:
                break
            if dry_run:
                print(f"  [dry-run] would delete {msg.id}: {msg.content[:60]!r}")
                deleted += 1
                continue
            try:
                await msg.delete()
                deleted += 1
                if deleted % 10 == 0:
                    print(f"  ... deleted {deleted}")
            except discord.NotFound:
                pass
            except discord.Forbidden:
                failed += 1
            except discord.HTTPException as e:
                failed += 1
                print(f"  delete {msg.id} failed: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(PER_DELETE_SLEEP)

    print("-" * 40)
    print(f"Scanned: {scanned}  |  Deleted: {deleted}  |  Failed: {failed}")
