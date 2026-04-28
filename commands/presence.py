"""
Activity / presence setters and Rich Presence.

Simple activity setters (game, stream, listening, watching) replace your
current presence with a single named activity. The full Rich Presence
sub-system (rpc) builds a Discord-style game card with assets/buttons/etc.

CLI:
    /game <name...>
    /stream <url> <name...>
    /listening <name...>
    /watching <name...>
    /clearactivity

    /rpc set <field> <value...>     -- field ∈ name|details|state|large_image|
                                      large_text|small_image|small_text|button1|
                                      button1_url|button2|button2_url|app_id|type
    /rpc show
    /rpc start
    /rpc stop

    /btcstream start [interval_s]
    /btcstream stop
"""

from __future__ import annotations

import asyncio
import time
import datetime as dt
from typing import TYPE_CHECKING, Optional

import aiohttp
import discord

from .db import db, kv_get, kv_set
from utils.branding import error, success, info, GREY, WHITE, YELLOW, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


# ---- simple activity setters ----------------------------------------

async def set_game(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /game <name...>")
    await handler.session.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=" ".join(args)))
    success(f"playing: {WHITE}{' '.join(args)}{RESET}")


async def set_stream(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /stream <url> <name...>")
    url, name = args[0], " ".join(args[1:])
    await handler.session.change_presence(
        activity=discord.Activity(type=discord.ActivityType.streaming, name=name, url=url)
    )
    success(f"streaming: {WHITE}{name}{RESET}  ({url})")


async def set_listening(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /listening <name...>")
    a = discord.Activity(type=discord.ActivityType.listening, name=" ".join(args))
    await handler.session.change_presence(activity=a)
    success(f"listening to: {WHITE}{' '.join(args)}{RESET}")


async def set_watching(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /watching <name...>")
    a = discord.Activity(type=discord.ActivityType.watching, name=" ".join(args))
    await handler.session.change_presence(activity=a)
    success(f"watching: {WHITE}{' '.join(args)}{RESET}")


async def clear_activity(handler: "CommandHandler", args: list[str]) -> None:
    await handler.session.change_presence(activity=None)
    success("activity cleared")


# ---- Rich Presence --------------------------------------------------

# All RPC config persisted under kv keys "rpc.<field>"

_RPC_FIELDS = {
    "name", "details", "state",
    "large_image", "large_text",
    "small_image", "small_text",
    "button1", "button1_url",
    "button2", "button2_url",
    "app_id", "type",
}

_RPC_DEFAULTS = {
    "type": "playing",
    "app_id": "1193291951290712154",   # generic public app id (works for arbitrary RPC)
}

_rpc_running = False
_rpc_task: Optional[asyncio.Task] = None


def _rpc_get(field: str) -> Optional[str]:
    return kv_get(f"rpc.{field}", _RPC_DEFAULTS.get(field))


def _rpc_set(field: str, value: str) -> None:
    kv_set(f"rpc.{field}", value)


def _rpc_build_activity() -> Optional[discord.Activity]:
    name = _rpc_get("name")
    if not name:
        return None
    type_str = (_rpc_get("type") or "playing").lower()
    type_map = {
        "playing":   discord.ActivityType.playing,
        "streaming": discord.ActivityType.streaming,
        "listening": discord.ActivityType.listening,
        "watching":  discord.ActivityType.watching,
        "competing": discord.ActivityType.competing,
    }
    a_type = type_map.get(type_str, discord.ActivityType.playing)

    assets = {}
    for k in ("large_image", "large_text", "small_image", "small_text"):
        v = _rpc_get(k)
        if v:
            assets[k] = v

    buttons = []
    for n in ("1", "2"):
        label = _rpc_get(f"button{n}")
        url = _rpc_get(f"button{n}_url")
        if label and url:
            buttons.append({"label": label, "url": url})

    try:
        app_id_val = int(_rpc_get("app_id") or _RPC_DEFAULTS["app_id"])
    except ValueError:
        app_id_val = int(_RPC_DEFAULTS["app_id"])

    kwargs = {
        "type":           a_type,
        "name":           name,
        "details":        _rpc_get("details"),
        "state":          _rpc_get("state"),
        "timestamps":     {"start": int(time.time() * 1000)},
        "assets":         assets,
        "application_id": app_id_val,
    }
    if buttons:
        kwargs["buttons"] = buttons

    return discord.Activity(**{k: v for k, v in kwargs.items() if v is not None})


_RPC_TEMPLATES = {
    "hi": {
        "type": "playing",
        "name": "Hi !",
        "details": "hi !!!!!",
        "state": "",
    },
    "omori": {
        "type": "playing",
        "name": "Omori",
        "details": "In Game",
        "state": "Fighting a boss.",
    },
    "cod": {
        "type": "playing",
        "name": "Call of Duty",
        "details": "Multiplayer",
        "state": "Searching for game",
    },
    "fortnite": {
        "type": "playing",
        "name": "Fortnite",
        "details": "Battle Royale",
        "state": "In Lobby",
    },
    "code": {
        "type": "playing",
        "name": "Visual Studio Code",
        "details": "Editing main.py",
        "state": "Workspace: rhino-selfbot",
    },
    "spotify": {
        "type": "listening",
        "name": "Spotify",
        "details": "Some song",
        "state": "Some artist",
    },
    "vc": {
        "type": "watching",
        "name": "voice chat",
        "details": "lurking",
        "state": "discord.gg/nca",
    },
}


async def rpc(handler: "CommandHandler", args: list[str]) -> None:
    global _rpc_running, _rpc_task

    if not args:
        raise ValueError("usage: /rpc <set|show|start|stop|template> ...")
    sub, *rest = args

    if sub == "template":
        if not rest:
            info("templates: " + ", ".join(_RPC_TEMPLATES.keys()))
            info("usage: /rpc template <name>")
            return
        tname = rest[0].lower()
        if tname not in _RPC_TEMPLATES:
            raise ValueError(f"unknown template. valid: {', '.join(_RPC_TEMPLATES)}")
        # Wipe current rpc fields, set from template
        for f in _RPC_FIELDS:
            kv_set(f"rpc.{f}", "")
        for f, v in _RPC_TEMPLATES[tname].items():
            if v:
                _rpc_set(f, v)
        success(f"rpc template loaded: {tname}")
        info(f"  /rpc start  to push it")
        return

    if sub == "set":
        if len(rest) < 2:
            raise ValueError("usage: /rpc set <field> <value...>")
        field = rest[0]
        if field not in _RPC_FIELDS:
            raise ValueError(f"unknown field. valid: {', '.join(sorted(_RPC_FIELDS))}")
        value = " ".join(rest[1:])
        _rpc_set(field, value)
        success(f"rpc.{field} = {value}")
        return

    if sub == "show":
        for f in sorted(_RPC_FIELDS):
            v = _rpc_get(f)
            if v:
                print(f"  {YELLOW}{f:<14}{RESET} {v}")
        info(f"running: {_rpc_running}")
        return

    if sub == "start":
        if _rpc_running:
            info("already running")
            return
        activity = _rpc_build_activity()
        if not activity:
            raise RuntimeError("set at least 'name' first:  /rpc set name <text>")

        async def _push():
            try:
                await handler.session.change_presence(
                    status=discord.Status.online, activity=activity
                )
            except Exception as e:
                error(f"change_presence failed: {e}")

        _rpc_running = True
        _rpc_task = asyncio.create_task(_push())
        success("rpc started")
        return

    if sub == "stop":
        _rpc_running = False
        if _rpc_task:
            _rpc_task.cancel()
            _rpc_task = None
        try:
            await handler.session.change_presence(activity=None)
        except Exception:
            pass
        success("rpc stopped")
        return

    raise ValueError(f"unknown rpc subcommand: {sub}")


# ---- BTC stream (status that periodically updates with BTC price) ---

_btc_running = False
_btc_task: Optional[asyncio.Task] = None


async def _btc_loop(handler: "CommandHandler", interval: int):
    timeout = aiohttp.ClientTimeout(total=10)
    while _btc_running:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as http:
                async with http.get(
                    "https://min-api.cryptocompare.com/data/price?fsym=BTC&tsyms=USD"
                ) as r:
                    d = await r.json()
            usd = float(d["USD"])
            await handler.session.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name=f"BTC ${usd:,.2f}")
            )
        except Exception as e:
            error(f"btcstream tick: {e}")
        await asyncio.sleep(interval)


async def btcstream(handler: "CommandHandler", args: list[str]) -> None:
    global _btc_running, _btc_task
    if not args:
        raise ValueError("usage: /btcstream <start|stop> [interval_s]")
    sub = args[0]
    if sub == "start":
        if _btc_running:
            info("already running")
            return
        interval = int(args[1]) if len(args) > 1 else 60
        if interval < 30:
            raise ValueError("interval must be >= 30s (api rate limit)")
        _btc_running = True
        _btc_task = asyncio.create_task(_btc_loop(handler, interval))
        success(f"btcstream started (every {interval}s)")
        return
    if sub == "stop":
        _btc_running = False
        if _btc_task:
            _btc_task.cancel()
            _btc_task = None
        success("btcstream stopped")
        return
    raise ValueError(f"unknown btcstream subcommand: {sub}")
