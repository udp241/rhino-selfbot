"""
Friend/blocked list export and mark-all-read.
Uses the documented client properties and bulk_ack().
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"


async def relationships_cmd(handler: "CommandHandler", args: list[str]) -> None:
    # Tolerate legacy `relationships export` for muscle memory; the export
    # is the only thing this command does, so the subcommand is noise.
    if args and args[0] == "export":
        args = args[1:]

    client = handler.session

    friends_list = []
    blocked_list = []
    incoming_list = []
    outgoing_list = []

    # Friends (RelationshipType.friend = 1)
    for r in getattr(client, "friends", []):
        u = r.user
        friends_list.append({"id": u.id, "name": str(u)})

    # Blocked (RelationshipType.blocked = 2)
    for r in getattr(client, "blocked", []):
        u = r.user
        blocked_list.append({"id": u.id, "name": str(u)})

    # Pending requests come from the full relationships list
    for r in getattr(client, "relationships", []):
        try:
            t_val = getattr(r.type, "value", r.type)
        except AttributeError:
            continue
        u = r.user
        entry = {"id": u.id, "name": str(u)}
        if t_val == 3:
            incoming_list.append(entry)
        elif t_val == 4:
            outgoing_list.append(entry)

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPORTS_DIR / f"relationships_{int(time.time())}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": int(time.time()),
                "friends": friends_list,
                "blocked": blocked_list,
                "incoming_requests": incoming_list,
                "outgoing_requests": outgoing_list,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    info(f"friends: {WHITE}{len(friends_list)}{RESET}  "
         f"blocked: {WHITE}{len(blocked_list)}{RESET}  "
         f"incoming: {WHITE}{len(incoming_list)}{RESET}  "
         f"outgoing: {WHITE}{len(outgoing_list)}{RESET}")
    success(f"saved: {out}")


async def readall_cmd(handler: "CommandHandler", args: list[str]) -> None:
    """Mark every guild + DM as read.

    Sequenced with a small inter-call sleep so we don't burn through the
    global 50-req/sec budget when you're in dozens of servers. On a 429
    we honor the Retry-After and try the same target once more before
    giving up.
    """
    import asyncio
    client = handler.session

    guilds = list(client.guilds)
    dms = [ch for ch in client.private_channels if hasattr(ch, "ack")]
    info(f"marking {WHITE}{len(guilds)}{RESET} guilds and "
         f"{WHITE}{len(dms)}{RESET} DMs as read...")

    PER_ACK_SLEEP = 0.6   # comfortable margin under 50 req/s global cap
    marked = 0
    failed = 0

    async def _ack(target, label: str) -> bool:
        """One ack with one rate-limit-aware retry. True on success."""
        for attempt in (1, 2):
            try:
                await target.ack()
                return True
            except discord.RateLimited as e:
                # discord.py-self raises RateLimited rather than auto-sleeping
                # if the per-route retry_after is large enough. Honor it.
                wait = float(getattr(e, "retry_after", 1.0)) + 0.25
                if attempt == 1:
                    await asyncio.sleep(wait)
                    continue
                error(f"  {label}: rate-limited (retry-after {wait:.1f}s)")
                return False
            except discord.HTTPException as e:
                # 403 (no perms), 404 (gone), 5xx (transient server) etc.
                # Retry once on 5xx, give up on 4xx.
                status = getattr(e, "status", 0)
                if 500 <= status < 600 and attempt == 1:
                    await asyncio.sleep(2)
                    continue
                # Quietly count as failure; printing every 403 is noisy
                return False
            except Exception as e:
                error(f"  {label}: {type(e).__name__}: {e}")
                return False
        return False

    for i, guild in enumerate(guilds, 1):
        ok = await _ack(guild, f"guild {guild.name}")
        if ok:
            marked += 1
        else:
            failed += 1
        if i % 10 == 0:
            info(f"  ...{i}/{len(guilds)} guilds  ({marked} ok, {failed} failed)")
        await asyncio.sleep(PER_ACK_SLEEP)

    for ch in dms:
        recip = getattr(ch, "recipient", None)
        label = f"DM with {recip}" if recip else f"DM {ch.id}"
        if await _ack(ch, label):
            marked += 1
        else:
            failed += 1
        await asyncio.sleep(PER_ACK_SLEEP)

    success(f"acked {marked} ({failed} failed)")
