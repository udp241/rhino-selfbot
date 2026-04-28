"""
Rhino Selfbot — entry point.
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import discord  # discord.py-self

from commands.handler import CommandHandler
from commands.cli import CLI
from commands.afk import maybe_auto_reply
from commands.snipe import record_delete
from commands.prefix import handle_prefix_message, DEFAULT_PREFIX
from commands.nitrosnipe import maybe_snipe as maybe_snipe_nitro
from commands.goodperson import maybe_correct as maybe_correct_good
from commands.copycat import maybe_mirror as maybe_copycat
from commands.mentions import maybe_notify_mention
from commands import meta as meta_mod
from utils.logging import setup_logging
from utils.branding import (
    banner, set_title, enable_ansi_on_windows,
    info, success, error, warn, hit,
    CYAN, CYAN_DIM, GREEN, GREY, WHITE, RESET,
)


CONFIG_PATH = Path(__file__).parent / "config.json"


def load_token() -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("token", "").strip()
        if token and token != "your_token_here":
            return token
    env = os.environ.get("DISCORD_TOKEN", "").strip()
    if env:
        return env
    error("No token found.")
    print(f"  Add it to {CONFIG_PATH} as {{\"token\": \"...\"}}")
    print(f"  or set the DISCORD_TOKEN environment variable.")
    sys.exit(1)


def load_prefix() -> str:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("prefix", "").strip()
            if p:
                return p
        except json.JSONDecodeError:
            pass
    return DEFAULT_PREFIX


def save_token(token: str) -> None:
    data = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    data["token"] = token
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class RhinoSelf(discord.Client):
    def __init__(self, prefix: str = DEFAULT_PREFIX):
        super().__init__(chunk_guilds_at_startup=False)
        self.prefix = prefix
        self.handler: CommandHandler | None = None
        self.cli: CLI | None = None

    async def on_ready(self):
        print(f"{CYAN}{'*' * 66}{RESET}")
        success(f"Logged in as {WHITE}{self.user}{RESET} {GREY}(id: {self.user.id}){RESET}")
        cc = getattr(self, "country_code", None)
        if cc:
            info(f"Country: {WHITE}{cc}{RESET}  Latency: {WHITE}{self.latency * 1000:.0f}ms{RESET}")
        info(f"Prefix: {WHITE}{self.prefix}{RESET}  (type {WHITE}{self.prefix}help{RESET} in any channel)")
        info(f"Connected to {WHITE}{len(self.guilds)}{RESET} server(s):")
        for g in self.guilds:
            print(f"    {CYAN_DIM}-{RESET} {g.name} {GREY}(id: {g.id}){RESET}")
        required = getattr(self, "required_action", None)
        if required:
            warn(f"Discord requires action: {required}")
        disclose = getattr(self, "disclose", None) or []
        if disclose:
            warn(f"Discord disclosures: {', '.join(disclose)}")
        print(f"{CYAN}{'*' * 66}{RESET}")
        set_title(f"Rhino Selfbot - {self.user}")
        if self.handler is None:
            self.handler = CommandHandler(self)
            self.cli = CLI(self, self.handler, save_token)
            asyncio.create_task(self.cli.run())

    async def on_message(self, message: discord.Message):
        if self.cli and self.cli.channel_viewer:
            self.cli.channel_viewer.maybe_add(message)
        await maybe_auto_reply(self, message)

        # Background listeners (only run if the user enabled them)
        try:
            await maybe_snipe_nitro(self, message)
        except Exception as e:
            error(f"nitrosniper crashed: {e}")
        try:
            await maybe_correct_good(self, message)
        except Exception as e:
            error(f"good crashed: {e}")
        try:
            await maybe_copycat(self, message)
        except Exception as e:
            error(f"copycat crashed: {e}")
        try:
            await maybe_notify_mention(self, message)
        except Exception as e:
            error(f"mention-notify crashed: {e}")

        # Prefix dispatcher: ONLY our own messages can trigger commands.
        if message.author.id == self.user.id and self.handler is not None:
            try:
                ran = await handle_prefix_message(self.handler, message, self.prefix)
                if ran:
                    return
            except Exception as e:
                error(f"prefix dispatch crashed: {e}")
            return

        # Other people's messages: ignored (selfbot, only owner runs commands).
        return

    async def on_message_delete(self, message: discord.Message):
        # Feed the snipe ring buffer
        try:
            record_delete(message)
        except Exception:
            pass


async def amain():
    enable_ansi_on_windows()
    set_title("Rhino is a God")
    print(banner())
    print()

    # Reset uptime clock to startup
    import datetime as _dt
    meta_mod.START_TIME = _dt.datetime.now(_dt.timezone.utc)

    setup_logging()
    token = load_token()
    prefix = load_prefix()
    client = RhinoSelf(prefix=prefix)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _signal():
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            pass

    info("Connecting to Discord...")
    runner = asyncio.create_task(client.start(token))
    waiter = asyncio.create_task(stop.wait())
    try:
        done, pending = await asyncio.wait(
            {runner, waiter}, return_when=asyncio.FIRST_COMPLETED
        )
    except discord.LoginFailure:
        hit("Login failure - token may be invalid or expired")
        return

    print()
    print(f"{CYAN}{'*' * 66}{RESET}")
    info("Shutting down...")
    print(f"{CYAN}{'*' * 66}{RESET}")
    await client.close()
    for t in pending:
        t.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
