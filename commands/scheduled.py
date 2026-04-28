"""
Scheduled messages — post a message in a specific channel at a future time.

Persisted in SQLite so they survive restarts. A background ticker checks
every 30s for due messages.

CLI:
    /sched <ch_id> <duration> <text...>     # schedule for ch_id in <duration>
    /sched list                              # show pending
    /sched del <id>                          # cancel one

Duration format: same as /remind  (30s, 5m, 2h, 1d, 1h30m...)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import discord

from .db import db
from .reminders import parse_duration, fmt_remaining
from utils.branding import info, success, error, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def sched(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError(
            "usage: /sched <ch_id> <duration> <text...>  |  /sched list  |  /sched del <id>"
        )

    sub = args[0]

    if sub == "list":
        rows = db().execute(
            "SELECT id, channel_id, text, due_at FROM scheduled_messages "
            "WHERE fired=0 ORDER BY due_at ASC"
        ).fetchall()
        if not rows:
            info("(no pending scheduled messages)")
            return
        now = int(time.time())
        for r in rows:
            remaining = max(0, r["due_at"] - now)
            preview = r["text"][:60].replace("\n", " ")
            print(f"  #{r['id']}  in {fmt_remaining(remaining)}  "
                  f"{GREY}ch:{r['channel_id']}{RESET}  {preview}")
        return

    if sub in ("del", "delete", "rm", "cancel"):
        if len(args) < 2:
            raise ValueError("usage: /sched del <id>")
        sid = int(args[1])
        conn = db()
        cur = conn.execute("DELETE FROM scheduled_messages WHERE id=? AND fired=0", (sid,))
        conn.commit()
        if cur.rowcount:
            success(f"cancelled scheduled message #{sid}")
        else:
            error(f"no pending scheduled message with id {sid}")
        return

    # Otherwise: schedule a new one. args = [ch_id, duration, ...text]
    if len(args) < 3:
        raise ValueError("usage: /sched <ch_id> <duration> <text...>")
    try:
        cid = int(args[0])
    except ValueError:
        raise ValueError("first arg must be a channel id (or 'list' / 'del')")

    duration_s = parse_duration(args[1])
    text = " ".join(args[2:])
    if not text:
        raise ValueError("missing message text")

    due = int(time.time()) + duration_s
    conn = db()
    cur = conn.execute(
        "INSERT INTO scheduled_messages(channel_id, text, due_at, created_at, fired) "
        "VALUES (?, ?, ?, ?, 0)",
        (cid, text, due, int(time.time())),
    )
    conn.commit()
    success(f"scheduled #{cur.lastrowid} for {fmt_remaining(duration_s)} from now "
            f"-> ch:{cid}")


async def sched_ticker(handler: "CommandHandler") -> None:
    """Background task: every 30s, post any due scheduled messages."""
    while True:
        await asyncio.sleep(30)
        try:
            now = int(time.time())
            rows = db().execute(
                "SELECT id, channel_id, text FROM scheduled_messages "
                "WHERE fired=0 AND due_at<=?",
                (now,),
            ).fetchall()
            for r in rows:
                ch = handler.session.get_channel(r["channel_id"])
                if ch is None:
                    try:
                        ch = await handler.session.fetch_channel(r["channel_id"])
                    except discord.HTTPException:
                        ch = None
                fired = False
                if ch is not None and hasattr(ch, "send"):
                    try:
                        await ch.send(r["text"])
                        fired = True
                    except discord.HTTPException as e:
                        error(f"sched #{r['id']} send failed: {e}")
                else:
                    error(f"sched #{r['id']}: channel {r['channel_id']} not reachable")

                # Mark fired regardless — don't loop on a permanently-broken target.
                # If you want retry semantics, re-add manually.
                conn = db()
                conn.execute(
                    "UPDATE scheduled_messages SET fired=1 WHERE id=?",
                    (r["id"],),
                )
                conn.commit()
                if fired:
                    info(f"posted scheduled #{r['id']} -> ch:{r['channel_id']}")
        except Exception as e:
            error(f"[sched_ticker] {type(e).__name__}: {e}")
