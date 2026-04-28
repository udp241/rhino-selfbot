"""
Info utilities: tokeninfo, whois, firstmsg.
"""

from __future__ import annotations

import base64
import datetime as dt
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


def _snowflake_to_dt(snowflake: int) -> dt.datetime:
    DISCORD_EPOCH = 1420070400000  # ms
    ms = (snowflake >> 22) + DISCORD_EPOCH
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)


async def tokeninfo(handler: "CommandHandler", args: list[str]) -> None:
    """Decode the base64 user-id segment of a token. Local only, no API call."""
    if not args:
        raise ValueError("usage: /tokeninfo <token>")
    token = args[0]

    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("not a valid token format")

    try:
        # First segment is base64-encoded user ID
        pad = "=" * (-len(parts[0]) % 4)
        user_id = base64.b64decode(parts[0] + pad).decode("utf-8")
    except Exception as e:
        raise ValueError(f"could not decode user id segment: {e}")

    print(f"User ID:    {user_id}")
    try:
        created = _snowflake_to_dt(int(user_id))
        print(f"Created:    {created.isoformat()}")
    except Exception:
        pass

    # Second segment encodes a creation timestamp for the token itself
    try:
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        token_ts = int.from_bytes(raw, "big")
        # Discord epoch offset for token timestamps
        token_dt = dt.datetime.fromtimestamp(token_ts + 1293840000, tz=dt.timezone.utc)
        print(f"Token gen:  {token_dt.isoformat()}")
    except Exception:
        pass


async def whois(handler: "CommandHandler", args: list[str]) -> None:
    """Fetch and pretty-print a user's public info."""
    if not args:
        raise ValueError("usage: /whois <user_id>")
    try:
        uid = int(args[0])
    except ValueError:
        raise ValueError("user_id must be a number")

    try:
        user = await handler.session.fetch_user(uid)
    except discord.NotFound:
        raise RuntimeError("user not found")
    except discord.HTTPException as e:
        raise RuntimeError(f"fetch failed: {e}")

    created = user.created_at.isoformat() if user.created_at else "?"
    print(f"User:       {user}")
    print(f"ID:         {user.id}")
    print(f"Created:    {created}")
    print(f"Bot:        {user.bot}")
    print(f"Avatar:     {user.display_avatar.url if user.display_avatar else '(none)'}")
    flags = getattr(user, "public_flags", None)
    if flags is not None:
        names = [name for name, val in flags if val]
        print(f"Flags:      {', '.join(names) if names else '(none)'}")


async def firstmsg(handler: "CommandHandler", args: list[str]) -> None:
    """Fetch the first message in a channel."""
    if not args:
        raise ValueError("usage: /firstmsg <channel_id>")
    try:
        cid = int(args[0])
    except ValueError:
        raise ValueError("channel_id must be a number")

    ch = handler.session.get_channel(cid)
    if ch is None:
        try:
            ch = await handler.session.fetch_channel(cid)
        except discord.HTTPException as e:
            raise RuntimeError(f"channel fetch failed: {e}")

    try:
        async for msg in ch.history(limit=1, oldest_first=True):
            print(f"From:    {msg.author}")
            print(f"At:      {msg.created_at.isoformat()}")
            print(f"Link:    {msg.jump_url}")
            print(f"Content: {msg.content!r}")
            return
    except discord.HTTPException as e:
        raise RuntimeError(f"history fetch failed: {e}")

    print("(channel appears to have no messages)")
