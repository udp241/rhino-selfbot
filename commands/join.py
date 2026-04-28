"""
Accept a single invite. Uses client.accept_invite (the documented API)
with a fallback to invite.use() for older library versions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import success, info, error

if TYPE_CHECKING:
    from .handler import CommandHandler


_INVITE_PREFIXES = (
    "https://discord.gg/",
    "http://discord.gg/",
    "https://discord.com/invite/",
    "http://discord.com/invite/",
    "discord.gg/",
    "discord.com/invite/",
)


def extract_invite_code(s: str) -> str:
    s = s.strip()
    for p in _INVITE_PREFIXES:
        if s.startswith(p):
            return s[len(p):].split("/")[0].split("?")[0]
    return s


async def join_invite(handler: "CommandHandler", invite_input: str) -> None:
    code = extract_invite_code(invite_input)
    client = handler.session

    try:
        invite = await client.fetch_invite(code, with_counts=True)
    except discord.NotFound:
        raise RuntimeError(f"invite '{code}' not found or expired")
    except discord.HTTPException as e:
        raise RuntimeError(f"failed to fetch invite: {e}")

    guild_name = invite.guild.name if invite.guild else "(unknown)"
    info(f"Joining: {guild_name}")
    if invite.guild and getattr(invite.guild, "description", None):
        info(f"  {invite.guild.description}")
    if invite.approximate_member_count:
        info(f"  Members: {invite.approximate_member_count} "
             f"({invite.approximate_presence_count or '?'} online)")
    if invite.inviter:
        info(f"  Invited by: {invite.inviter}")

    # Try the modern API first, fall back if it's not there
    try:
        if hasattr(client, "accept_invite"):
            await client.accept_invite(invite)
        else:
            await invite.use()
    except discord.HTTPException as e:
        raise RuntimeError(f"failed to accept invite: {e}")

    success(f"Joined {guild_name}")
