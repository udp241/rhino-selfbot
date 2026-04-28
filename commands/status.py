"""
Status cycler. Rotate custom status / playing / streaming / listening / watching
through a configured list, on a timer.

CLI:
    /status add <type> <text>       -- type: playing|streaming|listening|watching|custom
    /status list
    /status del <id>
    /status interval <seconds>
    /status start
    /status stop
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import discord

from .db import kv_get, kv_set

if TYPE_CHECKING:
    from .handler import CommandHandler


_TYPES = {"playing", "streaming", "listening", "watching", "custom"}


@dataclass
class CyclerState:
    items: list[tuple[str, str]] = field(default_factory=list)  # (type, text)
    interval: int = 60
    running: bool = False
    task: Optional[asyncio.Task] = None
    idx: int = 0


# Module-level singleton (one cycler per process)
_state = CyclerState()


def _serialize(items: list[tuple[str, str]]) -> str:
    return "\n".join(f"{t}|{x}" for t, x in items)


def _deserialize(s: str) -> list[tuple[str, str]]:
    out = []
    for line in (s or "").splitlines():
        if "|" in line:
            t, x = line.split("|", 1)
            if t in _TYPES:
                out.append((t, x))
    return out


def _save() -> None:
    kv_set("status_items", _serialize(_state.items))
    kv_set("status_interval", str(_state.interval))
    kv_set("status_running", "1" if _state.running else "0")


def _load() -> None:
    _state.items = _deserialize(kv_get("status_items", "") or "")
    try:
        _state.interval = int(kv_get("status_interval", "60") or "60")
    except ValueError:
        _state.interval = 60
    _state.running = (kv_get("status_running", "0") == "1")


def _make_activity(kind: str, text: str) -> Optional[discord.BaseActivity]:
    if kind == "playing":
        return discord.Activity(type=discord.ActivityType.playing, name=text)
    if kind == "streaming":
        return discord.Activity(type=discord.ActivityType.streaming, name=text, url="https://twitch.tv/discord")
    if kind == "listening":
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    if kind == "watching":
        return discord.Activity(type=discord.ActivityType.watching, name=text)
    if kind == "custom":
        return discord.CustomActivity(name=text)
    return None


async def _cycle_loop(handler: "CommandHandler") -> None:
    while _state.running:
        if not _state.items:
            await asyncio.sleep(_state.interval)
            continue
        kind, text = _state.items[_state.idx % len(_state.items)]
        _state.idx += 1
        try:
            activity = _make_activity(kind, text)
            await handler.session.change_presence(activity=activity)
        except Exception as e:
            print(f"[status_cycler] change_presence failed: {e}")
        await asyncio.sleep(_state.interval)


async def status_cmd(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /status <add|list|del|interval|start|stop>")
    sub, *rest = args

    if sub == "add":
        if len(rest) < 2:
            raise ValueError("usage: /status add <type> <text>")
        kind = rest[0].lower()
        if kind not in _TYPES:
            raise ValueError(f"type must be one of: {', '.join(_TYPES)}")
        text = " ".join(rest[1:])
        _state.items.append((kind, text))
        _save()
        print(f"added: [{kind}] {text}  (total: {len(_state.items)})")

    elif sub == "list":
        if not _state.items:
            print("(no statuses configured)")
            return
        for i, (t, x) in enumerate(_state.items):
            print(f"  #{i}  [{t}] {x}")
        print(f"interval: {_state.interval}s  |  running: {_state.running}")

    elif sub in ("del", "delete", "rm"):
        if not rest:
            raise ValueError("usage: /status del <index>")
        i = int(rest[0])
        if 0 <= i < len(_state.items):
            removed = _state.items.pop(i)
            _save()
            print(f"removed: {removed}")
        else:
            print("index out of range")

    elif sub == "interval":
        if not rest:
            raise ValueError("usage: /status interval <seconds>")
        secs = int(rest[0])
        if secs < 10:
            raise ValueError("interval must be at least 10 seconds")
        _state.interval = secs
        _save()
        print(f"interval set to {secs}s")

    elif sub == "start":
        if _state.running:
            print("already running")
            return
        _state.running = True
        _save()
        _state.task = asyncio.create_task(_cycle_loop(handler))
        print("status cycler started")

    elif sub == "stop":
        _state.running = False
        _save()
        if _state.task:
            _state.task.cancel()
            _state.task = None
        try:
            await handler.session.change_presence(activity=None)
        except Exception:
            pass
        print("status cycler stopped")

    else:
        raise ValueError(f"unknown status subcommand: {sub}")


async def autostart_if_configured(handler: "CommandHandler") -> None:
    """Called from on_ready. Resumes cycling if it was running before shutdown."""
    _load()
    if _state.running and _state.items:
        _state.task = asyncio.create_task(_cycle_loop(handler))
