"""
CLI — async stdin reader, command dispatch, sectioned help.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import discord

from utils.branding import (
    prompt as styled_prompt,
    info, success, error, warn,
    CYAN, CYAN_DIM, GREEN, RED, YELLOW, GREY, WHITE, RESET,
)


class ChannelViewer:
    def __init__(self):
        self.watching: bool = False
        self.channel_id: Optional[int] = None

    def maybe_add(self, msg: discord.Message) -> None:
        if not self.watching or self.channel_id is None:
            return
        if msg.channel.id != self.channel_id:
            return
        print(f"\n{CYAN_DIM}[#{msg.channel}]{RESET} "
              f"{WHITE}{msg.author}{RESET}{GREY}:{RESET} {msg.content}")


_ALIASES = {
    "h": "help", "?": "help",
    "s": "servers", "guilds": "servers",
    "c": "channels",
    "e": "enter",
    "w": "watch",
    "j": "join",
    "vc": "joinvc",
    "st": "settoken",
    "q": "exit", "quit": "exit",
    "p": "profile",
    "f": "friend",
    "ri": "roleinfo",
    "si": "serverinfo",
    # All cleanup commands route through `clear`
    "cleandm": "clear",
    "cleardm": "clear",
    "selfpurge": "clear",
    "purge": "clear",
    # Tier 2 renames — old names kept as aliases for muscle memory
    "tgrab":        "tokengrab",
    "ipblacklist":  "fakeipban",
    "emptychar":    "invis",
    "genname":      "mashmembers",
    "address":      "fakeaddress",
    "combine":      "mashnames",
    # Tier 3 — closedm consolidates closealldm; botclosedm stays separate
    # in dispatch since it injects an arg, but the alias maps both old
    # spellings here for completeness
    "closealldm":   "closedm",
    "userinfo": "whois",
    "ui": "whois",
    "av": "av",
    "8ball": "8ball",
}


_HELP = [
    ("Server / channel", [
        ("help",                          "command list  (alias: h)"),
        ("servers",                       "list all servers  (alias: s)"),
        ("channels <gid>",                "list channels in a server"),
        ("enter <gid>",                   "select a current server  (alias: e)"),
        ("leave",                         "clear selected server"),
        ("watch <ch_id>",                 "live-print messages  (alias: w)"),
        ("unwatch",                       "stop watching"),
        ("preview <gid>",                 "peek at a discoverable server"),
        ("serverinfo <gid>",              "guild info  (alias: si)"),
        ("guildicon <ch_id> <gid>",       "show guild icon in a channel"),
        ("roleinfo <gid> <rid>",          "role info  (alias: ri)"),
    ]),
    ("Voice / invites", [
        ("join <invite>",                 "accept invite  (alias: j)"),
        ("joinvc <name>",                 "join VC  (alias: vc)"),
        ("rejoin",                        "toggle 5-min auto-rejoin"),
    ]),
    ("Message ops", [
        ("clear <id> [N|flags]",          "delete YOUR msgs in DM/group/guild ch"),
        ("archive <id> [flags]",          "dump a DM to SQLite + files"),
        ("qs <ch_id> <msg...>",           "quick-send to channel by ID"),
        ("qdel <ch_id> [--seconds N] <msg...>", "send + auto-delete after N (default 5)"),
        ("qr <ch_id> <text...>",          "post a QR code PNG of <text>"),
        ("typing <ch_id> [seconds]",      "trigger typing indicator (default 10s)"),
        ("snipe <ch_id>",                 "last deleted message"),
        ("editall <ch_id> <text...>",     "edit all your past msgs in a channel"),
        ("clearchat <ch_id>",             "push scrollback (400 newlines)"),
        ("flood <ch_id>",                 "wall of invisible whitespace"),
    ]),
    ("Info / lookup", [
        ("profile <uid>",                 "rich profile  (alias: p)"),
        ("whois <uid>",                   "basic user info"),
        ("firstmsg <ch_id>",              "first message in a channel"),
        ("tokeninfo <token>",             "decode a token (local only)"),
        ("username <name>",               "Pomelo username availability"),
        ("weather <ch_id> <city>",        "OpenWeatherMap (needs key)"),
        ("btc <ch_id>",                   "BTC price"),
        ("eth <ch_id>",                   "ETH price"),
        ("geoip <ch_id> <ip>",            "IP geolocation"),
        ("mac <ch_id> <mac>",             "MAC vendor lookup"),
        ("pingweb <ch_id> <url>",         "is the site up?"),
        ("joke <ch_id>",                  "dad joke"),
        ("advice <ch_id>",                "random advice"),
        ("topic <ch_id>",                 "conversation topic"),
        ("wyr <ch_id>",                   "would-you-rather"),
        ("shorten <ch_id> [svc] <link>",  "URL shorten (tinyurl|bitly|cuttly)"),
        ("proxies",                       "scrape proxy lists to ./exports/proxies/"),
    ]),
    ("Friends / mentions / personal", [
        ("friend list/pending",           "manage friend list  (alias: f)"),
        ("friend add/accept/decline/remove/block/unblock", ""),
        ("mentions list/clear/dismiss",   "recent @mentions"),
        ("mentions notify on/off/status", "DM yourself when @mentioned"),
        ("dnote get/set/del/list",        "Discord-native per-user notes"),
        ("note add/list/search/del",      "your local notes"),
        ("bm add/list/del",               "bookmark Discord messages"),
        ("remind <dur> <text>",           "set a reminder"),
        ("reminders",                     "list pending reminders"),
        ("sched <ch_id> <dur> <text>",    "schedule a message in a channel"),
        ("sched list / sched del <id>",   "manage scheduled messages"),
        ("copycat on/off/list <uid>",     "auto-mirror a user's messages"),
        ("avatars [dl]",                  "your avatar history; 'dl' to save"),
    ]),
    ("Account / presence", [
        ("account",                       "summary: id, country, AFK, etc."),
        ("sessions",                      "active gateway sessions"),
        ("connections list/refresh",      "third-party connections"),
        ("premium [subs|boosts|slots]",   "Nitro / boost status"),
        ("status add/list/start/stop",    "rotating status cycler"),
        ("afk on/off/msg/preset/...",     "AFK auto-reply config"),
        ("affinity users/guilds/channels","top-interacted-with"),
        ("game <name...>",                "set a 'playing' activity"),
        ("stream <url> <name...>",        "set a streaming activity"),
        ("listening <name...>",           "set a listening activity"),
        ("watching <name...>",            "set a watching activity"),
        ("clearactivity",                 "remove activity"),
        ("rpc set/show/start/stop",       "full Rich Presence (assets/buttons)"),
        ("btcstream start/stop",          "rotating status with BTC price"),
    ]),
    ("Self-edit", [
        ("bio <text...>",                 "set your bio"),
        ("globalname <text>",             "set your display name"),
        ("pfp <url|uid|clear>",           "set/copy/clear avatar"),
        ("banner <url|clear>",            "set/clear banner (Nitro)"),
        ("hypesquad <bravery|brilliance|balance>", ""),
        ("cyclenick <gid> <text...>",     "animate your nickname"),
        ("stopcyclenick [gid]",           "stop nickname animation"),
        ("nick <gid> <text>",             "set your nickname in a guild"),
        ("color <ch_id> <hex>",           "post a color swatch image"),
        ("rolehex <gid> <rid>",           "show role color hex"),
        ("hwid",                          "print local machine HWID"),
        ("myav",                          "your avatar/banner URLs"),
        ("av <ch_id> [uid]",              "send a user's avatar to a channel"),
        ("reverseav <ch_id> [uid]",       "google reverse-image-search avatar"),
        ("fakenet <type> <n>",         "add a fake third-party connection"),
        ("masscon --confirm [count]",     "bulk fake connections (own account)"),
        ("stealallpfp <gid>",             "save all member pfps to ./exports/<gid>/"),
    ]),
    ("Server admin", [
        ("kick <gid> <uid> [reason...]",  "kick a member"),
        ("ban <gid> <uid> [reason...]",   "ban a member"),
        ("unban <gid> <uid>",             "unban a user"),
        ("guildrename <gid> <name...>",   "rename guild (Manage Server)"),
        ("guildbanner <ch_id> <gid>",     "post the guild's banner"),
        ("fetchmembers <gid> [count]",    "dump member list to ./exports/"),
        ("delwebhook <url>",              "delete a leaked webhook by URL"),
        ("delroles <gid> --confirm",      "delete all non-default roles"),
        ("delchannels <gid> --confirm",   "delete all channels"),
        ("massunban <gid> --confirm",     "unban every banned user"),
        ("massban <gid> --confirm",       "ban every member"),
        ("masskick <gid> --confirm",      "kick every member"),
        ("masschannel <gid> <n> [count]",  "bulk-create channels"),
        ("massrole <gid> <n> [count]",     "bulk-create roles"),
        ("nuke <gid> --confirm",          "delete channels+roles+ban all members"),
        ("dmguild <gid> --confirm <msg>", "DM every member of a guild"),
        ("rainbow <gid> <rid>",           "cycle a role's color"),
        ("stoprainbow <gid> <rid>",       ""),
        ("copyguild <src_gid>",           "duplicate guild structure into a new guild"),
        ("changeregions <ch_id> <count>", "cycle group DM call regions"),
    ]),
    ("Memes", [
        ("swat <ch_id> <uid>",            ""),
        ("fry <ch_id> [uid]",             "deepfry pfp"),
        ("tweet <ch_id> <user> <txt...>", ""),
        ("dick <ch_id> [uid]",            ""),
        ("howgay <ch_id> [uid|name]",     ""),
        ("howfemboy <ch_id> [uid|name]",  ""),
        ("tokengrab/fakeipban <ch_id> <uid>", "text-only meme"),
        ("gift <ch_id> [poor|nerd|hit]",  ""),
        ("hack <ch_id> <uid>",            ""),
        ("faketoken <ch_id> [uid]",       ""),
        ("fakenitro <ch_id>",             ""),
        ("slot/8ball/minesweeper <ch_id>","games"),
        ("cat/dog/fox <ch_id>",           "random animal pic"),
        ("mashmembers <ch_id> <gid>",     "mash 2 random member names"),
        ("cum <ch_id>",                   ""),
    ]),
    ("Action GIFs", [
        ("hug/pat/kiss/slap <ch_id> <uid>", ""),
        ("smug/tickle/feed <ch_id> <uid>",  ""),
    ]),
    ("Spam-family / DM cleanup", [
        ("spam <ch_id> <n> <msg...>",     "spam channel n times"),
        ("dm <uid> <msg...>",             "send a single DM"),
        ("dmall <msg...>",                "DM your friends list"),
        ("closedm [bots]",                "close 1-on-1 DMs (all, or bot-only)"),
        ("groupleaver",                   "leave all group DMs"),
        ("kickallgc <group_dm_id>",       "kick all from a group DM you own"),
    ]),
    ("Bumping / backup", [
        ("bump <ch_id> [count]",          "Disboard /bump (slash command)"),
        ("autobump <ch_id> [count]",      "post '!d bump' as text"),
        ("stopautobump",                  ""),
        ("backup save <gid>",             "save guild structure"),
        ("backup list",                   ""),
        ("backup load <bid> <target_gid>","restore into a guild"),
        ("backup delete <bid>",           ""),
    ]),
    ("Utilities / text fx", [
        ("encode/decode <ch_id> <txt>",   "base64"),
        ("leet/devowel <ch_id> <txt>",    ""),
        ("reverse/upper/bold <ch_id> <txt>", ""),
        ("spoiler <ch_id> <txt>",         ""),
        ("ascii <ch_id> <txt>",           "needs pyfiglet"),
        ("hastebin <ch_id> <txt>",        ""),
        ("hidemention <ch_id> <vis> | <hidden>", "embed hidden text via zero-width chars"),
        ("lmgtfy <ch_id> <query>",        ""),
        ("fakeaddress <ch_id> [count]",   "fake addresses"),
        ("mashnames <ch_id> <a> <b>",     "mash two names together"),
        ("invis/shrug/lenny <ch_id>",     "invisible char / ¯\\_(ツ)_/¯ / ( ͡° ͜ʖ ͡°)"),
        ("tableflip/unflip <ch_id>",      ""),
        ("everyonelink <ch_id>",          ""),
        ("junknick <gid>",                "set your own nick to garbled unicode"),
        ("relationships",                 "dump friends/blocked to JSON"),
        ("readall",                       "bulk_ack: mark everything as read"),
        ("tr <target> <text>",            "translate via Lingva"),
        ("settoken <token>",              "save token  (alias: st)"),
        ("exit",                          "quit  (aliases: quit, q)"),
    ]),
]


def _print_help() -> None:
    border = f"{CYAN}{'*' * 70}{RESET}"
    print(border)
    print(f"{CYAN}*{RESET}  {WHITE}Rhino Selfbot Command Reference{RESET}")
    print(border)
    for section, rows in _HELP:
        print(f"\n  {YELLOW}{section}{RESET}")
        for cmd, desc in rows:
            if cmd:
                print(f"    {GREEN}{cmd:<40}{RESET}  {GREY}{desc}{RESET}")
    print()
    print(border)


class CLI:
    def __init__(self, client: discord.Client, handler, save_token: Callable[[str], None]):
        self.client = client
        self.handler = handler
        self.save_token = save_token
        self.current_guild: Optional[discord.Guild] = None
        self.channel_viewer = ChannelViewer()

    async def _ainput(self, prompt: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))

    async def run(self):
        info(f"Type {GREEN}help{RESET} for commands.\n")
        while True:
            try:
                line = await self._ainput(styled_prompt())
            except (EOFError, KeyboardInterrupt):
                print()
                await self.client.close()
                return
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            cmd = _ALIASES.get(parts[0].lower(), parts[0].lower())
            args = parts[1:]
            try:
                await self._dispatch(cmd, args)
            except ValueError as e:
                error(str(e))
            except Exception as e:
                error(f"{type(e).__name__}: {e}")

    async def _dispatch(self, cmd: str, args: list[str]) -> None:
        if cmd == "help":
            _print_help(); return
        if cmd == "servers":
            self._list_servers(); return
        if cmd == "channels":
            if not args:
                error("usage: channels <gid>"); return
            self._list_channels(int(args[0])); return
        if cmd == "enter":
            if not args:
                error("usage: enter <gid>"); return
            g = self.client.get_guild(int(args[0]))
            if not g:
                error("server not found")
            else:
                self.current_guild = g
                success(f"entered: {WHITE}{g.name}{RESET}")
            return
        if cmd == "leave":
            self.current_guild = None
            info("left current server"); return
        if cmd == "watch":
            if not args:
                error("usage: watch <ch_id>"); return
            self.channel_viewer.channel_id = int(args[0])
            self.channel_viewer.watching = True
            success(f"watching channel {args[0]}"); return
        if cmd == "unwatch":
            self.channel_viewer.watching = False
            self.channel_viewer.channel_id = None
            info("stopped watching"); return
        if cmd == "settoken":
            if not args:
                error("usage: settoken <token>"); return
            self.save_token(args[0])
            success("token saved (restart to use it)"); return
        if cmd == "exit":
            await self.client.close(); return

        await self.handler.process(cmd, args, self.current_guild)

    def _list_servers(self):
        info(f"Servers ({WHITE}{len(self.client.guilds)}{RESET}):")
        for g in self.client.guilds:
            star = f"{GREEN}*{RESET}" if self.current_guild and g.id == self.current_guild.id else " "
            print(f"  {star} {GREY}{g.id}{RESET}  {g.name}")

    def _list_channels(self, gid: int):
        g = self.client.get_guild(gid)
        if not g:
            error("server not found"); return
        info(f"Channels in {WHITE}{g.name}{RESET}:")
        for c in g.channels:
            kind = type(c).__name__.replace("Channel", "").lower()
            print(f"    {CYAN_DIM}[{kind:>8}]{RESET}  {GREY}{c.id}{RESET}  {c.name}")
