"""
Self-edit commands — anything that modifies your own account or your
own member presence in a guild.

CLI:
    /bio <text...>
    /globalname <text>
    /pfp <url|user_id>                    -- set avatar (from URL or by stealing a user's pfp)
    /pfp clear
    /banner <url>
    /banner clear
    /hypesquad <bravery|brilliance|balance>
    /cyclenick <guild_id> <text...>       -- animate your nickname char by char
    /stopcyclenick
    /nick <guild_id> <text>
    /color <ch_id> <hex>                  -- send a swatch image of a color
    /rolehex <guild_id> <role_id>
    /hwid                                 -- print local machine HWID
    /myav                                 -- show URLs to your own avatar/banner
    /reverseav <ch_id> [user_id]          -- reverse-image-search a user's avatar
    /av <ch_id> [user_id]                 -- send avatar as file
"""

from __future__ import annotations

import asyncio
import io
import platform
import subprocess
import uuid
from typing import TYPE_CHECKING, Optional

import aiohttp
import discord

from utils.branding import error, success, info, warn, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


# Module-level state for cyclenick
_cycling: dict[int, bool] = {}  # guild_id -> running flag


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


# ---- bio / global name ----------------------------------------------

async def bio(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /bio <text...>")
    new_bio = " ".join(args)
    try:
        await handler.session.user.edit(bio=new_bio)
    except discord.HTTPException as e:
        raise RuntimeError(f"bio edit failed: {e}")
    success(f"bio set: {GREY}{new_bio[:80]}{RESET}")


async def globalname(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /globalname <text>")
    name = " ".join(args)
    try:
        await handler.session.user.edit(global_name=name)
    except discord.HTTPException as e:
        raise RuntimeError(f"global_name edit failed: {e}")
    success(f"display name set: {WHITE}{name}{RESET}")


# ---- avatar (set / steal-from-user / clear) -------------------------

async def _read_url_bytes(url: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(url) as r:
            if r.status != 200:
                raise RuntimeError(f"download failed: {r.status}")
            return await r.read()


async def pfp(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /pfp <url|user_id|clear>")
    arg = args[0]
    if arg == "clear":
        await handler.session.user.edit(avatar=None)
        success("avatar cleared")
        return

    if arg.startswith("http"):
        url = arg
    else:
        # treat as user id — copy their avatar
        try:
            uid = int(arg)
        except ValueError:
            raise ValueError("not a URL or user id")
        target = handler.session.get_user(uid) or await handler.session.fetch_user(uid)
        if target.avatar is None:
            raise RuntimeError("that user has no custom avatar")
        url = target.display_avatar.url

    blob = await _read_url_bytes(url)
    try:
        await handler.session.user.edit(avatar=blob)
    except discord.HTTPException as e:
        raise RuntimeError(f"avatar edit failed: {e}")
    success(f"avatar set from {url}")


async def banner(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /banner <url|clear>")
    arg = args[0]
    if arg == "clear":
        await handler.session.user.edit(banner=None)
        success("banner cleared")
        return
    blob = await _read_url_bytes(arg)
    try:
        await handler.session.user.edit(banner=blob)
    except discord.HTTPException as e:
        raise RuntimeError(f"banner edit failed: {e} (Nitro required)")
    success("banner set")


# ---- hypesquad ------------------------------------------------------

async def hypesquad(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /hypesquad <bravery|brilliance|balance>")
    house_name = args[0].lower()
    house_map = {
        "bravery":    discord.HypeSquadHouse.bravery,
        "brilliance": discord.HypeSquadHouse.brilliance,
        "balance":    discord.HypeSquadHouse.balance,
    }
    if house_name not in house_map:
        raise ValueError("house must be: bravery, brilliance, or balance")
    try:
        await handler.session.user.edit(house=house_map[house_name])
    except discord.HTTPException as e:
        raise RuntimeError(f"hypesquad edit failed: {e}")
    success(f"hypesquad set to {house_name}")


# ---- cyclenick / stopcyclenick / nick -------------------------------

async def cyclenick(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /cyclenick <guild_id> <text...>")
    gid = int(args[0])
    text = " ".join(args[1:])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    me = g.me
    _cycling[gid] = True
    info(f"cycling nick in {g.name} (run /stopcyclenick to stop)")

    async def _loop():
        try:
            while _cycling.get(gid):
                buf = ""
                for ch in text:
                    if not _cycling.get(gid):
                        break
                    buf += ch
                    try:
                        await me.edit(nick=buf[:32])
                    except discord.HTTPException:
                        break
                    await asyncio.sleep(1.2)
                await asyncio.sleep(2)
        finally:
            _cycling[gid] = False

    asyncio.create_task(_loop())


async def stopcyclenick(handler: "CommandHandler", args: list[str]) -> None:
    if args:
        gid = int(args[0])
        _cycling[gid] = False
    else:
        for k in list(_cycling.keys()):
            _cycling[k] = False
    success("cyclenick stopped")


async def nick(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /nick <guild_id> <text>")
    gid = int(args[0])
    text = " ".join(args[1:])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    try:
        await g.me.edit(nick=text)
    except discord.HTTPException as e:
        raise RuntimeError(f"nick edit failed: {e}")
    success(f"nick set in {g.name}")


# ---- color swatch ---------------------------------------------------

async def color(handler: "CommandHandler", args: list[str]) -> None:
    """Send a 200x90 image of a color hex."""
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("install Pillow first:  pip install Pillow")
    if len(args) < 2:
        raise ValueError("usage: /color <ch_id> <hex>")
    cid = int(args[0])
    hex_in = args[1].lstrip("#")
    if len(hex_in) != 6:
        raise ValueError("hex must be 6 chars (e.g. ff8800)")
    try:
        rgb = tuple(int(hex_in[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError("invalid hex")
    buf = io.BytesIO()
    Image.new("RGB", (200, 90), rgb).save(buf, format="PNG")
    buf.seek(0)
    ch = await _channel(handler.session, cid)
    await ch.send(content=f"**#{hex_in}**", file=discord.File(buf, "color.png"))


async def rolehex(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /rolehex <guild_id> <role_id>")
    gid, rid = int(args[0]), int(args[1])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    role = g.get_role(rid)
    if not role:
        raise RuntimeError("role not found")
    info(f"{role.name}: {role.color}")


# ---- hwid -----------------------------------------------------------

def _get_hwid() -> str:
    sysname = platform.system()
    try:
        if sysname == "Windows":
            out = subprocess.check_output(
                ["wmic", "csproduct", "get", "uuid"], stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                line = line.strip()
                if line and "UUID" not in line:
                    return line
        elif sysname == "Darwin":
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        else:
            try:
                with open("/etc/machine-id", "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
    except Exception:
        pass
    # Fallback: MAC-based UUID
    return str(uuid.UUID(int=uuid.getnode()))


async def hwid(handler: "CommandHandler", args: list[str]) -> None:
    info(f"HWID: {WHITE}{_get_hwid()}{RESET}")


# ---- avatar viewing -------------------------------------------------

async def myav(handler: "CommandHandler", args: list[str]) -> None:
    me = handler.session.user
    if me.avatar:
        info(f"avatar:  {me.avatar.url}")
    if getattr(me, "banner", None):
        info(f"banner:  {me.banner.url}")
    if not me.avatar and not getattr(me, "banner", None):
        info("(no custom avatar/banner)")


async def reverseav(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /reverseav <ch_id> [user_id]")
    cid = int(args[0])
    target_id = int(args[1]) if len(args) > 1 else handler.session.user.id
    user = handler.session.get_user(target_id) or await handler.session.fetch_user(target_id)
    av_url = user.display_avatar.url
    ch = await _channel(handler.session, cid)
    await ch.send(
        f"reverse search for {user}: "
        f"<https://images.google.com/searchbyimage?image_url={av_url}>"
    )


async def av_show(handler: "CommandHandler", args: list[str]) -> None:
    """Send a user's avatar to a channel as a file."""
    if not args:
        raise ValueError("usage: /av <ch_id> [user_id]")
    cid = int(args[0])
    target_id = int(args[1]) if len(args) > 1 else handler.session.user.id
    user = handler.session.get_user(target_id) or await handler.session.fetch_user(target_id)
    av = user.display_avatar
    fmt = "gif" if av.is_animated() else "png"
    blob = await _read_url_bytes(av.with_format(fmt).url)
    ch = await _channel(handler.session, cid)
    await ch.send(file=discord.File(io.BytesIO(blob), f"avatar.{fmt}"))


# ---- fakenet (add a fake third-party connection to your profile) ----

_FAKENET_TYPES = (
    "battlenet", "ebay", "epicgames", "facebook", "github", "instagram",
    "leagueoflegends", "paypal", "playstation", "reddit", "riotgames",
    "skype", "spotify", "steam", "tiktok", "twitch", "twitter", "xbox",
    "youtube",
)


async def fakenet(handler: "CommandHandler", args: list[str]) -> None:
    """Attach a fake third-party connection to your own profile."""
    if len(args) < 2:
        raise ValueError(
            "usage: /fakenet <type> <name>\n"
            f"  types: {', '.join(_FAKENET_TYPES)}"
        )
    conn_type, name = args[0].lower(), " ".join(args[1:])
    if conn_type not in _FAKENET_TYPES:
        raise ValueError(f"unknown type. valid: {', '.join(_FAKENET_TYPES)}")

    import random
    from discord.http import Route

    fake_id = str(random.randint(10_000_000, 99_999_999))
    payload = {"name": name, "visibility": 1}
    route = Route("PUT",
                  "/users/@me/connections/{type}/{id}",
                  type=conn_type, id=fake_id)
    try:
        await handler.session.http.request(route, json=payload)
    except discord.HTTPException as e:
        raise RuntimeError(f"connection add failed: {e}")
    success(f"added fake {conn_type} connection: {name} (id {fake_id})")


async def masscon(handler: "CommandHandler", args: list[str]) -> None:
    """Add many fake third-party connections to your OWN account.

    /masscon --confirm [count]   (default 25, max 50)

    Heads up: Discord auto-flags accounts with too many fake connections
    added too fast. This will likely get YOUR account hit.
    """
    if "--confirm" not in args:
        warn("this can flag YOUR OWN account. re-run with --confirm if you actually want it")
        return
    rest = [a for a in args if a != "--confirm"]
    count = int(rest[0]) if rest and rest[0].isdigit() else 25
    count = max(1, min(count, 50))

    import random, asyncio
    from discord.http import Route

    info(f"adding {count} fake connections to your account...")
    added = 0; failed = 0
    for _ in range(count):
        conn_type = random.choice(_FAKENET_TYPES)
        name = f"rhino_{random.randint(1000, 9999)}"
        fake_id = str(random.randint(10_000_000, 99_999_999))
        try:
            route = Route("PUT",
                          "/users/@me/connections/{type}/{id}",
                          type=conn_type, id=fake_id)
            await handler.session.http.request(route, json={"name": name, "visibility": 1})
            added += 1
            await asyncio.sleep(1.0)
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(2.0)
    info(f"added {added} fake connections, {failed} failed")


# ---- steal all pfps in a guild (download to ./exports/<gid>/) ------

async def stealallpfp(handler: "CommandHandler", args: list[str]) -> None:
    """Download every cached member's avatar in a guild."""
    if not args:
        raise ValueError("usage: /stealallpfp <guild_id>")
    gid = int(args[0])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")

    import asyncio
    from pathlib import Path

    out_dir = Path(__file__).resolve().parent.parent / "exports" / str(gid)
    out_dir.mkdir(parents=True, exist_ok=True)

    info(f"saving avatars from {g.name} -> {out_dir}")
    saved = 0; skipped = 0
    for m in g.members:
        if m.avatar is None:
            skipped += 1
            continue
        try:
            fmt = "gif" if m.avatar.is_animated() else "png"
            blob = await _read_url_bytes(m.avatar.with_format(fmt).url)
            out = out_dir / f"{m.id}.{fmt}"
            with open(out, "wb") as f:
                f.write(blob)
            saved += 1
            if saved % 25 == 0:
                info(f"  ... {saved}")
        except Exception as e:
            error(f"  {m}: {e}")
        await asyncio.sleep(0.5)
    success(f"saved {saved}, skipped {skipped} (default avatars)")
