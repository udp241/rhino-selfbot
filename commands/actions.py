"""
Action GIF commands. Uses the still-functional endpoints on nekos.life.

CLI:
    /hug <ch_id> <user_id>
    /pat <ch_id> <user_id>
    /kiss <ch_id> <user_id>
    /slap <ch_id> <user_id>
    /smug <ch_id> <user_id>
    /tickle <ch_id> <user_id>
    /feed <ch_id> <user_id>
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


async def _action(handler, args, endpoint: str, verb: str):
    if len(args) < 2:
        raise ValueError(f"usage: /{verb} <ch_id> <user_id>")
    cid, uid = int(args[0]), int(args[1])
    user = handler.session.get_user(uid) or await handler.session.fetch_user(uid)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(f"https://nekos.life/api/v2/img/{endpoint}") as r:
            d = await r.json()
    ch = await _channel(handler.session, cid)
    await ch.send(f"{user.mention} got a {verb} from {handler.session.user.mention}\n{d['url']}")


async def hug(handler, args):     await _action(handler, args, "hug",     "hug")
async def pat(handler, args):     await _action(handler, args, "pat",     "pat")
async def kiss(handler, args):    await _action(handler, args, "kiss",    "kiss")
async def slap(handler, args):    await _action(handler, args, "slap",    "slap")
async def smug(handler, args):    await _action(handler, args, "smug",    "smug")
async def tickle(handler, args):  await _action(handler, args, "tickle",  "tickle")
async def feed(handler, args):    await _action(handler, args, "feed",    "feed")
