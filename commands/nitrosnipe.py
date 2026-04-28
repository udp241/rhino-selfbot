"""
Nitro sniper. When ON, watches every incoming message for Discord gift
codes and tries to redeem them via the gift-code endpoint.

This is opt-in. State persists across restarts via the kv store.

CLI:
    /nitrosniper on
    /nitrosniper off
    /nitrosniper status
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord

from .db import kv_get, kv_set
from utils.branding import success, error, info, warn, GREY, WHITE, YELLOW, GREEN, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


# discord.gift/<code>, discord.com/gifts/<code>, discordapp.com/gifts/<code>
_GIFT_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gift|discord(?:app)?\.com/gifts)/([a-zA-Z0-9]{12,32})"
)

_KV_KEY = "nitrosniper.enabled"


def is_enabled() -> bool:
    return (kv_get(_KV_KEY, "0") or "0") == "1"


async def maybe_snipe(client: discord.Client, message: discord.Message) -> None:
    """Hook from main.py's on_message. Returns silently if disabled."""
    if not is_enabled():
        return
    # Don't try to redeem our own pasted codes
    if message.author.id == client.user.id:
        return
    matches = _GIFT_RE.findall(message.content or "")
    if not matches:
        return
    for code in matches:
        await _try_redeem(client, code, message)


async def _try_redeem(client: discord.Client, code: str, source: discord.Message):
    try:
        from discord.http import Route
    except ImportError:
        error("can't import discord.http.Route")
        return

    info(f"sniping gift {GREY}{code}{RESET}  (from {source.author})")

    # First fetch — confirms code is valid before we try to redeem
    try:
        check = Route("GET", "/entitlements/gift-codes/{code}", code=code)
        check_q = {"with_application": "false", "with_subscription_plan": "true"}
        await client.http.request(check, params=check_q)
    except discord.NotFound:
        warn(f"  invalid: {code}")
        return
    except discord.HTTPException as e:
        warn(f"  check failed: {e}")
        return

    # Redeem
    try:
        redeem = Route("POST", "/entitlements/gift-codes/{code}/redeem", code=code)
        await client.http.request(redeem, json={})
    except discord.HTTPException as e:
        # 400 / 403 generally = already claimed, you've used too many, or not eligible
        warn(f"  redeem failed: {e}")
        return
    success(f"  claimed nitro from {source.author}")


async def nitrosniper(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        info(f"sniper: {GREEN if is_enabled() else GREY}{'ON' if is_enabled() else 'OFF'}{RESET}")
        info("usage: /nitrosniper <on|off|status>")
        return
    sub = args[0].lower()
    if sub == "on":
        kv_set(_KV_KEY, "1")
        success("sniper ON")
        return
    if sub == "off":
        kv_set(_KV_KEY, "0")
        success("sniper OFF")
        return
    if sub == "status":
        info(f"sniper: {GREEN if is_enabled() else GREY}{'ON' if is_enabled() else 'OFF'}{RESET}")
        return
    raise ValueError(f"unknown subcommand: {sub}")
