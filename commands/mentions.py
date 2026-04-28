"""
Recent mentions viewer, dismisser, and live-notify.

CLI:
    /mentions list [--limit N] [--guild <guild_id>]
    /mentions clear                          -- dismiss all
    /mentions dismiss <message_id>           -- dismiss one
    /mentions notify on|off|status           -- DM yourself when @mentioned
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord

from .db import kv_get, kv_set
from utils.branding import info, success, error, GREEN, GREY, WHITE, YELLOW, CYAN_DIM, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


_NOTIFY_KEY = "mention_notify_enabled"


def _notify_enabled() -> bool:
    return (kv_get(_NOTIFY_KEY, "0") == "1")


async def mentions_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /mentions <list|clear|dismiss|notify>")
    sub, *rest = args
    client = handler.session

    if sub == "notify":
        if not rest or rest[0] == "status":
            state = "ON" if _notify_enabled() else "OFF"
            info(f"mention notify: {WHITE}{state}{RESET}")
            return
        action = rest[0].lower()
        if action == "on":
            kv_set(_NOTIFY_KEY, "1")
            success("mention notify ON — you'll get a DM when @mentioned")
            return
        if action == "off":
            kv_set(_NOTIFY_KEY, "0")
            success("mention notify OFF")
            return
        raise ValueError("usage: /mentions notify <on|off|status>")

    if not hasattr(client, "recent_mentions"):
        raise RuntimeError("recent_mentions not available — your discord.py-self may be outdated")

    if sub == "list":
        limit = 25
        guild_filter: Optional[int] = None
        i = 0
        while i < len(rest):
            if rest[i] == "--limit":
                limit = int(rest[i + 1]); i += 2
            elif rest[i] == "--guild":
                guild_filter = int(rest[i + 1]); i += 2
            else:
                i += 1

        kwargs = {"limit": limit}
        if guild_filter is not None:
            kwargs["guild"] = discord.Object(id=guild_filter)

        count = 0
        async for msg in client.recent_mentions(**kwargs):
            count += 1
            ch_name = getattr(msg.channel, "name", str(msg.channel.id))
            guild_name = msg.guild.name if msg.guild else "(DM)"
            print(f"  {GREY}{msg.id}{RESET}  "
                  f"[{guild_name} #{ch_name}]  "
                  f"{WHITE}{msg.author}{RESET}: {msg.content[:80]}")
            print(f"        {CYAN_DIM}{msg.jump_url}{RESET}")
        if count == 0:
            info("(no recent mentions)")
        return

    if sub == "dismiss":
        if not rest:
            raise ValueError("usage: /mentions dismiss <message_id>")
        mid = int(rest[0])
        try:
            await client.delete_recent_mention(discord.Object(id=mid))
        except discord.HTTPException as e:
            raise RuntimeError(f"dismiss failed: {e}")
        success(f"dismissed mention {mid}")
        return

    if sub == "clear":
        cleared = 0
        async for msg in client.recent_mentions(limit=200):
            try:
                await client.delete_recent_mention(msg)
                cleared += 1
            except discord.HTTPException:
                pass
        success(f"cleared {cleared} mention(s)")
        return

    raise ValueError(f"unknown mentions subcommand: {sub}")


# ---- live notify listener -------------------------------------------

async def maybe_notify_mention(client: discord.Client, message: discord.Message) -> None:
    """Called from main.py's on_message hook. DMs the user when they're
    @mentioned in any channel they can see, while toggle is on."""
    if not _notify_enabled():
        return
    if message.author.id == client.user.id:
        return
    me_id = client.user.id

    # Direct user mention or role mention that resolves to us
    mentioned = any(u.id == me_id for u in (message.mentions or []))
    if not mentioned and message.guild is not None:
        # Role-mention check: am I a member of any mentioned role?
        my_member = message.guild.get_member(me_id)
        if my_member is not None and message.role_mentions:
            my_role_ids = {r.id for r in my_member.roles}
            if any(r.id in my_role_ids for r in message.role_mentions):
                mentioned = True

    if not mentioned:
        return

    # Build a notification DM — keep it terse, jump_url is the main thing
    where = "DM" if message.guild is None else f"{message.guild.name} #{message.channel}"
    preview = (message.content or "")[:200]
    body = (
        f"@mention from **{message.author}** in `{where}`\n"
        f"{message.jump_url}\n"
        f"```\n{preview}\n```"
    )

    try:
        # DM ourselves via the self-DM channel
        me = client.user
        dm = me.dm_channel or await me.create_dm()
        await dm.send(body)
    except discord.HTTPException:
        # Self-DM couldn't be sent (rare). Silent.
        pass
