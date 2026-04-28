"""
CommandHandler — single dispatch point for every CLI command.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import discord

# Existing modules
from .join         import join_invite
from .voice        import VoiceState, join_vc, toggle_rejoin, start_rejoin_monitor
from .clear        import clear
from .archive      import archive_dm
from .quicksend    import quicksend, qdel
from .info         import tokeninfo, whois, firstmsg
from .notes        import note, bookmark
from .reminders    import remind, list_reminders, reminder_ticker
from .scheduled    import sched, sched_ticker
from .qr           import qr_cmd
from .delwebhook   import delwebhook
from .copycat      import copycat_cmd
from .status       import status_cmd, autostart_if_configured as status_autostart
from .afk          import afk_cmd, load_on_startup as afk_load
from .export       import relationships_cmd, readall_cmd
from .translate    import translate
from .profile      import profile
from .friends      import friend_cmd
from .mentions     import mentions_cmd
from .sessions     import sessions_cmd
from .affinity     import affinity_cmd
from .connections  import connections_cmd
from .premium      import premium_cmd
from .discovery    import preview_cmd, username_cmd
from .avatars      import avatars_cmd
from .account      import account_cmd
from .dnotes       import dnote_cmd
from .typing       import typing_cmd

# New cluster modules
from . import textfx, lookup, memes, actions, selfedit, admin, presence
from . import spammers, bumping, backup as backup_mod, snipe
from . import audio, meta, nitrosnipe, goodperson


@dataclass
class CommandHandler:
    client: discord.Client
    voice_state: VoiceState = field(default_factory=VoiceState)
    _started_tasks: bool = False

    def __post_init__(self):
        if not self._started_tasks:
            asyncio.create_task(start_rejoin_monitor(self))
            asyncio.create_task(reminder_ticker(self))
            asyncio.create_task(sched_ticker(self))
            asyncio.create_task(self._post_init_async())
            self._started_tasks = True

    async def _post_init_async(self):
        await status_autostart(self)
        afk_load()

    @property
    def session(self) -> discord.Client:
        return self.client

    async def process(self, cmd: str, args: list[str], current_guild: Optional[discord.Guild]) -> None:
        # ---- voice / invites ----
        if cmd == "join":
            if not args: raise ValueError("usage: /join <invite>")
            await join_invite(self, args[0])
        elif cmd == "joinvc":
            if not args: raise ValueError("usage: /joinvc <vc_name>")
            if current_guild is None: raise ValueError("enter a server first")
            await join_vc(self, " ".join(args), current_guild)
        elif cmd == "rejoin":
            await toggle_rejoin(self)
        elif cmd == "joincam":
            from .voice import joincam
            await joincam(self, args)

        # ---- message ops ----
        elif cmd == "clear":        await clear(self, args)
        elif cmd == "archive":      await archive_dm(self, args)
        elif cmd == "qs":           await quicksend(self, args)
        elif cmd == "qdel":         await qdel(self, args)
        elif cmd == "qr":           await qr_cmd(self, args)
        elif cmd == "typing":       await typing_cmd(self, args)
        elif cmd == "snipe":        await snipe.snipe(self, args)
        elif cmd == "editall":      await spammers.editall(self, args)
        elif cmd == "hidemention":  await textfx.hidemention(self, args)

        # ---- info / lookup ----
        elif cmd == "tokeninfo":    await tokeninfo(self, args)
        elif cmd == "whois":        await whois(self, args)
        elif cmd == "profile":      await profile(self, args)
        elif cmd == "firstmsg":     await firstmsg(self, args)
        elif cmd == "preview":      await preview_cmd(self, args)
        elif cmd == "username":     await username_cmd(self, args)
        elif cmd == "weather":      await lookup.weather(self, args)
        elif cmd == "shorten":      await lookup.shorten(self, args)
        elif cmd == "tinyurl":      await lookup.tinyurl(self, args)
        elif cmd == "bitly":        await lookup.bitly(self, args)
        elif cmd == "cuttly":       await lookup.cuttly(self, args)
        elif cmd == "btc":          await lookup.btc(self, args)
        elif cmd == "eth":          await lookup.eth(self, args)
        elif cmd == "geoip":        await lookup.geoip(self, args)
        elif cmd == "mac":          await lookup.mac(self, args)
        elif cmd == "pingweb":      await lookup.pingweb(self, args)
        elif cmd == "joke":         await lookup.joke(self, args)
        elif cmd == "advice":       await lookup.advice(self, args)
        elif cmd == "topic":        await lookup.topic(self, args)
        elif cmd == "wyr":          await lookup.wyr(self, args)
        elif cmd == "proxies":      await lookup.proxies(self, args)

        # ---- text fx ----
        elif cmd == "clearchat":    await textfx.clear_chat(self, args)
        elif cmd == "flood":        await textfx.flood(self, args)
        elif cmd == "lmgtfy":       await textfx.lmgtfy(self, args)
        elif cmd == "encode":       await textfx.b64encode(self, args)
        elif cmd == "decode":       await textfx.b64decode(self, args)
        elif cmd == "leet":         await textfx.leet(self, args)
        elif cmd == "devowel":      await textfx.devowel(self, args)
        elif cmd == "reverse":      await textfx.reverse_text(self, args)
        elif cmd == "upper":        await textfx.upper(self, args)
        elif cmd == "bold":         await textfx.bold(self, args)
        elif cmd == "spoiler":      await textfx.spoiler(self, args)
        elif cmd == "invis":        await textfx.empty(self, args)
        elif cmd == "shrug":        await textfx.shrug(self, args)
        elif cmd == "lenny":        await textfx.lenny(self, args)
        elif cmd == "tableflip":    await textfx.tableflip(self, args)
        elif cmd == "unflip":       await textfx.unflip(self, args)
        elif cmd == "ascii":        await textfx.ascii_art(self, args)
        elif cmd == "hastebin":     await textfx.hastebin(self, args)
        elif cmd == "junknick":     await textfx.junknick(self, args)
        elif cmd == "fakeaddress":  await textfx.address(self, args)
        elif cmd == "mashnames":    await textfx.combine_names(self, args)
        elif cmd == "everyonelink": await textfx.everyone_link(self, args)
        elif cmd == "abc":          await textfx.abc_anim(self, args)

        # ---- audio ----
        elif cmd == "tts":          await audio.tts(self, args)

        # ---- bot meta ----
        elif cmd == "uptime":       await meta.uptime(self, args)
        elif cmd == "ping":         await meta.ping(self, args)
        elif cmd == "cls":          await meta.cls(self, args)

        # ---- nitro sniper / good person ----
        elif cmd == "nitrosniper":  await nitrosnipe.nitrosniper(self, args)
        elif cmd == "good":         await goodperson.good_cmd(self, args)

        # ---- memes ----
        elif cmd == "swat":         await memes.swat(self, args)
        elif cmd == "fry":          await memes.fry(self, args)
        elif cmd == "tweet":        await memes.tweet(self, args)
        elif cmd == "dick":         await memes.dick(self, args)
        elif cmd == "howgay":       await memes.howgay(self, args)
        elif cmd == "howfemboy":    await memes.howfemboy(self, args)
        elif cmd == "tokengrab":    await memes.tgrab(self, args)
        elif cmd == "fakeipban":    await memes.ipblacklist(self, args)
        elif cmd == "gift":         await memes.gift(self, args)
        elif cmd == "hack":         await memes.hack(self, args)
        elif cmd == "faketoken":    await memes.token_meme(self, args)
        elif cmd == "fakenitro":    await memes.nitro_meme(self, args)
        elif cmd == "slot":         await memes.slot(self, args)
        elif cmd == "8ball":        await memes.eightball(self, args)
        elif cmd == "minesweeper":  await memes.minesweeper(self, args)
        elif cmd == "cat":          await memes.cat_pic(self, args)
        elif cmd == "dog":          await memes.dog_pic(self, args)
        elif cmd == "fox":          await memes.fox_pic(self, args)
        elif cmd == "mashmembers":  await memes.genname(self, args)
        elif cmd == "cum":          await memes.cum(self, args)

        # ---- action gifs ----
        elif cmd == "hug":          await actions.hug(self, args)
        elif cmd == "pat":          await actions.pat(self, args)
        elif cmd == "kiss":         await actions.kiss(self, args)
        elif cmd == "slap":         await actions.slap(self, args)
        elif cmd == "smug":         await actions.smug(self, args)
        elif cmd == "tickle":       await actions.tickle(self, args)
        elif cmd == "feed":         await actions.feed(self, args)

        # ---- self-edit ----
        elif cmd == "bio":          await selfedit.bio(self, args)
        elif cmd == "globalname":   await selfedit.globalname(self, args)
        elif cmd == "pfp":          await selfedit.pfp(self, args)
        elif cmd == "banner":       await selfedit.banner(self, args)
        elif cmd == "hypesquad":    await selfedit.hypesquad(self, args)
        elif cmd == "cyclenick":    await selfedit.cyclenick(self, args)
        elif cmd == "stopcyclenick":await selfedit.stopcyclenick(self, args)
        elif cmd == "nick":         await selfedit.nick(self, args)
        elif cmd == "color":        await selfedit.color(self, args)
        elif cmd == "rolehex":      await selfedit.rolehex(self, args)
        elif cmd == "hwid":         await selfedit.hwid(self, args)
        elif cmd == "myav":         await selfedit.myav(self, args)
        elif cmd == "reverseav":    await selfedit.reverseav(self, args)
        elif cmd == "av":           await selfedit.av_show(self, args)
        elif cmd == "fakenet":      await selfedit.fakenet(self, args)
        elif cmd == "masscon":      await selfedit.masscon(self, args)
        elif cmd == "stealallpfp":  await selfedit.stealallpfp(self, args)

        # ---- admin ----
        elif cmd == "roleinfo":     await admin.roleinfo(self, args)
        elif cmd == "serverinfo":   await admin.serverinfo(self, args)
        elif cmd == "guildicon":    await admin.guildicon(self, args)
        elif cmd == "guildbanner":  await admin.guildbanner(self, args)
        elif cmd == "guildrename":  await admin.guildrename(self, args)
        elif cmd == "fetchmembers": await admin.fetchmembers(self, args)
        elif cmd == "delwebhook":   await delwebhook(self, args)
        elif cmd == "kick":         await admin.kick(self, args)
        elif cmd == "ban":          await admin.ban(self, args)
        elif cmd == "unban":        await admin.unban(self, args)
        elif cmd == "delroles":     await admin.delroles(self, args)
        elif cmd == "delchannels":  await admin.delchannels(self, args)
        elif cmd == "massunban":    await admin.massunban(self, args)
        elif cmd == "massban":      await admin.massban(self, args)
        elif cmd == "masskick":     await admin.masskick(self, args)
        elif cmd == "masschannel":  await admin.masschannel(self, args)
        elif cmd == "massrole":     await admin.massrole(self, args)
        elif cmd == "nuke":         await admin.nuke(self, args)
        elif cmd == "dmguild":      await admin.dmguild(self, args)
        elif cmd == "rainbow":      await admin.rainbow(self, args)
        elif cmd == "stoprainbow":  await admin.stoprainbow(self, args)
        elif cmd == "copyguild":    await admin.copyguild(self, args)
        elif cmd == "changeregions":await admin.changeregions(self, args)

        # ---- presence ----
        elif cmd == "game":         await presence.set_game(self, args)
        elif cmd == "stream":       await presence.set_stream(self, args)
        elif cmd == "listening":    await presence.set_listening(self, args)
        elif cmd == "watching":     await presence.set_watching(self, args)
        elif cmd == "clearactivity":await presence.clear_activity(self, args)
        elif cmd == "rpc":          await presence.rpc(self, args)
        elif cmd == "btcstream":    await presence.btcstream(self, args)

        # ---- spam-family / DM cleanup ----
        elif cmd == "spam":         await spammers.spam(self, args)
        elif cmd == "dm":           await spammers.dm(self, args)
        elif cmd == "dmall":        await spammers.dmall(self, args)
        elif cmd == "closedm":      await spammers.closedm(self, args)
        elif cmd == "botclosedm":   await spammers.closedm(self, ["bots"] + args)
        elif cmd == "groupleaver":  await spammers.groupleaver(self, args)
        elif cmd == "kickallgc":    await spammers.kickallgc(self, args)

        # ---- bumping ----
        elif cmd == "bump":         await bumping.bump(self, args)
        elif cmd == "autobump":     await bumping.autobump(self, args)
        elif cmd == "stopautobump": await bumping.stopautobump(self, args)

        # ---- backup ----
        elif cmd == "backup":       await backup_mod.backup(self, args)

        # ---- personal local ----
        elif cmd == "note":         await note(self, args)
        elif cmd == "bm":           await bookmark(self, args)
        elif cmd == "remind":       await remind(self, args)
        elif cmd == "reminders":    await list_reminders(self, args)
        elif cmd == "sched":        await sched(self, args)
        elif cmd == "copycat":      await copycat_cmd(self, args)

        # ---- discord-native personal ----
        elif cmd == "dnote":        await dnote_cmd(self, args)
        elif cmd == "friend":       await friend_cmd(self, args)
        elif cmd == "mentions":     await mentions_cmd(self, args)
        elif cmd == "avatars":      await avatars_cmd(self, args)

        # ---- presence/state ----
        elif cmd == "status":       await status_cmd(self, args)
        elif cmd == "afk":          await afk_cmd(self, args)
        elif cmd == "account":      await account_cmd(self, args)
        elif cmd == "sessions":     await sessions_cmd(self, args)

        # ---- account-wide ----
        elif cmd == "connections":  await connections_cmd(self, args)
        elif cmd == "premium":      await premium_cmd(self, args)
        elif cmd == "affinity":     await affinity_cmd(self, args)

        # ---- exports / utilities ----
        elif cmd == "relationships":await relationships_cmd(self, args)
        elif cmd == "readall":      await readall_cmd(self, args)
        elif cmd == "tr":           await translate(self, args)

        else:
            raise ValueError(f"unknown command: /{cmd}")
