"""
Local notes + bookmarks. Both stored in SQLite. Nothing leaves your machine.

Notes:
    /note add <text>            -- can use #tag1,tag2 anywhere in the text
    /note list [tag]
    /note search <query>
    /note del <id>

Bookmarks:
    /bm add <message_link>
    /bm list
    /bm del <id>
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import discord

from .db import db

if TYPE_CHECKING:
    from .handler import CommandHandler


_TAG_RE = re.compile(r"#([\w-]+)")
_LINK_RE = re.compile(
    r"https?://(?:www\.|canary\.|ptb\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild>\d+|@me)/(?P<channel>\d+)/(?P<message>\d+)"
)


# ---------- notes ----------

async def note(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /note <add|list|search|del> ...")
    sub, *rest = args

    if sub == "add":
        if not rest:
            raise ValueError("usage: /note add <text>")
        text = " ".join(rest)
        tags = ",".join(sorted(set(_TAG_RE.findall(text))))
        conn = db()
        cur = conn.execute(
            "INSERT INTO notes(content, tags, created_at) VALUES (?, ?, ?)",
            (text, tags, int(time.time())),
        )
        conn.commit()
        print(f"saved note #{cur.lastrowid}" + (f" [{tags}]" if tags else ""))

    elif sub == "list":
        if rest:
            tag = rest[0].lstrip("#")
            rows = db().execute(
                "SELECT id, content, tags, created_at FROM notes "
                "WHERE tags LIKE ? ORDER BY id DESC",
                (f"%{tag}%",),
            ).fetchall()
        else:
            rows = db().execute(
                "SELECT id, content, tags, created_at FROM notes ORDER BY id DESC"
            ).fetchall()
        if not rows:
            print("(no notes)")
            return
        for r in rows:
            tag_str = f" [{r['tags']}]" if r["tags"] else ""
            print(f"  #{r['id']}{tag_str}  {r['content']}")

    elif sub == "search":
        if not rest:
            raise ValueError("usage: /note search <query>")
        q = " ".join(rest)
        rows = db().execute(
            "SELECT id, content, tags FROM notes WHERE content LIKE ? ORDER BY id DESC",
            (f"%{q}%",),
        ).fetchall()
        for r in rows:
            print(f"  #{r['id']}  {r['content']}")
        if not rows:
            print("(no matches)")

    elif sub in ("del", "delete", "rm"):
        if not rest:
            raise ValueError("usage: /note del <id>")
        nid = int(rest[0])
        conn = db()
        conn.execute("DELETE FROM notes WHERE id=?", (nid,))
        conn.commit()
        print(f"deleted note #{nid}")

    else:
        raise ValueError(f"unknown note subcommand: {sub}")


# ---------- bookmarks ----------

async def bookmark(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /bm <add|list|del> ...")
    sub, *rest = args

    if sub == "add":
        if not rest:
            raise ValueError("usage: /bm add <message_link>")
        link = rest[0]
        m = _LINK_RE.match(link)
        if not m:
            raise ValueError("not a valid Discord message link")

        guild_part = m.group("guild")
        channel_id = int(m.group("channel"))
        message_id = int(m.group("message"))

        client = handler.session
        ch = client.get_channel(channel_id)
        if ch is None:
            try:
                ch = await client.fetch_channel(channel_id)
            except discord.HTTPException as e:
                raise RuntimeError(f"could not fetch channel: {e}")

        try:
            msg = await ch.fetch_message(message_id)
        except discord.HTTPException as e:
            raise RuntimeError(f"could not fetch message: {e}")

        guild_name = msg.guild.name if msg.guild else "(DM)"
        ch_name = getattr(ch, "name", None) or str(ch)

        conn = db()
        cur = conn.execute(
            "INSERT INTO bookmarks(jump_url, content, author, channel_name, guild_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg.jump_url, msg.content, str(msg.author), ch_name, guild_name, int(time.time())),
        )
        conn.commit()
        print(f"bookmark #{cur.lastrowid}: {msg.author} in #{ch_name}")

    elif sub == "list":
        rows = db().execute(
            "SELECT id, jump_url, content, author, channel_name, guild_name "
            "FROM bookmarks ORDER BY id DESC"
        ).fetchall()
        if not rows:
            print("(no bookmarks)")
            return
        for r in rows:
            preview = (r["content"] or "")[:80]
            print(f"  #{r['id']}  [{r['guild_name']} #{r['channel_name']}] {r['author']}: {preview}")
            print(f"        {r['jump_url']}")

    elif sub in ("del", "delete", "rm"):
        if not rest:
            raise ValueError("usage: /bm del <id>")
        bid = int(rest[0])
        conn = db()
        conn.execute("DELETE FROM bookmarks WHERE id=?", (bid,))
        conn.commit()
        print(f"deleted bookmark #{bid}")

    else:
        raise ValueError(f"unknown bm subcommand: {sub}")
