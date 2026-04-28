"""
'Good person' mode. When ON, watches your own outgoing messages, scans
for words on the badword list, and (if found) edits the message to one
of the wholesome replacements before anyone sees it.

Opt-in. Off by default. State persists via kv store.

CLI:
    /good on
    /good off
    /good status
    /good addbad <word>
    /good removebad <word>
    /good listbad
"""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

import discord

from .db import kv_get, kv_set
from utils.branding import success, info, error, warn, GREY, WHITE, GREEN, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


_KV_ENABLED = "good.enabled"
_KV_BADWORDS = "good.badwords"

# Default starter list — kept short on purpose
_DEFAULT_BAD = ["fuck", "shit", "bitch", "ass", "damn"]

_REPLACEMENTS = [
    "have a great day :)",
    "stay positive friends",
    "love everyone equally",
    "vibes only",
    "we are all winning today",
    "blessed to be here",
]


def is_enabled() -> bool:
    return (kv_get(_KV_ENABLED, "0") or "0") == "1"


def _get_badwords() -> list[str]:
    raw = kv_get(_KV_BADWORDS)
    if not raw:
        return list(_DEFAULT_BAD)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return list(_DEFAULT_BAD)


def _set_badwords(words: list[str]) -> None:
    kv_set(_KV_BADWORDS, json.dumps(sorted(set(words))))


async def maybe_correct(client: discord.Client, message: discord.Message) -> None:
    """Hook from main.py's on_message. Called for every message we send."""
    if not is_enabled():
        return
    if message.author.id != client.user.id:
        return
    content = (message.content or "").lower()
    if not content:
        return
    bad = _get_badwords()
    hits = [w for w in bad if w in content]
    if not hits:
        return
    try:
        await message.edit(content=random.choice(_REPLACEMENTS))
    except discord.HTTPException:
        pass


async def good_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        info(f"good: {GREEN if is_enabled() else GREY}{'ON' if is_enabled() else 'OFF'}{RESET}")
        info("usage: /good <on|off|status|addbad|removebad|listbad> ...")
        return
    sub, *rest = args

    if sub == "on":
        kv_set(_KV_ENABLED, "1")
        success("good ON — your bad words will get edited")
        return
    if sub == "off":
        kv_set(_KV_ENABLED, "0")
        success("good OFF")
        return
    if sub == "status":
        info(f"good: {GREEN if is_enabled() else GREY}{'ON' if is_enabled() else 'OFF'}{RESET}")
        info(f"badwords: {len(_get_badwords())} terms")
        return
    if sub == "addbad":
        if not rest:
            raise ValueError("usage: /good addbad <word>")
        words = _get_badwords()
        word = rest[0].lower()
        if word in words:
            info(f"already in list: {word}")
            return
        words.append(word)
        _set_badwords(words)
        success(f"added: {word}")
        return
    if sub == "removebad":
        if not rest:
            raise ValueError("usage: /good removebad <word>")
        words = _get_badwords()
        word = rest[0].lower()
        if word not in words:
            warn(f"not in list: {word}")
            return
        words.remove(word)
        _set_badwords(words)
        success(f"removed: {word}")
        return
    if sub == "listbad":
        words = _get_badwords()
        info(f"badwords ({len(words)}):")
        for w in words:
            print(f"  {GREY}{w}{RESET}")
        return

    raise ValueError(f"unknown subcommand: {sub}")
