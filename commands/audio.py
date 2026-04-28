"""
Audio commands. Currently just TTS (gTTS-based).

CLI:
    /tts <ch_id> <text...>     -- send a TTS .mp3 to a channel
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


async def tts(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /tts <ch_id> <text...>")
    try:
        from gtts import gTTS
    except ImportError:
        raise RuntimeError("install gTTS:  pip install gTTS")
    cid = int(args[0])
    text = " ".join(args[1:])
    buf = io.BytesIO()
    gTTS(text=text, lang="en").write_to_fp(buf)
    buf.seek(0)
    ch = await _channel(handler.session, cid)
    await ch.send(file=discord.File(buf, "tts.mp3"))
