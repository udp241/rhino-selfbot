"""
Friend request management.

CLI:
    /friend list                       -- list current friends
    /friend pending                    -- list incoming + outgoing requests
    /friend add <user_id|username>     -- send a friend request
    /friend accept <user_id>           -- accept an incoming request
    /friend decline <user_id>          -- decline an incoming or cancel an outgoing
    /friend remove <user_id>           -- unfriend
    /friend block <user_id>            -- block a user
    /friend unblock <user_id>          -- unblock a user
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, warn, GREEN, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


def _rel_type_value(rel) -> int | None:
    try:
        return getattr(rel.type, "value", rel.type)
    except AttributeError:
        return None


async def friend_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /friend <list|pending|add|accept|decline|remove|block|unblock>")
    sub, *rest = args
    client = handler.session

    if sub == "list":
        friends = list(getattr(client, "friends", []))
        info(f"Friends ({WHITE}{len(friends)}{RESET}):")
        for r in friends:
            u = r.user
            print(f"  {GREY}{u.id}{RESET}  {u}")
        return

    if sub == "pending":
        incoming, outgoing = [], []
        for r in getattr(client, "relationships", []):
            t = _rel_type_value(r)
            if t == 3:
                incoming.append(r.user)
            elif t == 4:
                outgoing.append(r.user)
        info(f"Incoming requests ({WHITE}{len(incoming)}{RESET}):")
        for u in incoming:
            print(f"  {GREY}{u.id}{RESET}  {u}")
        info(f"Outgoing requests ({WHITE}{len(outgoing)}{RESET}):")
        for u in outgoing:
            print(f"  {GREY}{u.id}{RESET}  {u}")
        return

    if sub == "add":
        if not rest:
            raise ValueError("usage: /friend add <user_id|username>")
        target = rest[0]
        try:
            uid = int(target)
            user = await client.fetch_user(uid)
            await client.send_friend_request(user)
        except ValueError:
            # username (pomelo) — pass the string directly
            await client.send_friend_request(target)
        except discord.HTTPException as e:
            raise RuntimeError(f"send failed: {e}")
        success(f"friend request sent to {target}")
        return

    if sub == "accept":
        if not rest:
            raise ValueError("usage: /friend accept <user_id>")
        uid = int(rest[0])
        rel = client.get_relationship(uid)
        if rel is None or _rel_type_value(rel) != 3:
            error("no incoming request from that user")
            return
        try:
            await rel.accept()
        except discord.HTTPException as e:
            raise RuntimeError(f"accept failed: {e}")
        success(f"accepted friend request from {rel.user}")
        return

    if sub in ("decline", "cancel"):
        if not rest:
            raise ValueError("usage: /friend decline <user_id>")
        uid = int(rest[0])
        rel = client.get_relationship(uid)
        if rel is None:
            error("no such relationship")
            return
        try:
            await rel.delete()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        success(f"removed {rel.user}")
        return

    if sub == "remove":
        if not rest:
            raise ValueError("usage: /friend remove <user_id>")
        uid = int(rest[0])
        rel = client.get_relationship(uid)
        if rel is None or _rel_type_value(rel) != 1:
            error("not friends with that user")
            return
        try:
            await rel.delete()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        success(f"unfriended {rel.user}")
        return

    if sub == "block":
        if not rest:
            raise ValueError("usage: /friend block <user_id>")
        uid = int(rest[0])
        try:
            user = await client.fetch_user(uid)
            await user.block()
        except discord.HTTPException as e:
            raise RuntimeError(f"block failed: {e}")
        success(f"blocked {user}")
        return

    if sub == "unblock":
        if not rest:
            raise ValueError("usage: /friend unblock <user_id>")
        uid = int(rest[0])
        rel = client.get_relationship(uid)
        if rel is None or _rel_type_value(rel) != 2:
            error("user is not blocked")
            return
        try:
            await rel.delete()
        except discord.HTTPException as e:
            raise RuntimeError(f"unblock failed: {e}")
        success(f"unblocked {rel.user}")
        return

    raise ValueError(f"unknown friend subcommand: {sub}")
