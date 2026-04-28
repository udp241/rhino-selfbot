"""
DM archiver. Walks a DM's message history and writes each message to a
per-channel SQLite database. Optionally downloads attachments to disk.

CLI:
    /archive <user|channel id> [--limit N] [--no-attach] [--out <dir>]
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aiohttp
import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


ARCHIVE_ROOT = Path(__file__).resolve().parent.parent / "archives"


def _open_archive_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id   INTEGER PRIMARY KEY,
            author_id    INTEGER,
            author_name  TEXT,
            content      TEXT,
            created_at   TEXT,
            edited_at    TEXT,
            attachments  TEXT  -- JSON array
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY, value TEXT
        );
        """
    )
    conn.commit()
    return conn


async def _resolve_dm(client: discord.Client, target_id: int) -> Optional[discord.DMChannel]:
    ch = client.get_channel(target_id)
    if isinstance(ch, discord.DMChannel):
        return ch
    try:
        user = await client.fetch_user(target_id)
    except discord.HTTPException:
        return None
    if user.dm_channel:
        return user.dm_channel
    try:
        return await user.create_dm()
    except discord.HTTPException:
        return None


async def archive_dm(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError(
            "usage: /archive <user|channel id> [--limit N] [--no-attach] [--out <dir>]"
        )

    target_id = int(args[0])
    limit_total: Optional[int] = None
    download_attachments = True
    out_dir = ARCHIVE_ROOT

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--limit":
            limit_total = int(args[i + 1]); i += 2
        elif a == "--no-attach":
            download_attachments = False; i += 1
        elif a == "--out":
            out_dir = Path(args[i + 1]); i += 2
        else:
            raise ValueError(f"unknown flag: {a}")

    channel = await _resolve_dm(handler.session, target_id)
    if channel is None:
        raise RuntimeError(f"could not resolve DM channel for id {target_id}")

    other = channel.recipient if hasattr(channel, "recipient") else "unknown"
    print(f"Archiving DM with: {other}")

    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / f"dm_{channel.id}.db"
    files_dir = out_dir / f"dm_{channel.id}_files"
    if download_attachments:
        files_dir.mkdir(parents=True, exist_ok=True)

    conn = _open_archive_db(db_path)
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("recipient", str(other)),
    )
    conn.commit()

    saved = 0
    skipped = 0
    last_id = None

    async with aiohttp.ClientSession() as http:
        while True:
            if limit_total is not None and saved >= limit_total:
                break

            kwargs = {"limit": 100}
            if last_id is not None:
                kwargs["before"] = last_id

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
            last_id = batch[-1]

            for msg in batch:
                # Already saved? skip
                exists = conn.execute(
                    "SELECT 1 FROM messages WHERE message_id=?", (msg.id,)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                attachments = []
                for att in msg.attachments:
                    rec = {"id": att.id, "filename": att.filename, "url": att.url, "size": att.size}
                    if download_attachments:
                        local_name = f"{att.id}_{att.filename}"
                        local_path = files_dir / local_name
                        try:
                            async with http.get(att.url) as resp:
                                if resp.status == 200:
                                    with open(local_path, "wb") as f:
                                        async for chunk in resp.content.iter_chunked(64 * 1024):
                                            f.write(chunk)
                                    rec["local"] = str(local_path)
                        except Exception as e:
                            rec["error"] = str(e)
                    attachments.append(rec)

                conn.execute(
                    "INSERT INTO messages(message_id, author_id, author_name, content, created_at, edited_at, attachments) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        msg.id,
                        msg.author.id,
                        str(msg.author),
                        msg.content,
                        msg.created_at.isoformat() if msg.created_at else None,
                        msg.edited_at.isoformat() if msg.edited_at else None,
                        json.dumps(attachments),
                    ),
                )
                saved += 1
                if saved % 100 == 0:
                    conn.commit()
                    print(f"  ... saved {saved}")
                if limit_total is not None and saved >= limit_total:
                    break

            conn.commit()
            await asyncio.sleep(0.5)  # gentle on the rate limiter

    conn.close()
    print("-" * 40)
    print(f"Saved: {saved}  |  Skipped (already in db): {skipped}")
    print(f"Database: {db_path}")
    if download_attachments:
        print(f"Attachments: {files_dir}")
