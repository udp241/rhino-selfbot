"""
Lookup commands — weather, crypto, IP geolocation, MAC, URL shorteners,
joke/advice/topic prompts, proxy scrape.

All inline-printable to a channel by ID.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import discord

from utils.branding import error, success, info, text_embed, GREY, WHITE, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def _api_keys() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


async def _channel(client: discord.Client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


def _split(args: list[str]) -> tuple[int, list[str]]:
    if not args:
        raise ValueError("missing channel id")
    return int(args[0]), args[1:]


# ---- weather (OpenWeatherMap) ----------------------------------------

async def weather(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /weather <ch_id> <city...>")
    city = " ".join(rest)
    key = _api_keys().get("openweather_key", "")
    if not key:
        raise RuntimeError("set 'openweather_key' in config.json (https://openweathermap.org/api)")

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={key}"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"upstream {resp.status}")
            d = await resp.json()
    main = d.get("main", {})
    msg = text_embed(
        title=f"Weather: {d.get('name', city)}",
        fields=[
            ("Temp",     f"`{main.get('temp')}°C`"),
            ("Min/Max",  f"`{main.get('temp_min')}° / {main.get('temp_max')}°`"),
            ("Humidity", f"`{main.get('humidity')}%`"),
            ("Wind",     f"`{d.get('wind', {}).get('speed')} m/s`"),
            ("Sky",      f"`{d.get('weather', [{}])[0].get('main', '?')}`"),
        ],
    )
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- URL shorteners --------------------------------------------------

# ---- URL shorteners --------------------------------------------------
#
# `shorten` is the unified entry point. It picks one of three services:
#   shorten <ch_id> <url>                 -- defaults to tinyurl (no key)
#   shorten <ch_id> tinyurl <url>
#   shorten <ch_id> bitly <url>           -- requires bitly_key in config
#   shorten <ch_id> cuttly <url>          -- requires cuttly_key in config
#
# tinyurl/bitly/cuttly are kept as aliases that route into shorten with
# the service preselected.


async def _tinyurl_call(link: str) -> str:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(f"https://tinyurl.com/api-create.php?url={link}") as resp:
            return (await resp.text()).strip()


async def _bitly_call(link: str) -> str:
    key = _api_keys().get("bitly_key", "")
    if not key:
        raise RuntimeError("set 'bitly_key' in config.json")
    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"long_url": link}
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.post("https://api-ssl.bitly.com/v4/shorten",
                             headers=headers, json=payload) as resp:
            d = await resp.json()
    return d.get("link", "(no link returned)")


async def _cuttly_call(link: str) -> str:
    key = _api_keys().get("cuttly_key", "")
    if not key:
        raise RuntimeError("set 'cuttly_key' in config.json (free at cutt.ly)")
    timeout = aiohttp.ClientTimeout(total=10)
    url = f"https://cutt.ly/api/api.php?key={key}&short={link}"
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(url) as resp:
            d = await resp.json(content_type=None)
    return d.get("url", {}).get("shortLink", "(no link)")


_SHORTEN_SERVICES = {
    "tinyurl": _tinyurl_call,
    "bitly":   _bitly_call,
    "cuttly":  _cuttly_call,
}


async def shorten(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError(
            "usage: /shorten <ch_id> [tinyurl|bitly|cuttly] <url>"
        )

    # Service is the first arg if it matches a known one; otherwise default
    service = "tinyurl"
    if rest[0].lower() in _SHORTEN_SERVICES:
        service = rest[0].lower()
        rest = rest[1:]
    if not rest:
        raise ValueError("missing URL")
    link = rest[0]

    short = await _SHORTEN_SERVICES[service](link)
    ch = await _channel(handler.session, cid)
    await ch.send(short)


# Old per-service entry points kept as thin wrappers so existing callers
# (CLI, prefix dispatch, scripts) keep working.

async def tinyurl(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /tinyurl <ch_id> <link>")
    short = await _tinyurl_call(rest[0])
    ch = await _channel(handler.session, cid)
    await ch.send(short)


async def bitly(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /bitly <ch_id> <link>")
    short = await _bitly_call(rest[0])
    ch = await _channel(handler.session, cid)
    await ch.send(short)


async def cuttly(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /cuttly <ch_id> <link>")
    short = await _cuttly_call(rest[0])
    ch = await _channel(handler.session, cid)
    await ch.send(short)


# ---- crypto prices ---------------------------------------------------

async def _crypto(symbol: str) -> tuple[float, float]:
    timeout = aiohttp.ClientTimeout(total=10)
    url = f"https://min-api.cryptocompare.com/data/price?fsym={symbol}&tsyms=USD,EUR"
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(url) as resp:
            d = await resp.json()
    return float(d["USD"]), float(d["EUR"])


async def btc(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    usd, eur = await _crypto("BTC")
    msg = text_embed(title="Bitcoin", description=f"USD: `${usd:,.2f}`  •  EUR: `€{eur:,.2f}`")
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


async def eth(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    usd, eur = await _crypto("ETH")
    msg = text_embed(title="Ethereum", description=f"USD: `${usd:,.2f}`  •  EUR: `€{eur:,.2f}`")
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- IP geolocation (ip-api.com is free, no key) ---------------------

async def geoip(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /geoip <ch_id> <ip>")
    ip = rest[0]
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(f"http://ip-api.com/json/{ip}") as resp:
            d = await resp.json()
    if d.get("status") != "success":
        raise RuntimeError(d.get("message", "lookup failed"))
    fields = []
    for k in ("country", "regionName", "city", "zip", "isp", "org",
              "as", "lat", "lon", "timezone"):
        v = d.get(k)
        if v:
            fields.append((k, f"`{v}`"))
    msg = text_embed(title=f"GeoIP: {ip}", fields=fields)
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- MAC vendor lookup ----------------------------------------------

async def mac(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /mac <ch_id> <MAC>")
    addr = rest[0]
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(f"https://api.macvendors.com/{addr}") as resp:
            text = await resp.text()
    msg = text_embed(title=f"MAC: {addr}", description=f"`{text or '(no result)'}`")
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- pingweb ---------------------------------------------------------

async def pingweb(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /pingweb <ch_id> <url>")
    url = rest[0]
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.get(url) as resp:
                code = resp.status
    except Exception as e:
        raise RuntimeError(f"ping failed: {e}")
    state = "up" if 200 <= code < 400 else "down"
    ch = await _channel(handler.session, cid)
    await ch.send(f"`{url}` is **{state}** ({code})")


# ---- joke / advice / dad jokes --------------------------------------

async def joke(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get("https://icanhazdadjoke.com/", headers=headers) as resp:
            d = await resp.json()
    ch = await _channel(handler.session, cid)
    await ch.send(d.get("joke", "(no joke)"))


async def advice(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get("https://api.adviceslip.com/advice") as resp:
            d = await resp.json(content_type=None)
    ch = await _channel(handler.session, cid)
    await ch.send(d["slip"]["advice"])


# ---- conversation prompts (local lists; old API is dead) -------------

_TOPICS = [
    "What's the most interesting place you've been to?",
    "What show have you rewatched the most?",
    "If you could only eat one cuisine for a year, what would it be?",
    "Most useless skill you've mastered?",
    "What's a hill you'd die on?",
    "What's the worst job you've ever had?",
    "Describe yourself in three words.",
    "What's something popular you can't stand?",
    "What's the strangest dream you remember?",
    "What's the first concert you went to?",
]

_WYR = [
    ("Be invisible", "Be able to fly"),
    ("Have unlimited money but no friends", "Have great friends but be broke"),
    ("Always be 10 minutes late", "Always be 20 minutes early"),
    ("Speak every language", "Play every instrument"),
    ("Lose all your photos", "Lose all your contacts"),
    ("Have super speed", "Have super strength"),
    ("Live in space", "Live underwater"),
    ("Forget who you are", "Have everyone forget who you are"),
]


async def topic(handler: "CommandHandler", args: list[str]) -> None:
    import random
    cid, _ = _split(args)
    ch = await _channel(handler.session, cid)
    await ch.send(random.choice(_TOPICS))


async def wyr(handler: "CommandHandler", args: list[str]) -> None:
    import random
    cid, _ = _split(args)
    a, b = random.choice(_WYR)
    msg = text_embed(title="Would you rather", description=f"**A.** {a}\n**B.** {b}")
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- proxy scrape ----------------------------------------------------

PROXIES_DIR = Path(__file__).resolve().parent.parent / "exports" / "proxies"


async def proxies(handler: "CommandHandler", args: list[str]) -> None:
    """Scrape proxyscrape.com lists into ./exports/proxies/."""
    PROXIES_DIR.mkdir(parents=True, exist_ok=True)
    timeout = aiohttp.ClientTimeout(total=30)
    types = ("http", "socks4", "socks5")
    totals = {}
    async with aiohttp.ClientSession(timeout=timeout) as http:
        for t in types:
            url = ("https://api.proxyscrape.com/v2/?request=displayproxies"
                   f"&protocol={t}&timeout=2000&country=all")
            try:
                async with http.get(url) as resp:
                    txt = await resp.text()
            except Exception as e:
                error(f"{t}: {e}")
                continue
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            with open(PROXIES_DIR / f"{t}.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            totals[t] = len(lines)
    for t, n in totals.items():
        success(f"{t}: {n} proxies -> {PROXIES_DIR / f'{t}.txt'}")
