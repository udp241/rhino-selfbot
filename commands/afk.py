"""
AFK auto-reply. When toggled on, replies once per DM with a configurable
message, with a per-user cooldown so you never spam the same person.

CLI:
    /afk on [message]
    /afk off
    /afk msg <message>
    /afk cooldown <seconds>
    /afk status
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

from .db import kv_get, kv_set

if TYPE_CHECKING:
    from .handler import CommandHandler


@dataclass
class AFKState:
    enabled: bool = False
    message: str = "I'm currently AFK. I'll respond when I'm back."
    cooldown: int = 3600  # seconds per user
    last_reply: dict[int, float] = field(default_factory=dict)


_state = AFKState()


# Pre-baked AFK messages with your servers. Use `/afk preset <name>` to load.
# `<...>` around URLs suppresses Discord's embed unfurl so the reply doesn't
# balloon into three giant preview cards.
_PRESETS: dict[str, str] = {
    "clean": (
        "**afk rn**\n"
        "\n"
        "> join the community: <https://discord.gg/613>\n"
        "> telegram: <https://t.me/ncaheadquarters>\n"
        "> bot server: <https://discord.gg/nca>"
    ),
    "bullets": (
        "**i'm afk** — drop into one of these:\n"
        "\n"
        "• community → <https://discord.gg/613>\n"
        "• telegram  → <https://t.me/ncaheadquarters>\n"
        "• bot server → <https://discord.gg/nca>\n"
        "\n"
        "back later."
    ),
    "minimal": (
        "i'm afk — join the community at <https://discord.gg/613>, "
        "telegram <https://t.me/ncaheadquarters>, "
        "and the bot server <https://discord.gg/nca>"
    ),
    "card": (
        "```ansi\n"
        "\u001b[1;36m  afk\u001b[0m\n"
        "```\n"
        "**community**  ·  <https://discord.gg/613>\n"
        "**telegram**   ·  <https://t.me/ncaheadquarters>\n"
        "**bot server** ·  <https://discord.gg/nca>"
    ),
    "default": "I'm currently AFK. I'll respond when I'm back.",
}


def _save() -> None:
    kv_set("afk_enabled", "1" if _state.enabled else "0")
    kv_set("afk_message", _state.message)
    kv_set("afk_cooldown", str(_state.cooldown))


def _load() -> None:
    _state.enabled = (kv_get("afk_enabled", "0") == "1")
    msg = kv_get("afk_message")
    if msg:
        _state.message = msg
    try:
        _state.cooldown = int(kv_get("afk_cooldown", "3600") or "3600")
    except ValueError:
        _state.cooldown = 3600


async def afk_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /afk <on|off|msg|preset|cooldown|status>")
    sub, *rest = args

    if sub == "preset":
        if not rest or rest[0] in ("list", "ls"):
            print("available presets:")
            for n, body in _PRESETS.items():
                preview = body.split("\n")[0][:60]
                print(f"  {n:<10}  {preview}")
            print()
            print("use:  /afk preset <n>")
            return
        name = rest[0].lower()
        if name not in _PRESETS:
            valid = ", ".join(_PRESETS.keys())
            raise ValueError(f"unknown preset '{name}'. valid: {valid}")
        _state.message = _PRESETS[name]
        _save()
        print(f"AFK message set from preset '{name}':")
        for line in _state.message.split("\n"):
            print(f"  {line}")
        return

    if sub == "on":
        _state.enabled = True
        if rest:
            _state.message = " ".join(rest)
        _state.last_reply.clear()
        _save()
        print(f"AFK on. message: {_state.message!r}")

    elif sub == "off":
        _state.enabled = False
        _state.last_reply.clear()
        _save()
        print("AFK off")

    elif sub == "msg":
        if not rest:
            raise ValueError("usage: /afk msg <message>   (use \\n for newlines)")
        # Interpret literal `\n` and `\t` so multi-line/formatted messages
        # are settable from one CLI line.
        raw = " ".join(rest)
        msg = raw.replace("\\n", "\n").replace("\\t", "\t")
        _state.message = msg
        _save()
        print(f"AFK message updated:")
        for line in msg.split("\n"):
            print(f"  {line}")

    elif sub == "cooldown":
        if not rest:
            raise ValueError("usage: /afk cooldown <seconds>")
        _state.cooldown = max(60, int(rest[0]))
        _save()
        print(f"cooldown set to {_state.cooldown}s")

    elif sub == "status":
        print(f"enabled:  {_state.enabled}")
        print(f"message:  {_state.message!r}")
        print(f"cooldown: {_state.cooldown}s")

    else:
        raise ValueError(f"unknown afk subcommand: {sub}")


async def maybe_auto_reply(client: discord.Client, message: discord.Message) -> None:
    """Called from on_message. Only replies in DMs, only when AFK on, with cooldown."""
    if not _state.enabled:
        return
    if message.author.id == client.user.id:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return

    now = time.time()
    last = _state.last_reply.get(message.author.id, 0)
    if now - last < _state.cooldown:
        return

    # Reserve the cooldown slot BEFORE the network call. discord.py-self
    # dispatches each on_message event in its own asyncio task, so two
    # messages arriving within ~100ms can land in two handlers running
    # concurrently. Without this reservation, both handlers read
    # last_reply == 0, both pass the cooldown check, and both send a
    # reply — which is the duplicate-AFK-message bug. Writing the
    # timestamp first ensures the second handler bails on the cooldown
    # check while the first one is still awaiting the HTTP send.
    _state.last_reply[message.author.id] = now
    try:
        await message.channel.send(_state.message)
    except discord.HTTPException:
        # The send failed (network blip, recipient blocked us, etc.).
        # Roll back the reservation so the user gets another reply on
        # their next message rather than waiting out the full cooldown
        # for a reply that never arrived.
        _state.last_reply.pop(message.author.id, None)


def load_on_startup() -> None:
    _load()
