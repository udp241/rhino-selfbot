"""
Discord-native per-user notes. These are the notes you can write in
the user popout in the Discord client — they're stored on Discord's
servers, not locally.

(Different from /note which is for your own local notes.)

CLI:
    /dnote get <user_id>
    /dnote set <user_id> <text...>
    /dnote del <user_id>
    /dnote list                       -- list all your stored notes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def dnote_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /dnote <get|set|del|list> ...")
    sub, *rest = args
    client = handler.session

    if sub == "list":
        try:
            notes = await client.fetch_notes()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        # Dict[int, str] : { user_id : note_text }
        info(f"Discord notes ({WHITE}{len(notes)}{RESET}):")
        for uid, text in notes.items():
            print(f"  {GREY}{uid}{RESET}  {text}")
        return

    if sub == "get":
        if not rest:
            raise ValueError("usage: /dnote get <user_id>")
        uid = int(rest[0])
        try:
            note = await client.fetch_note(uid)
        except discord.NotFound:
            info("(no note)")
            return
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        # Returns Optional[str]
        if not note:
            info("(no note)")
        else:
            print(f"  {note}")
        return

    if sub == "set":
        if len(rest) < 2:
            raise ValueError("usage: /dnote set <user_id> <text...>")
        uid = int(rest[0])
        text = " ".join(rest[1:])
        try:
            user = await client.fetch_user(uid)
            await user.edit_note(text)
        except discord.HTTPException as e:
            raise RuntimeError(f"set failed: {e}")
        success(f"note set for {uid}")
        return

    if sub == "del":
        if not rest:
            raise ValueError("usage: /dnote del <user_id>")
        uid = int(rest[0])
        try:
            user = await client.fetch_user(uid)
            await user.edit_note("")
        except discord.HTTPException as e:
            raise RuntimeError(f"del failed: {e}")
        success(f"note deleted for {uid}")
        return

    raise ValueError(f"unknown dnote subcommand: {sub}")
