"""
Reminders. Persisted in SQLite so they survive restarts.

CLI:
    /remind <duration> <text>            -- prints to console + logs
    /remind <duration> <text> --to <channel_id>   -- also posts in channel
    /reminders                            -- list pending
    /remind del <id>

Duration format: combinations of <number><s|m|h|d>, e.g.
    30s, 5m, 2h, 1d, 1h30m, 2d6h, 90m
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Optional

import discord

from .db import db

if TYPE_CHECKING:
    from .handler import CommandHandler


_DUR_RE = re.compile(r"(\d+)([smhd])")


def parse_duration(s: str) -> int:
    """Returns seconds. Raises ValueError if no valid units found."""
    matches = _DUR_RE.findall(s.lower())
    if not matches:
        raise ValueError(f"could not parse duration '{s}' (use 30s/5m/2h/1d combos)")
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return sum(int(n) * mult[u] for n, u in matches)


def fmt_remaining(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60}s"
    if secs < 86400:
        h, rem = divmod(secs, 3600)
        return f"{h}h{rem // 60}m"
    d, rem = divmod(secs, 86400)
    return f"{d}d{rem // 3600}h"


async def remind(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /remind <duration> <text>  [--to <channel_id>]")

    if args[0] in ("del", "delete", "rm"):
        if len(args) < 2:
            raise ValueError("usage: /remind del <id>")
        rid = int(args[1])
        conn = db()
        conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
        conn.commit()
        print(f"deleted reminder #{rid}")
        return

    # Pull off optional --to <channel_id>
    channel_id: Optional[int] = None
    parts = list(args)
    if "--to" in parts:
        i = parts.index("--to")
        try:
            channel_id = int(parts[i + 1])
        except (IndexError, ValueError):
            raise ValueError("--to needs a numeric channel id")
        del parts[i:i + 2]

    if len(parts) < 2:
        raise ValueError("usage: /remind <duration> <text>")
    duration_s = parse_duration(parts[0])
    text = " ".join(parts[1:])
    due = int(time.time()) + duration_s

    conn = db()
    cur = conn.execute(
        "INSERT INTO reminders(text, due_at, channel_id, created_at, fired) "
        "VALUES (?, ?, ?, ?, 0)",
        (text, due, channel_id, int(time.time())),
    )
    conn.commit()
    print(f"reminder #{cur.lastrowid} set for {fmt_remaining(duration_s)} from now")


async def list_reminders(handler: "CommandHandler", args: list[str]) -> None:
    rows = db().execute(
        "SELECT id, text, due_at, channel_id FROM reminders WHERE fired=0 ORDER BY due_at ASC"
    ).fetchall()
    if not rows:
        print("(no pending reminders)")
        return
    now = int(time.time())
    for r in rows:
        remaining = max(0, r["due_at"] - now)
        ch = f" -> ch:{r['channel_id']}" if r["channel_id"] else ""
        print(f"  #{r['id']}  in {fmt_remaining(remaining)}{ch}  {r['text']}")


async def reminder_ticker(handler: "CommandHandler") -> None:
    """Background task: every 30s, fire any due reminders."""
    while True:
        await asyncio.sleep(30)
        try:
            now = int(time.time())
            rows = db().execute(
                "SELECT id, text, channel_id FROM reminders WHERE fired=0 AND due_at<=?",
                (now,),
            ).fetchall()
            for r in rows:
                msg = f"⏰ REMINDER #{r['id']}: {r['text']}"
                print(f"\n{'=' * 60}\n{msg}\n{'=' * 60}\n> ", end="", flush=True)

                # Optionally also post in a channel
                if r["channel_id"]:
                    ch = handler.session.get_channel(r["channel_id"])
                    if ch is None:
                        try:
                            ch = await handler.session.fetch_channel(r["channel_id"])
                        except discord.HTTPException:
                            ch = None
                    if ch and hasattr(ch, "send"):
                        try:
                            await ch.send(msg)
                        except discord.HTTPException:
                            pass

                conn = db()
                conn.execute("UPDATE reminders SET fired=1 WHERE id=?", (r["id"],))
                conn.commit()
        except Exception as e:
            print(f"[reminder_ticker] error: {e}")
