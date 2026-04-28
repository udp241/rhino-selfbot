"""
Guild backup. Save a guild's structure (channels, categories, roles)
to JSON, list saved backups, delete one, or restore a backup into a
guild you have admin in.

CLI:
    /backup save <guild_id>
    /backup list
    /backup load <backup_id> <target_guild_id>
    /backup delete <backup_id>

Backup files live under ./backups/ — gitignored by default.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import discord

from utils.branding import error, success, info, warn, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


BACKUPS_DIR = Path(__file__).resolve().parent.parent / "backups"


def _serialize_guild(g: discord.Guild) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "saved_at": int(time.time()),
        "icon_url": g.icon.url if g.icon else None,
        "roles": [
            {
                "name": r.name,
                "color": r.color.value,
                "hoist": r.hoist,
                "mentionable": r.mentionable,
                "permissions": r.permissions.value,
                "position": r.position,
            }
            for r in g.roles if not r.is_default()
        ],
        "categories": [
            {"name": c.name, "position": c.position}
            for c in g.categories
        ],
        "text_channels": [
            {
                "name": c.name,
                "topic": c.topic,
                "nsfw": c.nsfw,
                "category": c.category.name if c.category else None,
                "position": c.position,
                "slowmode_delay": c.slowmode_delay,
            }
            for c in g.text_channels
        ],
        "voice_channels": [
            {
                "name": c.name,
                "bitrate": c.bitrate,
                "user_limit": c.user_limit,
                "category": c.category.name if c.category else None,
                "position": c.position,
            }
            for c in g.voice_channels
        ],
    }


async def backup(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /backup <save|list|load|delete> ...")
    sub, *rest = args

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    if sub == "save":
        if not rest:
            raise ValueError("usage: /backup save <guild_id>")
        g = handler.session.get_guild(int(rest[0]))
        if not g:
            raise RuntimeError("not in that guild")
        data = _serialize_guild(g)
        path = BACKUPS_DIR / f"{g.id}_{int(time.time())}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        success(f"saved: {path.name}")
        info(f"  {len(data['roles'])} roles, {len(data['text_channels'])} text, "
             f"{len(data['voice_channels'])} voice, {len(data['categories'])} categories")
        return

    if sub == "list":
        files = sorted(BACKUPS_DIR.glob("*.json"))
        if not files:
            info("(no backups)")
            return
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    d = json.load(fh)
                info(f"  {GREY}{f.stem}{RESET}  {WHITE}{d.get('name')}{RESET}  "
                     f"{GREY}guild:{d.get('id')}{RESET}")
            except json.JSONDecodeError:
                error(f"  {f.name}: corrupt")
        return

    if sub == "load":
        if len(rest) < 2:
            raise ValueError("usage: /backup load <backup_id> <target_guild_id>")
        backup_id = rest[0]
        target_gid = int(rest[1])
        path = BACKUPS_DIR / f"{backup_id}.json"
        if not path.exists():
            raise RuntimeError(f"backup not found: {path.name}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        g = handler.session.get_guild(target_gid)
        if not g:
            raise RuntimeError("not in target guild")
        if not g.me.guild_permissions.administrator:
            raise RuntimeError("need administrator in target guild")

        warn(f"loading '{data.get('name')}' into {g.name}, wiping existing structure first")
        # Wipe
        for ch in list(g.channels):
            try:
                await ch.delete()
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)
        for r in list(g.roles):
            if r.is_default() or r.managed:
                continue
            try:
                await r.delete()
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)

        # Roles (lowest position first)
        new_roles_by_name = {}
        for rdef in sorted(data["roles"], key=lambda r: r["position"]):
            try:
                nr = await g.create_role(
                    name=rdef["name"],
                    colour=discord.Color(rdef.get("color", 0)),
                    hoist=rdef.get("hoist", False),
                    mentionable=rdef.get("mentionable", False),
                    permissions=discord.Permissions(rdef.get("permissions", 0)),
                )
                new_roles_by_name[rdef["name"]] = nr
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)

        # Categories
        new_cats = {}
        for cdef in sorted(data["categories"], key=lambda c: c["position"]):
            try:
                cat = await g.create_category(cdef["name"])
                new_cats[cdef["name"]] = cat
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)

        # Text channels
        for cdef in sorted(data["text_channels"], key=lambda c: c["position"]):
            try:
                cat = new_cats.get(cdef["category"]) if cdef.get("category") else None
                await g.create_text_channel(
                    name=cdef["name"],
                    topic=cdef.get("topic"),
                    nsfw=cdef.get("nsfw", False),
                    category=cat,
                    slowmode_delay=cdef.get("slowmode_delay", 0),
                )
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)

        # Voice channels
        for cdef in sorted(data["voice_channels"], key=lambda c: c["position"]):
            try:
                cat = new_cats.get(cdef["category"]) if cdef.get("category") else None
                await g.create_voice_channel(
                    name=cdef["name"],
                    bitrate=cdef.get("bitrate", 64000),
                    user_limit=cdef.get("user_limit", 0),
                    category=cat,
                )
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)

        success(f"backup loaded into {g.name}")
        return

    if sub == "delete":
        if not rest:
            raise ValueError("usage: /backup delete <backup_id>")
        path = BACKUPS_DIR / f"{rest[0]}.json"
        if not path.exists():
            raise RuntimeError("backup not found")
        os.remove(path)
        success(f"deleted {path.name}")
        return

    raise ValueError(f"unknown backup subcommand: {sub}")
