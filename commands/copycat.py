"""
Copycat — auto-reply with the same content whenever a target user speaks.

State lives in the kv table so it persists across restarts. Toggle and
target list are managed via the `copycat` CLI command.

CLI:
    /copycat on <user_id>          -- start copying that user
    /copycat off <user_id>         -- stop copying that user
    /copycat off                   -- stop copying everyone
    /copycat list                  -- show who's being copied
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import discord

from .db import kv_get, kv_set
from utils.branding import info, success, error, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


_KEY = "copycat_users"  # comma-separated user ids
_COOLDOWN_SECONDS = 1.0  # min gap between copy-replies per channel
_last_reply_at: dict[int, float] = {}  # channel_id -> last reply ts


def _load_targets() -> set[int]:
    raw = kv_get(_KEY, "") or ""
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _save_targets(targets: set[int]) -> None:
    kv_set(_KEY, ",".join(str(t) for t in sorted(targets)))


async def copycat_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /copycat <on|off|list> [user_id]")

    sub = args[0].lower()
    targets = _load_targets()

    if sub == "list":
        if not targets:
            info("(copycat targets: none)")
            return
        info(f"copycat targets ({len(targets)}):")
        for t in sorted(targets):
            print(f"  {WHITE}{t}{RESET}")
        return

    if sub == "on":
        if len(args) < 2:
            raise ValueError("usage: /copycat on <user_id>")
        uid = int(args[1])
        targets.add(uid)
        _save_targets(targets)
        success(f"copying user {uid}")
        return

    if sub == "off":
        if len(args) < 2:
            # Off all
            _save_targets(set())
            success("copycat: stopped copying everyone")
            return
        uid = int(args[1])
        if uid in targets:
            targets.remove(uid)
            _save_targets(targets)
            success(f"stopped copying {uid}")
        else:
            error(f"{uid} wasn't in the copycat list")
        return

    raise ValueError(f"unknown copycat subcommand: {sub}")


async def maybe_mirror(client: discord.Client, message: discord.Message) -> None:
    """Called from main.py's on_message hook. No-op if not active."""
    # Self-message guard — never mirror ourselves
    if message.author.id == client.user.id:
        return
    if message.author.bot:
        return

    targets = _load_targets()
    if not targets or message.author.id not in targets:
        return

    # Per-channel cooldown so two fast messages from the target don't
    # both fire (same race shape as the AFK bug we fixed earlier).
    now = time.time()
    last = _last_reply_at.get(message.channel.id, 0)
    if now - last < _COOLDOWN_SECONDS:
        return
    _last_reply_at[message.channel.id] = now

    content = message.content or ""
    if not content:
        return

    # Tiny delay so it doesn't look like a millisecond-perfect echo
    await asyncio.sleep(0.4 + (hash(content) % 30) / 100.0)

    try:
        await message.channel.send(content)
    except discord.HTTPException:
        # Couldn't send — roll back the cooldown so we can try next message
        _last_reply_at.pop(message.channel.id, None)
