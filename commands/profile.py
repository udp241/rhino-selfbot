"""
Rich user profile lookup using client.fetch_user_profile.

Returns mutual guilds, mutual friends, badges, banner, accent color,
premium type, bio, etc. — much richer than fetch_user.

CLI:
    /profile <user_id>
    /profile <user_id> --no-mutuals     (faster, just the basics)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, error, GREEN, GREY, WHITE, YELLOW, CYAN_DIM, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def profile(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /profile <user_id> [--no-mutuals]")
    try:
        uid = int(args[0])
    except ValueError:
        raise ValueError("user_id must be a number")

    fetch_mutuals = "--no-mutuals" not in args
    client = handler.session

    try:
        prof = await client.fetch_user_profile(
            uid,
            with_mutual_guilds=fetch_mutuals,
            with_mutual_friends=fetch_mutuals,
            with_mutual_friends_count=fetch_mutuals,
        )
    except discord.NotFound:
        raise RuntimeError("user not found, or no shared guild/friendship to view profile")
    except discord.HTTPException as e:
        raise RuntimeError(f"profile fetch failed: {e}")

    user = prof.user if hasattr(prof, "user") else prof

    print(f"{CYAN_DIM}{'-' * 50}{RESET}")
    print(f"  {WHITE}{user}{RESET}  {GREY}(id: {user.id}){RESET}")
    if user.created_at:
        print(f"  Created:    {user.created_at.isoformat()}")
    print(f"  Bot:        {user.bot}")

    bio = getattr(prof, "bio", None)
    if bio:
        print(f"  Bio:        {bio}")

    banner = getattr(prof, "banner", None)
    if banner:
        print(f"  Banner:     {banner.url}")

    accent = getattr(prof, "accent_colour", None) or getattr(prof, "accent_color", None)
    if accent:
        print(f"  Accent:     {accent}")

    premium_type = getattr(prof, "premium_type", None)
    if premium_type is not None:
        print(f"  Premium:    {premium_type}")

    premium_since = getattr(prof, "premium_since", None)
    if premium_since:
        print(f"  Nitro since: {premium_since.isoformat()}")

    premium_guild_since = getattr(prof, "premium_guild_since", None)
    if premium_guild_since:
        print(f"  Boost since: {premium_guild_since.isoformat()}")

    flags = getattr(user, "public_flags", None)
    if flags is not None:
        names = [name for name, val in flags if val]
        print(f"  Badges:     {', '.join(names) if names else '(none)'}")

    avatar = getattr(user, "display_avatar", None) or getattr(user, "avatar", None)
    if avatar:
        print(f"  Avatar:     {avatar.url}")

    if fetch_mutuals:
        mutual_guilds = getattr(prof, "mutual_guilds", None)
        if mutual_guilds is not None:
            print(f"\n  {YELLOW}Mutual guilds ({len(mutual_guilds)}):{RESET}")
            for g in mutual_guilds[:30]:
                name = getattr(g, "name", str(g))
                gid = getattr(g, "id", "?")
                print(f"    {GREY}{gid}{RESET}  {name}")
            if len(mutual_guilds) > 30:
                print(f"    {GREY}... +{len(mutual_guilds) - 30} more{RESET}")

        mutual_friends = getattr(prof, "mutual_friends", None)
        mf_count = getattr(prof, "mutual_friends_count", None)
        if mutual_friends:
            print(f"\n  {YELLOW}Mutual friends ({len(mutual_friends)}):{RESET}")
            for f in mutual_friends[:20]:
                print(f"    {f}")
            if len(mutual_friends) > 20:
                print(f"    {GREY}... +{len(mutual_friends) - 20} more{RESET}")
        elif mf_count:
            print(f"\n  Mutual friends count: {mf_count}")

    print(f"{CYAN_DIM}{'-' * 50}{RESET}")
