"""
Memes & games. All output to a channel by ID.

Commands:
    /swat <ch_id> <user_id>
    /fry <ch_id> [user_id]
    /tweet <ch_id> <username> <text...>
    /dick <ch_id> [user_id]
    /howgay <ch_id> [user_id|name]
    /howfemboy <ch_id> [user_id|name]
    /tgrab <ch_id> <user_id> [reason...]
    /ipblacklist <ch_id> <user_id> [reason...]
    /gift <ch_id> [type]                -- type ∈ poor/nerd/hit/random
    /hack <ch_id> <user_id>
    /token <ch_id> [user_id]            -- fake token from a user id
    /nitro <ch_id>                      -- random fake nitro-style code
    /slot <ch_id>
    /eightball <ch_id> <question...>
    /minesweeper <ch_id> [size]
    /cat <ch_id>
    /dog <ch_id>
    /fox <ch_id>
    /genname <ch_id> <guild_id>
    /cum <ch_id>
"""

from __future__ import annotations

import asyncio
import base64
import io
import random
from typing import TYPE_CHECKING

import aiohttp
import discord

from utils.branding import error, info, text_embed

if TYPE_CHECKING:
    from .handler import CommandHandler


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


def _split(args: list[str]) -> tuple[int, list[str]]:
    if not args:
        raise ValueError("missing channel id")
    return int(args[0]), args[1:]


async def _fetch_user(client, uid: int):
    u = client.get_user(uid)
    if u is None:
        u = await client.fetch_user(uid)
    return u


# ---- swat ------------------------------------------------------------

async def swat(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /swat <ch_id> <user_id>")
    user = await _fetch_user(handler.session, int(rest[0]))
    ch = await _channel(handler.session, cid)
    await ch.send(
        f"{user.mention} has been swatted by {handler.session.user.mention} 🚓\n"
        "https://media2.giphy.com/media/jmSjPi6soIoQCFwaXJ/giphy.gif"
    )


# ---- fry (deepfry pfp via nekobot) ----------------------------------

async def fry(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    target_id = int(rest[0]) if rest else handler.session.user.id
    user = await _fetch_user(handler.session, target_id)
    avatar_url = str(user.display_avatar.with_format("png").url)
    api = f"https://nekobot.xyz/api/imagegen?type=deepfry&image={avatar_url}"
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(api) as resp:
            d = await resp.json()
        async with http.get(d["message"]) as resp2:
            blob = await resp2.read()
    ch = await _channel(handler.session, cid)
    await ch.send(file=discord.File(io.BytesIO(blob), "fry.jpg"))


# ---- tweet image gen -------------------------------------------------

async def tweet(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if len(rest) < 2:
        raise ValueError("usage: /tweet <ch_id> <username> <text...>")
    username, text = rest[0], " ".join(rest[1:])
    api = f"https://nekobot.xyz/api/imagegen?type=tweet&username={username}&text={text}"
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get(api) as resp:
            d = await resp.json()
    ch = await _channel(handler.session, cid)
    await ch.send(d["message"])


# ---- dick ------------------------------------------------------------

async def dick(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    target_id = int(rest[0]) if rest else handler.session.user.id
    user = await _fetch_user(handler.session, target_id)
    size = random.randint(1, 15)
    ch = await _channel(handler.session, cid)
    await ch.send(f"**{user.display_name}'s size:**  `8{'=' * size}D`")


# ---- howgay / howfemboy ---------------------------------------------

async def _percent_meme(handler, args, label: str):
    cid, rest = _split(args)
    if rest:
        try:
            user = await _fetch_user(handler.session, int(rest[0]))
            target = user.mention
        except ValueError:
            target = " ".join(rest)
    else:
        target = handler.session.user.mention
    pct = random.randint(0, 100)
    ch = await _channel(handler.session, cid)
    await ch.send(f"{target} is **{pct}%** {label}")


async def howgay(handler: "CommandHandler", args: list[str]) -> None:
    await _percent_meme(handler, args, "gay :rainbow_flag:")


async def howfemboy(handler: "CommandHandler", args: list[str]) -> None:
    await _percent_meme(handler, args, "femboy")


# ---- tgrab / ipblacklist (text-only memes) --------------------------

async def tgrab(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /tgrab <ch_id> <user_id> [reason...]")
    user = await _fetch_user(handler.session, int(rest[0]))
    reason = " ".join(rest[1:]) or "unknown reason"
    ch = await _channel(handler.session, cid)
    await ch.send(f"```{user} has been token grabbed for {reason}```")


async def ipblacklist(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /ipblacklist <ch_id> <user_id> [reason...]")
    user = await _fetch_user(handler.session, int(rest[0]))
    reason = " ".join(rest[1:]) or "---"
    ch = await _channel(handler.session, cid)
    await ch.send(f"```{user} has been IP-blacklisted ({reason})```")


# ---- fake gift link --------------------------------------------------

async def gift(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    kind = rest[0] if rest else "random"
    presets = {
        "poor":  "discord.gift/vhnuzE2YkNCZ7sfYHHKebKXB",
        "nerd":  "discord.gift/Udzwm3hrQECQBnEEFFCEwdSq",
        "hit":   "discord.gift/BMHmv4FWEM5WVGnHUHCYFKMx",
    }
    if kind in presets:
        out = presets[kind]
    else:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        out = "discord.gift/" + "".join(random.choice(alphabet) for _ in range(16))
    ch = await _channel(handler.session, cid)
    await ch.send(out)


# ---- hack (silly fake hacking animation) ----------------------------

async def hack(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /hack <ch_id> <user_id>")
    user = await _fetch_user(handler.session, int(rest[0]))
    ch = await _channel(handler.session, cid)
    msg = await ch.send(f"--- hacking {user.mention} ---")
    await asyncio.sleep(2)
    await msg.edit(content="connecting to mainframe...")
    await asyncio.sleep(2)
    await msg.edit(content=f"found email: {user.name}@gmail.com")
    await asyncio.sleep(2)
    await msg.edit(content="bypassing 2FA...")
    await asyncio.sleep(2)
    await msg.edit(content=f"got {user.mention}'s account. ez")


# ---- fake token from a user id --------------------------------------

async def token_meme(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    target_id = int(rest[0]) if rest else handler.session.user.id
    encoded = base64.b64encode(str(target_id).encode("utf-8")).decode("ascii")
    ch = await _channel(handler.session, cid)
    await ch.send(f"`{encoded}.XxXxXx.{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=27))}`")


# ---- random nitro-style code (not a real claim) ---------------------

async def nitro_meme(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    pool = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    code = "".join(random.choice(pool) for _ in range(24))
    ch = await _channel(handler.session, cid)
    await ch.send(f"discord.gift/{code}")


# ---- slot ------------------------------------------------------------

async def slot(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    fruits = "🍎🍊🍐🍋🍉🍇🍓🍒"
    a, b, c = random.choice(fruits), random.choice(fruits), random.choice(fruits)
    line = f"[ {a} {b} {c} ]"
    if a == b == c:
        result = "JACKPOT"
    elif a == b or b == c or a == c:
        result = "two of a kind"
    else:
        result = "no match"
    ch = await _channel(handler.session, cid)
    await ch.send(f"**{line}** — {result}")


# ---- 8ball -----------------------------------------------------------

async def eightball(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /eightball <ch_id> <question...>")
    answers = [
        "definitely yes", "definitely not", "ask again later",
        "signs point to yes", "very doubtful", "without a doubt",
        "outlook good", "outlook not so good", "as I see it, yes",
        "reply hazy, try again",
    ]
    msg = text_embed(
        title="🎱 8-ball",
        fields=[
            ("Q", " ".join(rest)),
            ("A", random.choice(answers)),
        ],
    )
    ch = await _channel(handler.session, cid)
    await ch.send(msg)


# ---- minesweeper -----------------------------------------------------

async def minesweeper(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    size = 5
    if rest:
        try:
            size = max(2, min(8, int(rest[0])))
        except ValueError:
            pass
    bombs = {(random.randint(0, size - 1), random.randint(0, size - 1))
             for _ in range(size - 1)}
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    out = []
    for y in range(size):
        row = []
        for x in range(size):
            if (x, y) in bombs:
                row.append("||💣||")
            else:
                count = sum((x + dx, y + dy) in bombs
                            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                            if (dx, dy) != (0, 0))
                row.append(f"||{nums[count - 1] if count else '⬜'}||")
        out.append("".join(row))
    ch = await _channel(handler.session, cid)
    await ch.send("**Click to play:**\n" + "\n".join(out))


# ---- cat / dog / fox ------------------------------------------------

async def cat_pic(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get("https://api.thecatapi.com/v1/images/search") as r:
            d = await r.json()
    ch = await _channel(handler.session, cid)
    await ch.send(d[0]["url"])


async def dog_pic(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get("https://dog.ceo/api/breeds/image/random") as r:
            d = await r.json()
    ch = await _channel(handler.session, cid)
    await ch.send(d["message"])


async def fox_pic(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        async with http.get("https://randomfox.ca/floof/") as r:
            d = await r.json()
    ch = await _channel(handler.session, cid)
    await ch.send(d["image"])


# ---- genname (mash random member display names) --------------------

async def genname(handler: "CommandHandler", args: list[str]) -> None:
    cid, rest = _split(args)
    if not rest:
        raise ValueError("usage: /genname <ch_id> <guild_id>")
    g = handler.session.get_guild(int(rest[0]))
    if not g:
        raise RuntimeError("not in that guild")
    members = list(g.members)
    if len(members) < 2:
        raise RuntimeError("need at least 2 members cached in that guild")
    a, b = random.sample(members, 2)
    n1, n2 = a.display_name, b.display_name
    out = n2[:len(n2) // 2] + n1[len(n1) // 2:]
    ch = await _channel(handler.session, cid)
    await ch.send(discord.utils.escape_mentions(out))


# ---- cum (animated emoji meme, 9 frames) ----------------------------

async def cum(handler: "CommandHandler", args: list[str]) -> None:
    cid, _ = _split(args)
    ch = await _channel(handler.session, cid)
    frames = [
        '''
               :ok_hand:            :smile:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8=:punch:=D 
                :trumpet:      :eggplant:''',
        '''
                         :ok_hand:            :smiley:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8==:punch:D 
                :trumpet:      :eggplant:  
        ''',
        '''
                         :ok_hand:            :grimacing:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8=:punch:=D 
                :trumpet:      :eggplant:  
        ''',
        '''
                         :ok_hand:            :persevere:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8==:punch:D 
                :trumpet:      :eggplant:   
        ''',
        '''
                         :ok_hand:            :confounded:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8=:punch:=D 
                :trumpet:      :eggplant: 
        ''',
        '''
                          :ok_hand:            :tired_face:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8==:punch:D 
                :trumpet:      :eggplant:    
        ''',
        '''
                          :ok_hand:            :weary:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8=:punch:= D:sweat_drops:
                :trumpet:      :eggplant:        
        ''',
        '''
                          :ok_hand:            :dizzy_face:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8==:punch:D :sweat_drops:
                :trumpet:      :eggplant:                 :sweat_drops:
        ''',
        '''
                          :ok_hand:            :drooling_face:
      :eggplant: :zzz: :necktie: :eggplant: 
                      :oil:     :nose:
                    :zap: 8==:punch:D :sweat_drops:
                :trumpet:      :eggplant:                 :sweat_drops:
        ''',
    ]
    msg = await ch.send(frames[0])
    for f in frames[1:]:
        await asyncio.sleep(0.5)
        await msg.edit(content=f)
