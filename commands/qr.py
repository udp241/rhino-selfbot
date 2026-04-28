"""
QR code generator. Posts a PNG of the encoded text to a channel.
Useful for sharing wifi passwords, invite links, anything scannable.

CLI:
    /qr <ch_id> <text...>
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


async def qr_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /qr <ch_id> <text...>")

    cid = int(args[0])
    text = " ".join(args[1:])
    if not text:
        raise ValueError("nothing to encode")

    # Lazy import so missing-dep error is local to this command, not startup
    try:
        import qrcode
    except ImportError:
        raise RuntimeError("install qrcode:  pip install qrcode")

    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    client = handler.session
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")

    await ch.send(file=discord.File(buf, filename="qr.png"))
