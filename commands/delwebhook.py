"""
Delete a Discord webhook given its URL.

Webhook URLs contain both the id and the token, which together act as
the webhook's auth — anyone holding the URL can post or delete it. This
is useful when you find a leaked webhook URL in a server you moderate
and want to immediately kill it before it can be abused.

CLI:
    /delwebhook <webhook_url>
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import aiohttp

from utils.branding import info, success, error

if TYPE_CHECKING:
    from .handler import CommandHandler


# Matches https://discord.com/api/webhooks/<id>/<token>
# (also accepts canary./ptb./discordapp.com hosts and trailing path bits)
_WEBHOOK_RE = re.compile(
    r"https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api(?:/v\d+)?"
    r"/webhooks/(\d+)/([A-Za-z0-9_\-]+)"
)


async def delwebhook(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /delwebhook <webhook_url>")
    url = args[0].strip()

    m = _WEBHOOK_RE.search(url)
    if not m:
        raise ValueError("that doesn't look like a webhook URL")

    wh_id, wh_token = m.group(1), m.group(2)
    target = f"https://discord.com/api/v10/webhooks/{wh_id}/{wh_token}"

    info(f"deleting webhook {wh_id}...")
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.delete(target) as resp:
            if resp.status == 204:
                success(f"webhook {wh_id} deleted")
                return
            if resp.status == 401:
                raise RuntimeError("401 — token is invalid (already deleted?)")
            if resp.status == 404:
                raise RuntimeError("404 — webhook not found (already deleted?)")
            body = (await resp.text())[:200]
            error(f"unexpected {resp.status}: {body}")
