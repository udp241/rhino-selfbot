"""
SQLite for persistent state (reminders, notes, bookmarks).

DM archives live in their own databases per channel — see archive.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "selfbot.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


_CONN: Optional[sqlite3.Connection] = None


def db() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = _connect()
        _init_schema(_CONN)
    return _CONN


def _init_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT NOT NULL,
            due_at      INTEGER NOT NULL,         -- unix timestamp (s)
            channel_id  INTEGER,                  -- optional notify channel
            created_at  INTEGER NOT NULL,
            fired       INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at, fired);

        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT NOT NULL,
            tags        TEXT,                     -- comma-separated
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bookmarks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            jump_url     TEXT NOT NULL,
            content      TEXT,
            author       TEXT,
            channel_name TEXT,
            guild_name   TEXT,
            created_at   INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kv (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id  INTEGER NOT NULL,
            text        TEXT NOT NULL,
            due_at      INTEGER NOT NULL,
            created_at  INTEGER NOT NULL,
            fired       INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sched_due ON scheduled_messages(due_at, fired);
        """
    )
    conn.commit()


def kv_get(key: str, default: Optional[str] = None) -> Optional[str]:
    row = db().execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(key: str, value: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO kv(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
