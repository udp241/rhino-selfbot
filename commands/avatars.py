"""
View your avatar history.

CLI:
    /avatars
    /avatars dl                 -- save all to ./exports/avatars/
                                   ('download' also works)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord

from utils.branding import info, success, error, GREY, WHITE, YELLOW, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler

AVATAR_DIR = Path(__file__).resolve().parent.parent / "exports" / "avatars"


async def avatars_cmd(handler: "CommandHandler", args: list[str]) -> None:
    client = handler.session
    download = bool(args and args[0].lower() in ("dl", "download"))

    if not hasattr(client, "recent_avatars"):
        raise RuntimeError("recent_avatars not available")

    try:
        avatars = await client.recent_avatars()
    except discord.HTTPException as e:
        raise RuntimeError(f"fetch failed: {e}")

    info(f"Avatar history ({WHITE}{len(avatars)}{RESET}):")
    for i, av in enumerate(avatars):
        # Asset-like or dict-like — handle both
        url = getattr(av, "url", None) or (av.get("url") if isinstance(av, dict) else str(av))
        print(f"  {GREY}#{i:>2}{RESET}  {url}")

    if not download:
        return

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        for i, av in enumerate(avatars):
            url = getattr(av, "url", None) or (av.get("url") if isinstance(av, dict) else None)
            if not url:
                continue
            ext = ".gif" if ".gif" in url.lower() else ".png"
            local = AVATAR_DIR / f"avatar_{i:02d}{ext}"
            try:
                async with http.get(url) as resp:
                    if resp.status == 200:
                        with open(local, "wb") as f:
                            async for chunk in resp.content.iter_chunked(64 * 1024):
                                f.write(chunk)
                        success(f"saved {local}")
            except Exception as e:
                error(f"download #{i} failed: {e}")
            await asyncio.sleep(0.3)
