"""
Discovery utilities.

CLI:
    /preview <guild_id>            -- peek at a public/discoverable server without joining
    /username <name>               -- check if a Pomelo username is available
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, GREY, WHITE, YELLOW, GREEN, RED, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def preview_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /preview <guild_id>")
    try:
        gid = int(args[0])
    except ValueError:
        raise ValueError("guild_id must be a number")
    client = handler.session

    if not hasattr(client, "fetch_guild_preview"):
        raise RuntimeError("fetch_guild_preview not available")

    try:
        prev = await client.fetch_guild_preview(gid)
    except discord.NotFound:
        raise RuntimeError("guild not found or not previewable (must be discoverable / public)")
    except discord.HTTPException as e:
        raise RuntimeError(f"preview fetch failed: {e}")

    print(f"  {WHITE}{prev.name}{RESET}  {GREY}(id: {prev.id}){RESET}")
    if prev.description:
        print(f"  {prev.description}")
    members = getattr(prev, "approximate_member_count", None)
    online = getattr(prev, "approximate_presence_count", None)
    if members is not None:
        print(f"  Members: {WHITE}{members}{RESET}  Online: {WHITE}{online or '?'}{RESET}")
    icon = getattr(prev, "icon", None)
    if icon:
        print(f"  Icon:    {icon.url}")
    splash = getattr(prev, "splash", None)
    if splash:
        print(f"  Splash:  {splash.url}")
    features = getattr(prev, "features", None)
    if features:
        print(f"  Features: {', '.join(features)}")
    emojis = getattr(prev, "emojis", None)
    if emojis:
        print(f"  Emojis:  {len(emojis)}")


async def username_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /username <desired_name>")
    name = args[0]
    client = handler.session

    if not hasattr(client, "check_pomelo_username"):
        raise RuntimeError("check_pomelo_username not available")

    try:
        result = await client.check_pomelo_username(name)
    except discord.HTTPException as e:
        raise RuntimeError(f"check failed: {e}")

    # Result shape varies; commonly returns dict or named tuple with 'taken'
    taken = result.get("taken") if isinstance(result, dict) else getattr(result, "taken", None)
    if taken is True:
        print(f"  {RED}taken{RESET}: {name}")
    elif taken is False:
        print(f"  {GREEN}available{RESET}: {name}")
    else:
        # Fall back to printing the raw response
        print(f"  result: {result}")
