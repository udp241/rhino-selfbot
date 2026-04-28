"""
Text utilities. All of these post output to a channel by ID — they're
not bound to a "current channel" because we run from a CLI.

Usage pattern across this module:
    /<cmd> <channel_id> <args...>
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord

from utils.branding import error, success, info

if TYPE_CHECKING:
    from .handler import CommandHandler


# ---- helpers ----------------------------------------------------------

async def _resolve_channel(client: discord.Client, cid: int):
    ch = client.get_channel(cid)
    if ch is None:
        ch = await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("that channel can't be sent to")
    return ch


def _split_channel(args: list[str]) -> tuple[int, list[str]]:
    if not args:
        raise ValueError("missing channel id")
    return int(args[0]), args[1:]


# ---- the commands -----------------------------------------------------

async def clear_chat(handler: "CommandHandler", args: list[str]) -> None:
    """Push scrollback by sending one giant wall of newlines (V1 'clear' style)."""
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    # Hangul filler (\u3164) at start+end keeps Discord from collapsing the
    # trailing newlines, same trick V1 used. Single ~2000-char message.
    await ch.send("\u3164\n" + "\n" * 400 + "\u3164")


async def flood(handler: "CommandHandler", args: list[str]) -> None:
    """
    Push messages off-screen with walls of blank lines (V1 'clear' style,
    but across multiple messages).

    Usage: /flood <ch_id> [count]
    Default count: 10 messages.
    """
    import asyncio
    cid, rest = _split_channel(args)
    count = 10
    if rest and rest[0].isdigit():
        count = max(1, min(int(rest[0]), 50))

    ch = await _resolve_channel(handler.session, cid)

    # Hangul filler at start+end keeps Discord from collapsing the newlines
    # between them. Same trick V1's clear command used.
    body = "\u3164\n" + ("\n" * 400) + "\u3164"

    for _ in range(count):
        try:
            await ch.send(body)
        except Exception:
            await asyncio.sleep(2.0)
            continue
        await asyncio.sleep(1.0)  # stay under user-account rate limits


async def lmgtfy(handler: "CommandHandler", args: list[str]) -> None:
    """Send a let-me-google-that-for-you link."""
    from urllib.parse import urlencode
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /lmgtfy <ch_id> <query...>")
    q = urlencode({"q": " ".join(rest)})
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"<https://lmgtfy.app/?{q}>")


async def b64encode(handler: "CommandHandler", args: list[str]) -> None:
    import base64
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /encode <ch_id> <text...>")
    out = base64.b64encode(" ".join(rest).encode("utf-8")).decode("ascii")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"`{out}`")


async def b64decode(handler: "CommandHandler", args: list[str]) -> None:
    import base64
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /decode <ch_id> <base64...>")
    raw = " ".join(rest).strip()
    raw += "=" * (-len(raw) % 4)
    try:
        out = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"decode failed: {e}")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"`{out}`")


_LEET = str.maketrans({"a": "4", "A": "4", "e": "3", "E": "3",
                       "i": "1", "I": "1", "o": "0", "O": "0",
                       "s": "5", "S": "5", "t": "7", "T": "7"})


async def leet(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /leet <ch_id> <text...>")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"`{' '.join(rest).translate(_LEET)}`")


async def devowel(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /devowel <ch_id> <text...>")
    txt = " ".join(rest)
    out = "".join(c for c in txt if c.lower() not in "aeiou")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(out)


async def reverse_text(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /reverse <ch_id> <text...>")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(" ".join(rest)[::-1])


async def upper(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /upper <ch_id> <text...>")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(" ".join(rest).upper())


async def bold(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /bold <ch_id> <text...>")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"**{' '.join(rest)}**")


async def spoiler(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /spoiler <ch_id> <text...>")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"||{' '.join(rest)}||")


async def empty(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(chr(173))  # soft hyphen


async def shrug(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(r"¯\_(ツ)_/¯")


async def lenny(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send("( ͡° ͜ʖ ͡°)")


async def tableflip(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send("(╯°□°）╯︵ ┻━┻")


async def unflip(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send("┬─┬ ノ( ゜-゜ノ)")


async def ascii_art(handler: "CommandHandler", args: list[str]) -> None:
    """Generate ASCII art using pyfiglet (local; the old artii.herokuapp.com is dead)."""
    try:
        import pyfiglet
    except ImportError:
        raise RuntimeError("install pyfiglet first:  pip install pyfiglet")
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /ascii <ch_id> <text...>")
    art = pyfiglet.figlet_format(" ".join(rest))
    if len(art) > 1990:
        art = art[:1990]
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"```\n{art}\n```")


async def hastebin(handler: "CommandHandler", args: list[str]) -> None:
    """Upload to hastebin (works against the toptal-hosted version)."""
    import aiohttp
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /hastebin <ch_id> <content...>")
    body = " ".join(rest)
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.post("https://hastebin.com/documents", data=body.encode()) as resp:
            if resp.status != 200:
                raise RuntimeError(f"hastebin returned {resp.status}")
            data = await resp.json()
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(f"<https://hastebin.com/{data['key']}>")


async def junknick(handler: "CommandHandler", args: list[str]) -> None:
    """Set your own nickname in a guild to garbled unicode."""
    if not args:
        raise ValueError("usage: /junknick <guild_id>")
    gid = int(args[0])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    me = g.me
    glyph = "\u0d6f\u200b" * 30
    try:
        await me.edit(nick=glyph)
    except discord.HTTPException as e:
        raise RuntimeError(f"nick edit failed: {e}")
    success(f"nick set to junk in {g.name}")


async def address(handler: "CommandHandler", args: list[str]) -> None:
    """Generate fake US-style addresses. Local generator, no API."""
    cid, rest = _split_channel(args)
    count = 5
    if rest:
        try:
            count = max(1, min(20, int(rest[0])))
        except ValueError:
            pass
    streets = ["Maple St", "Oak Ave", "Cedar Ln", "Pine Rd", "Elm Dr",
               "Birch Way", "Willow Ct", "Ash Blvd", "Walnut Pl", "Spruce Cir"]
    cities = ["Springfield", "Riverside", "Franklin", "Greenville", "Bristol",
              "Clinton", "Madison", "Salem", "Georgetown", "Arlington"]
    states = ["NY", "CA", "TX", "FL", "PA", "OH", "GA", "NC", "MI", "IL"]
    out = []
    for _ in range(count):
        out.append(f"{random.randint(100, 9999)} {random.choice(streets)}, "
                   f"{random.choice(cities)}, {random.choice(states)} "
                   f"{random.randint(10000, 99999)}")
    ch = await _resolve_channel(handler.session, cid)
    await ch.send("```\n" + "\n".join(out) + "\n```")


async def combine_names(handler: "CommandHandler", args: list[str]) -> None:
    """Mash two names together."""
    cid, rest = _split_channel(args)
    if len(rest) < 2:
        raise ValueError("usage: /combine <ch_id> <name1> <name2>")
    n1, n2 = rest[0], rest[1]
    out = n1[:len(n1) // 2] + n2[len(n2) // 2:]
    ch = await _resolve_channel(handler.session, cid)
    await ch.send(out)


async def everyone_link(handler: "CommandHandler", args: list[str]) -> None:
    """The classic @everyone-in-URL meme."""
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    await ch.send("https://@everyone@google.com")


async def abc_anim(handler: "CommandHandler", args: list[str]) -> None:
    """Slow alphabet animation — sends 'a', edits to 'b', etc."""
    import asyncio
    cid, _ = _split_channel(args)
    ch = await _resolve_channel(handler.session, cid)
    letters = "abcdefghijklmnopqrstuvwxyz"
    msg = await ch.send(letters[0])
    for c in letters[1:]:
        await asyncio.sleep(2)
        try:
            await msg.edit(content=c)
        except discord.HTTPException:
            break


async def hidemention(handler: "CommandHandler", args: list[str]) -> None:
    """Embed a hidden message inside a visible one using zero-width chars.
    The hidden text rides between the visible chars as a sequence of
    U+200B / U+200C — copy-pasting the visible text out of Discord
    preserves the hidden bits, which can then be decoded.

    CLI:
        /hidemention <ch_id> <visible> | <hidden>

    The literal '|' separates the two halves. If only one half is given,
    the visible defaults to a single dot.
    """
    cid, rest = _split_channel(args)
    if not rest:
        raise ValueError("usage: /hidemention <ch_id> <visible> | <hidden>")

    raw = " ".join(rest)
    if "|" in raw:
        visible, _, hidden = raw.partition("|")
        visible = visible.strip() or "."
        hidden = hidden.strip()
    else:
        visible = "."
        hidden = raw.strip()

    if not hidden:
        raise ValueError("nothing to hide")

    # Encode each char of `hidden` as 8 zero-width bits (\u200B = 0, \u200C = 1)
    bits = []
    for ch in hidden.encode("utf-8"):
        for i in range(7, -1, -1):
            bits.append("\u200b" if (ch >> i) & 1 == 0 else "\u200c")
    payload = "".join(bits)

    # Splice the payload into the visible text so it doesn't all bunch at the end
    out_chars = list(visible)
    insert_at = max(1, len(out_chars) // 2)
    out_chars.insert(insert_at, payload)

    ch = await _resolve_channel(handler.session, cid)
    await ch.send("".join(out_chars))
