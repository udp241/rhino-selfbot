"""
Prefix-based command invocation from inside Discord.

Wired into main.py's on_message: if the author is us and content starts
with the prefix, parse and run via the same CommandHandler used by the CLI.

Beyond plain dispatch, this layer handles:

  1. Mention expansion. <@123>, <@!123>, <#123>, <@&123> are stripped to
     their bare snowflake before the command sees them. So `$swat @user`
     and `$qs #general hi` work without typing IDs.

  2. Reply targeting. If you reply to someone's message and run a
     user-target command (`$swat`, `$kick`, etc) without an explicit
     user, the replied-to author is used.

  3. Channel/guild auto-injection. Commands whose first arg is a
     <ch_id> or <guild_id> have it filled in from the current
     channel/guild when not provided.

  4. Output capture. Terminal-style print/info/success/error from
     within commands is captured, ANSI-stripped, and posted back to the
     channel as a code block. Commands that already send their own
     messages (cat, weather, joke, swat...) emit nothing extra.

  5. Trigger-message deletion. The `$cmd ...` message is deleted after
     the command runs so chat stays clean.

  6. Help. `$help` and `$help <section>` render proper Discord embeds
     with all 140+ commands grouped by category.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import re
import sys
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


DEFAULT_PREFIX = "$"


# ---- which commands take a <ch_id> as their first positional arg ----

CHANNEL_FIRST_ARG = {
    # textfx
    "clearchat", "flood", "lmgtfy", "encode", "decode", "leet", "devowel",
    "reverse", "upper", "bold", "spoiler", "invis", "shrug", "lenny",
    "tableflip", "unflip", "ascii", "hastebin", "fakeaddress", "mashnames",
    "everyonelink", "abc", "hidemention",
    # audio
    "tts",
    # lookup
    "weather", "shorten", "tinyurl", "bitly", "cuttly", "btc", "eth", "geoip",
    "mac", "pingweb", "joke", "advice", "topic", "wyr",
    # memes
    "swat", "fry", "tweet", "dick", "howgay", "howfemboy", "tokengrab",
    "fakeipban", "gift", "hack", "faketoken", "fakenitro", "slot",
    "8ball", "minesweeper", "cat", "dog", "fox", "cum",
    # actions
    "hug", "pat", "kiss", "slap", "smug", "tickle", "feed",
    # selfedit
    "color", "av", "reverseav",
    # misc
    "qs", "qdel", "qr", "snipe", "typing", "changeregions",
    "guildicon", "guildbanner",
    # spam family
    "spam", "editall", "kickallgc",
    # bumping
    "bump", "autobump",
    # info / housekeeping
    "firstmsg", "clear",
}

GUILD_FIRST_ARG = {
    "junknick", "mashmembers", "cyclenick", "nick", "rolehex", "roleinfo",
    "serverinfo", "kick", "ban", "unban", "delroles", "delchannels",
    "massunban", "rainbow", "stoprainbow", "copyguild", "stealallpfp",
    "massban", "masskick", "masschannel", "massrole", "nuke", "dmguild",
    "guildrename", "fetchmembers",
}

# Commands that only make sense from the CLI — running them from prefix
# is either useless (output goes to terminal) or a footgun (HWID leaks
# into a chat channel). Reject these with a friendly hint.
CLI_ONLY = {
    "myav",   # prints your avatar URLs to terminal; $av posts to channel
    "cls",    # clears the CLI screen
    "hwid",   # leaks local machine HWID; never want this in chat
}

# Commands where a single user id is THE target of the command. If the
# trigger message is a reply and no user id was provided in args, the
# replied-to user fills the slot.
USER_TARGET_COMMANDS = {
    # memes (after auto-injected ch_id)
    "swat", "fry", "dick", "howgay", "howfemboy", "tokengrab", "fakeipban",
    "hack", "faketoken",
    # actions (after auto-injected ch_id)
    "hug", "pat", "kiss", "slap", "smug", "tickle", "feed",
    # admin (after auto-injected guild_id)
    "kick", "ban", "unban",
    # info (single arg)
    "whois", "profile", "dm",
    # selfedit (after auto-injected ch_id, optional user)
    "av", "reverseav",
}


# ---- patterns -------------------------------------------------------

_SNOWFLAKE = re.compile(r"^\d{17,20}$")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Discord mention forms — capture both the kind ('@', '@!', '@&', '#') and the id
_MENTION = re.compile(r"<(@[!&]?|#)(\d{17,20})>")


def _expand_mentions(args: list[str]) -> tuple[list[str], list[str]]:
    """
    Replace any Discord mention tokens with the bare snowflake AND return
    a parallel list of "kinds" so the dispatcher can tell a user mention
    apart from a channel mention (both look like bare snowflakes after
    expansion otherwise).

    kinds[i] is one of: 'channel', 'user', 'role', 'plain'.
    'plain' covers everything else (bare snowflakes, plain text, flags).
    """
    out_args: list[str] = []
    out_kinds: list[str] = []
    for a in args:
        m = _MENTION.fullmatch(a)
        if m:
            tag, snowflake = m.group(1), m.group(2)
            if tag == "#":
                kind = "channel"
            elif tag == "@&":
                kind = "role"
            else:
                kind = "user"
            out_args.append(snowflake)
            out_kinds.append(kind)
        else:
            out_args.append(_MENTION.sub(r"\2", a))
            out_kinds.append("plain")
    return out_args, out_kinds


def _replied_user_id(message: discord.Message) -> Optional[int]:
    """If this message is a reply to another, return that author's id."""
    ref = message.reference
    if ref is None:
        return None
    # Resolved object — fast path
    cached = getattr(ref, "resolved", None)
    if isinstance(cached, discord.Message):
        return cached.author.id
    # Reference exists but isn't resolved; we'd need to fetch
    return None


async def _resolve_replied_user(message: discord.Message) -> Optional[int]:
    """Async resolver that fetches the replied message if not cached."""
    uid = _replied_user_id(message)
    if uid is not None:
        return uid
    ref = message.reference
    if ref is None or ref.message_id is None:
        return None
    try:
        replied = await message.channel.fetch_message(ref.message_id)
        return replied.author.id
    except discord.HTTPException:
        return None


# ---- the dispatcher -------------------------------------------------

async def handle_prefix_message(
    handler: "CommandHandler",
    message: discord.Message,
    prefix: str = DEFAULT_PREFIX,
) -> bool:
    """Returns True if we tried to run a command, False otherwise."""
    content = message.content or ""
    if not content.startswith(prefix):
        return False

    body = content[len(prefix):].strip()
    if not body:
        return False

    parts = body.split()
    cmd_raw = parts[0].lower()
    raw_args = parts[1:]

    # Resolve aliases the same way the CLI does
    from .cli import _ALIASES
    cmd = _ALIASES.get(cmd_raw, cmd_raw)

    # CLI-only commands: print output to terminal, useless from chat,
    # or in HWID's case a security footgun. Reject early.
    if cmd in CLI_ONLY:
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await _reply(message, f"`{cmd}` is CLI-only — run it from the terminal")
        return True

    # Help is special — render a Discord embed instead of dispatching
    if cmd == "help":
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await _send_help_embed(message, raw_args, prefix)
        return True

    # 1. Expand all mentions, tracking kind per arg
    args, kinds = _expand_mentions(raw_args)

    # 2. Auto-inject channel id (if the command takes <ch_id> first).
    #    For commands where the user is the actual target (swat/dick/hug/...),
    #    we ALWAYS use the current channel unless an explicit <#channel>
    #    mention was passed — bare snowflakes are interpreted as the user
    #    target, not the channel.
    if cmd in CHANNEL_FIRST_ARG:
        if cmd in USER_TARGET_COMMANDS:
            # Only count an explicit <#> channel mention as "channel provided"
            first_is_channel = (args and kinds[0] == "channel")
        else:
            # Generic case: bare snowflakes count as channel ids
            first_is_channel = (
                args and _SNOWFLAKE.match(args[0]) and kinds[0] in ("plain", "channel")
            )
        if not first_is_channel:
            args = [str(message.channel.id)] + args
            kinds = ["plain"] + kinds
    elif cmd in GUILD_FIRST_ARG:
        first_is_guild = (
            args and _SNOWFLAKE.match(args[0]) and kinds[0] == "plain"
        )
        if not first_is_guild:
            if message.guild is None:
                await _reply(message, "this command needs a guild, we're in a DM")
                return True
            args = [str(message.guild.id)] + args
            kinds = ["plain"] + kinds

    # 3. Reply targeting: if this is a reply and the command takes a
    #    user, fill in the user slot from the reply target.
    if cmd in USER_TARGET_COMMANDS:
        is_ch_or_g_first = cmd in CHANNEL_FIRST_ARG or cmd in GUILD_FIRST_ARG
        slot = 1 if is_ch_or_g_first else 0
        slot_filled = (
            len(args) > slot
            and _SNOWFLAKE.match(args[slot])
            and kinds[slot] in ("plain", "user")
        )
        if not slot_filled:
            replied = await _resolve_replied_user(message)
            if replied is not None:
                args = args[:slot] + [str(replied)] + args[slot:]
                kinds = kinds[:slot] + ["plain"] + kinds[slot:]

    # 4. Delete the trigger message FIRST so it disappears instantly,
    #    rather than lingering while a long-running command (spam, autobump,
    #    abc animation, etc) does its thing. All info we needed off the
    #    trigger (reply target, mentions, channel, guild) is already
    #    captured above; the channel reference stays valid after delete.
    try:
        await message.delete()
    except discord.HTTPException:
        pass

    # 5. Run the command. We capture stdout so CLI status messages don't
    #    pollute the user's terminal — but neither stdout nor errors are
    #    relayed to chat. If a command needs to send something visible,
    #    it does so itself via ch.send(). Errors print to local stdout.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            await handler.process(cmd, args, message.guild)
    except ValueError as e:
        # Local-only — print to real stdout (the CLI), not to chat
        sys.__stdout__.write(f"prefix dispatch: {e}\n")
    except Exception as e:
        sys.__stdout__.write(f"prefix dispatch crashed: {type(e).__name__}: {e}\n")

    return True


async def _reply(message: discord.Message, content: str):
    try:
        await message.channel.send(content)
    except discord.HTTPException:
        pass


def _format_block(text: str) -> str:
    MAX = 1900
    if len(text) <= MAX:
        return f"```\n{text}\n```"
    return f"```\n{text[:MAX]}\n... (truncated)\n```"


# ---- help embeds ----------------------------------------------------

# Sections + commands. Keep these tight — one line each, no fluff.
# Format: (section_title, [(cmd_signature, short_desc), ...])

_HELP_SECTIONS = {
    "browse": ("Server / channel", [
        ("servers / s",                    "list guilds"),
        ("channels <gid>",                 "list channels"),
        ("enter <gid> / leave",            "set/clear current server"),
        ("watch <ch_id> / unwatch",        "live-print messages"),
        ("preview <gid>",                  "discoverable server preview"),
        ("serverinfo / si <gid>",          "guild info"),
        ("guildicon <gid>",                "post guild icon"),
        ("roleinfo / ri <gid> <rid>",      "role info"),
    ]),
    "voice": ("Voice / invites", [
        ("join / j <invite>",              "accept invite"),
        ("joinvc / vc <name>",             "join voice"),
        ("joincam <vc_id>",                "join voice with cam on"),
        ("rejoin",                         "toggle 5min auto-rejoin"),
    ]),
    "msgs": ("Message ops", [
        ("clear [N]",                      "delete YOUR msgs (DM, group, or guild)"),
        ("archive <id>",                   "dump DM to SQLite + files"),
        ("qs <ch_id> <msg>",               "quick send"),
        ("qdel <text>",                    "send + auto-delete after 5s"),
        ("qr <text>",                      "post a QR code PNG"),
        ("typing [seconds]",               "typing indicator (default 10s)"),
        ("snipe",                          "last deleted msg"),
        ("editall <ch_id> <text>",         "edit all your past msgs"),
        ("clearchat",                      "push scrollback"),
        ("flood",                          "whitespace wall"),
        ("tts <text>",                     "send TTS audio (gTTS)"),
        ("abc",                            "slow alphabet animation"),
    ]),
    "info": ("Info / lookup", [
        ("profile / p <uid>",              "rich profile"),
        ("whois <uid>",                    "basic user info"),
        ("firstmsg",                       "first msg in channel"),
        ("tokeninfo <token>",              "decode token (local)"),
        ("username <name>",                "Pomelo availability"),
        ("weather <city>",                 "OpenWeatherMap"),
        ("btc / eth",                      "crypto prices"),
        ("geoip <ip>",                     "IP geolocation"),
        ("mac <addr>",                     "MAC vendor"),
        ("pingweb <url>",                  "site up/down"),
        ("joke / advice / topic / wyr",    "chat starters"),
        ("shorten [svc] <link>",           "URL shorten (tinyurl|bitly|cuttly)"),
        ("proxies",                        "scrape proxy lists"),
        ("uptime / ping",                  "bot meta"),
    ]),
    "personal": ("Friends / personal", [
        ("friend / f list/pending/...",    "manage friends"),
        ("friend add/accept/decline/remove/block/unblock", ""),
        ("mentions list/clear/dismiss",    "recent @mentions"),
        ("mentions notify on/off",         "DM yourself when @mentioned"),
        ("dnote get/set/del/list <uid>",   "Discord-native notes"),
        ("note add/list/search/del",       "local notes"),
        ("bm add/list/del",                "bookmark messages"),
        ("remind <dur> <text>",            "set reminder"),
        ("reminders",                      "list pending"),
        ("sched <ch> <dur> <text>",        "post in channel later"),
        ("sched list / sched del <id>",    "manage scheduled"),
        ("copycat on/off/list <uid>",      "auto-mirror a user's messages"),
        ("avatars [dl]",                   "your avatar history; 'dl' to save"),
    ]),
    "presence": ("Account / presence", [
        ("account",                        "id, country, AFK..."),
        ("sessions",                       "active gateway sessions"),
        ("connections list/refresh",       "third-party links"),
        ("premium",                        "Nitro/boost status"),
        ("status add/list/start/stop",     "rotating status"),
        ("afk on/off/msg/preset/cooldown", "AFK auto-reply (DMs only)"),
        ("affinity users/guilds/channels", "top interactions"),
        ("game / stream / listening / watching <name>", "set activity"),
        ("clearactivity",                  "remove activity"),
        ("rpc set/show/start/stop",        "Rich Presence"),
        ("rpc template <n>",            "load preset RPC (cod, omori, etc.)"),
        ("btcstream start/stop",           "BTC price status"),
    ]),
    "selfedit": ("Self-edit", [
        ("bio <text>",                     "set bio"),
        ("globalname <text>",              "set display name"),
        ("pfp <url|uid|clear>",            "avatar"),
        ("banner <url|clear>",             "banner (Nitro)"),
        ("hypesquad <house>",              "bravery|brilliance|balance"),
        ("cyclenick <text>",               "animate nickname"),
        ("stopcyclenick",                  ""),
        ("nick <text>",                    "set guild nickname"),
        ("color <hex>",                    "post color swatch"),
        ("rolehex <rid>",                  "role color hex"),
        ("av [uid]",                       "send user's avatar (defaults to you)"),
        ("reverseav [uid]",                "google reverse search"),
        ("fakenet <type> <name>",          "fake third-party connection"),
        ("masscon --confirm [count]",      "bulk fake connections (own acct)"),
        ("stealallpfp <gid>",              "save all member pfps to disk"),
    ]),
    "admin": ("Server admin", [
        ("kick <uid> [reason]",            "kick member"),
        ("ban <uid> [reason]",             "ban member"),
        ("unban <uid>",                    "unban"),
        ("guildrename <name>",             "rename current guild"),
        ("guildbanner",                    "post current guild banner"),
        ("fetchmembers [count]",           "dump member list to ./exports"),
        ("delwebhook <url>",               "DELETE a leaked webhook by URL"),
        ("delroles --confirm",             "delete all non-default roles"),
        ("delchannels --confirm",          "delete all channels"),
        ("massunban --confirm",            "unban everyone"),
        ("massban --confirm",              "ban every member"),
        ("masskick --confirm",             "kick every member"),
        ("masschannel <n> [count]",     "bulk-create channels"),
        ("massrole <n> [count]",        "bulk-create roles"),
        ("nuke --confirm [--rename txt]",  "channels+roles+members teardown"),
        ("dmguild --confirm <msg>",        "DM every guild member"),
        ("rainbow <rid> / stoprainbow",    "cycle role color"),
        ("copyguild <src_gid>",            "duplicate structure"),
        ("changeregions <count>",          "cycle group call regions"),
    ]),
    "memes": ("Memes", [
        ("swat <uid>",                     ""),
        ("fry [uid]",                      "deepfry pfp"),
        ("tweet <user> <text>",            ""),
        ("dick [uid]",                     ""),
        ("howgay / howfemboy [uid]",       ""),
        ("tokengrab / fakeipban <uid>",    "text-only meme"),
        ("gift [poor|nerd|hit]",           ""),
        ("hack <uid>",                     ""),
        ("faketoken [uid]",                ""),
        ("fakenitro",                      "random gift code"),
        ("slot / 8ball / minesweeper",     ""),
        ("cat / dog / fox",                "random pic"),
        ("mashmembers",                    "mash 2 random member names"),
        ("cum",                            ""),
    ]),
    "actions": ("Action GIFs", [
        ("hug / pat / kiss <uid>",         ""),
        ("slap / smug / tickle <uid>",     ""),
        ("feed <uid>",                     ""),
    ]),
    "spam": ("Spam-family / DM cleanup", [
        ("spam <n> <msg>",                 "spam current channel"),
        ("dm <uid> <msg>",                 "single DM"),
        ("dmall <msg>",                    "DM friends list only"),
        ("closedm [bots]",                 "close DMs (all, or bot-only)"),
        ("groupleaver",                    "leave all group DMs"),
        ("kickallgc <gc_id>",              "clear group DM you own"),
    ]),
    "bumping": ("Bumping / backup", [
        ("bump [count]",                   "Disboard /bump (slash)"),
        ("autobump [count] / stopautobump", ""),
        ("backup save <gid>",              ""),
        ("backup list",                    ""),
        ("backup load <bid> <target_gid>", ""),
        ("backup delete <bid>",            ""),
    ]),

    "watch": ("Background listeners", [
        ("nitrosniper on/off/status",      "auto-redeem nitro codes seen in chat"),
        ("good on/off/addbad/listbad",     "auto-edit your bad words to wholesome"),
    ]),
    "textfx": ("Text fx / utilities", [
        ("encode / decode <text>",         "base64"),
        ("leet / devowel <text>",          ""),
        ("reverse / upper / bold <text>",  ""),
        ("spoiler <text>",                 ""),
        ("ascii <text>",                   "needs pyfiglet"),
        ("hastebin <text>",                ""),
        ("hidemention <vis> | <hidden>",   "embed hidden text via zero-width chars"),
        ("lmgtfy <query>",                 ""),
        ("fakeaddress [count]",            "fake addresses"),
        ("mashnames <a> <b>",              "mash two names"),
        ("invis / shrug / lenny",          "invisible char / shrug / lenny"),
        ("tableflip / unflip",             ""),
        ("everyonelink",                   ""),
        ("junknick",                       "garble own nickname"),
        ("relationships",                  "JSON dump of friends/blocked"),
        ("readall",                        "mark all read"),
        ("tr <target> <text>",             "translate"),
    ]),
}


def _build_overview_text(prefix: str) -> str:
    parts = [
        "**rhino-selfbot**",
        f"Prefix: `{prefix}`  •  Type `{prefix}help <section>` for one section.",
        "User mentions, channel mentions, and replies all work as targets.",
        "",
        "**Sections:**",
    ]
    for key, (title, items) in _HELP_SECTIONS.items():
        parts.append(f"`{prefix}help {key}` — {title} ({len(items)})")
    parts.append("")
    parts.append("-# discord.gg/nca  •  by @rhino241")
    return "\n".join(parts)


def _build_section_chunks(prefix: str, key: str) -> list[str]:
    """Return one or more message strings (each <2000 chars) for a section."""
    title, items = _HELP_SECTIONS[key]
    rows = []
    for sig, desc in items:
        if desc:
            rows.append(f"{prefix}{sig:<38}  {desc}")
        else:
            rows.append(f"{prefix}{sig}")

    # Build code-block chunks under 1900 chars each (Discord limit is 2000)
    chunks: list[str] = []
    header = f"**{title}**\n```\n"
    footer = "\n```"
    cur = header
    for r in rows:
        if len(cur) + len(r) + len(footer) + 1 > 1900:
            chunks.append(cur + footer)
            cur = "```\n" + r
        else:
            cur += ("\n" if cur != header else "") + r
    if cur != header:
        chunks.append(cur + footer)
    return chunks


async def _send_help_embed(message: discord.Message, args: list[str], prefix: str):
    if not args:
        try:
            await message.channel.send(_build_overview_text(prefix))
        except discord.HTTPException:
            pass
        return

    section = args[0].lower()
    if section not in _HELP_SECTIONS:
        # Fuzzy match any close section name
        matches = [k for k in _HELP_SECTIONS if k.startswith(section)]
        if len(matches) == 1:
            section = matches[0]
        else:
            valid = ", ".join(_HELP_SECTIONS.keys())
            await _reply(message, f"unknown section. valid: {valid}")
            return

    for chunk in _build_section_chunks(prefix, section):
        try:
            await message.channel.send(chunk)
        except discord.HTTPException:
            pass
