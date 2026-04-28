"""
Affinity scores — Discord's algorithmic ranking of who/what you interact
with most. Useful for "who do I actually talk to" or "what server do I
spend the most time in."

CLI:
    /affinity users [--limit N]
    /affinity guilds [--limit N]
    /affinity channels [--limit N]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.branding import info, error, GREY, WHITE, YELLOW, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


def _fmt_score(s):
    if isinstance(s, (int, float)):
        return f"{s:>8.4f}"
    return f"{str(s):>8}"


async def affinity_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /affinity <users|guilds|channels> [--limit N]")
    kind, *rest = args
    client = handler.session

    limit = 25
    i = 0
    while i < len(rest):
        if rest[i] == "--limit":
            limit = int(rest[i + 1]); i += 2
        else:
            i += 1

    if kind == "users":
        if not hasattr(client, "user_affinities"):
            raise RuntimeError("user_affinities not available")
        affinities = await client.user_affinities()
        info(f"Top users (top {WHITE}{limit}{RESET}):")
        for a in list(affinities)[:limit]:
            score = getattr(a, "affinity", None) or getattr(a, "score", "?")
            uid = getattr(a, "user_id", None) or getattr(getattr(a, "user", None), "id", "?")
            user = client.get_user(uid) if uid != "?" else None
            name = str(user) if user else f"<id:{uid}>"
            print(f"  {YELLOW}{_fmt_score(score)}{RESET}  {GREY}{uid}{RESET}  {name}")
        return

    if kind == "guilds":
        if not hasattr(client, "guild_affinities"):
            raise RuntimeError("guild_affinities not available")
        affinities = await client.guild_affinities()
        info(f"Top guilds (top {WHITE}{limit}{RESET}):")
        for a in list(affinities)[:limit]:
            score = getattr(a, "affinity", None) or getattr(a, "score", "?")
            gid = getattr(a, "guild_id", None) or getattr(getattr(a, "guild", None), "id", "?")
            guild = client.get_guild(gid) if gid != "?" else None
            name = guild.name if guild else f"<id:{gid}>"
            print(f"  {YELLOW}{_fmt_score(score)}{RESET}  {GREY}{gid}{RESET}  {name}")
        return

    if kind == "channels":
        if not hasattr(client, "channel_affinities"):
            raise RuntimeError("channel_affinities not available")
        affinities = await client.channel_affinities()
        info(f"Top channels (top {WHITE}{limit}{RESET}):")
        for a in list(affinities)[:limit]:
            score = getattr(a, "affinity", None) or getattr(a, "score", "?")
            cid = getattr(a, "channel_id", None) or getattr(getattr(a, "channel", None), "id", "?")
            ch = client.get_channel(cid) if cid != "?" else None
            name = getattr(ch, "name", None) or (str(ch) if ch else f"<id:{cid}>")
            print(f"  {YELLOW}{_fmt_score(score)}{RESET}  {GREY}{cid}{RESET}  #{name}")
        return

    raise ValueError(f"unknown affinity kind: {kind}")
