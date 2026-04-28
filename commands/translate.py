"""
Translator. Uses a public Lingva instance (free, no API key).
If lingva.ml is down, swap LINGVA_HOST below to another public instance:
    https://github.com/thedaviddelta/lingva-translate#instances

CLI:
    /tr <target_lang> <text>      -- e.g. /tr es Hello world
    /tr <source>:<target> <text>  -- e.g. /tr en:fr Hello
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from .handler import CommandHandler


LINGVA_HOST = "https://lingva.ml"


async def translate(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /tr <target> <text>   or   /tr <src>:<tgt> <text>")

    spec = args[0]
    if ":" in spec:
        src, tgt = spec.split(":", 1)
    else:
        src, tgt = "auto", spec
    text = " ".join(args[1:])

    url = f"{LINGVA_HOST}/api/v1/{src}/{tgt}/{aiohttp.helpers.quote(text, safe='')}"

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        try:
            async with http.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"upstream returned {resp.status}")
                data = await resp.json()
        except Exception as e:
            raise RuntimeError(f"translation failed: {e}")

    translation = data.get("translation", "(no result)")
    print(f"  [{src} -> {tgt}] {translation}")
