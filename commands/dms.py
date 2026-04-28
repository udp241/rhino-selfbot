"""
DM cleaner — deletes your own messages from a DM channel.

Properly respects Discord's rate limits. discord.py-self handles 429s
internally with retry-after; we add a small inter-request sleep so the
bucket doesn't get hammered.

Usage from CLI:
    /cleandm <user_id_or_channel_id>
    /cleandm <user_id_or_channel_id> --before <message_id>
    /cleandm <user_id_or_channel_id> --limit 500
    /cleandm <user_id_or_channel_id> --dry-run
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def _resolve_dm_channel(client: discord.Client, target_id: int) -> Optional[discord.DMChannel]:
    """Accept either a user ID (open/find DM) or a DM channel ID."""
    # Try interpreting as channel ID first
    ch = client.get_channel(target_id)
    if isinstance(ch, discord.DMChannel):
        return ch

    # Try as a user ID -> open DM
    try:
        user = await client.fetch_user(target_id)
    except discord.NotFound:
        return None
    except discord.HTTPException:
        return None

    if user.dm_channel:
        return user.dm_channel
    try:
        return await user.create_dm()
    except discord.HTTPException:
        return None


def _parse_args(args: list[str]) -> dict:
    out = {"target": None, "before": None, "limit": None, "dry_run": False}
    if not args:
        raise ValueError("missing target id")
    out["target"] = int(args[0])
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--before":
            i += 1
            out["before"] = int(args[i])
        elif a == "--limit":
            i += 1
            out["limit"] = int(args[i])
        elif a == "--dry-run":
            out["dry_run"] = True
        else:
            raise ValueError(f"unknown flag: {a}")
        i += 1
    return out


async def clean_dm(handler: "CommandHandler", args: list[str]) -> None:
    parsed = _parse_args(args)
    client = handler.session
    me_id = client.user.id

    channel = await _resolve_dm_channel(client, parsed["target"])
    if channel is None:
        raise RuntimeError(f"could not resolve DM channel for id {parsed['target']}")

    other = channel.recipient if hasattr(channel, "recipient") else "(unknown)"
    print(f"Cleaning your messages in DM with: {other}")
    if parsed["dry_run"]:
        print("[dry-run] no messages will actually be deleted")

    before = discord.Object(id=parsed["before"]) if parsed["before"] else None
    limit_total = parsed["limit"]

    deleted = 0
    scanned = 0
    failed = 0
    last_id = before

    # discord.py-self honors 429s automatically; the inter-call sleep keeps
    # us comfortably under the per-channel delete bucket.
    PER_DELETE_SLEEP = 1.1  # seconds. Conservative; tune if you want.

    try:
        while True:
            if limit_total is not None and deleted >= limit_total:
                break

            # Pull a page of history
            batch: list[discord.Message] = []
            kwargs = {"limit": 100}
            if last_id is not None:
                kwargs["before"] = last_id
            try:
                async for msg in channel.history(**kwargs):
                    batch.append(msg)
            except discord.HTTPException as e:
                print(f"history fetch failed: {e}")
                await asyncio.sleep(5)
                continue

            if not batch:
                break

            last_id = batch[-1]  # oldest in this batch -> next "before"

            for msg in batch:
                scanned += 1
                if msg.author.id != me_id:
                    continue
                if limit_total is not None and deleted >= limit_total:
                    break

                if parsed["dry_run"]:
                    print(f"  [dry-run] would delete {msg.id}: {msg.content[:60]!r}")
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
                    # discord.py-self will already have honored Retry-After
                    # for proper 429s. Anything else, log and continue.
                    failed += 1
                    print(f"  delete {msg.id} failed: {e}")
                    await asyncio.sleep(2)

                await asyncio.sleep(PER_DELETE_SLEEP)

    except asyncio.CancelledError:
        print("Cancelled.")
        raise

    print("-" * 40)
    print(f"Scanned: {scanned}  |  Deleted: {deleted}  |  Failed: {failed}")
