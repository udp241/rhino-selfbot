"""
Voice channel logic — port of core/commands/joinvc.go.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import discord

if TYPE_CHECKING:
    from .handler import CommandHandler


@dataclass
class VoiceState:
    current_guild_id: Optional[int] = None
    current_channel_id: Optional[int] = None
    rejoin_enabled: bool = False
    voice_client: Optional[discord.VoiceClient] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_connected(self) -> bool:
        return bool(self.voice_client and self.voice_client.is_connected())


def _find_voice_channel(guild: discord.Guild, name: str) -> Optional[discord.VoiceChannel]:
    """Try exact (case-insensitive) match first, then substring."""
    name_lower = name.lower()
    voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]

    for ch in voice_channels:
        if ch.name.lower() == name_lower:
            return ch
    for ch in voice_channels:
        if name_lower in ch.name.lower():
            return ch
    return None


async def join_vc(handler: "CommandHandler", vc_name: str, guild: discord.Guild) -> None:
    if guild is None:
        raise RuntimeError("no server selected. Enter a server first")

    vc = _find_voice_channel(guild, vc_name)
    if vc is None:
        raise RuntimeError(f"voice channel '{vc_name}' not found")

    state = handler.voice_state

    async with state._lock:
        # Disconnect from current VC if connected
        if state.is_connected():
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                pass
            state.voice_client = None

        # Try to join
        try:
            voice_client = await vc.connect(timeout=10.0, reconnect=False, self_deaf=False, self_mute=False)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "voice connection timeout. This often occurs due to encryption mode "
                "issues with user tokens. Voice channels may not be fully supported "
                "with selfbots."
            )
        except discord.ClientException as e:
            raise RuntimeError(f"voice connection failed: {e}")
        except Exception as e:
            raise RuntimeError(f"failed to join voice channel: {e}")

        state.current_guild_id = guild.id
        state.current_channel_id = vc.id
        state.voice_client = voice_client

    print(f"✓ Joined voice channel: {vc.name}")
    print("Note: Voice with user tokens has known limitations (DAVE / encryption modes).")


async def toggle_rejoin(handler: "CommandHandler") -> None:
    state = handler.voice_state
    state.rejoin_enabled = not state.rejoin_enabled
    if state.rejoin_enabled:
        print("✓ Auto-rejoin enabled (checks every 5 minutes)")
    else:
        print("✗ Auto-rejoin disabled")


async def start_rejoin_monitor(handler: "CommandHandler") -> None:
    """Background task: every 5 minutes, if rejoin is on and we're disconnected, reconnect."""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        state = handler.voice_state
        if not state.rejoin_enabled:
            continue
        if state.current_guild_id is None or state.current_channel_id is None:
            continue
        if state.is_connected():
            continue

        guild = handler.session.get_guild(state.current_guild_id)
        if not guild:
            continue
        ch = guild.get_channel(state.current_channel_id)
        if not isinstance(ch, discord.VoiceChannel):
            continue

        print("\n[Auto-Rejoin] Detected disconnection, rejoining...")
        try:
            voice_client = await ch.connect(timeout=10.0, reconnect=False, self_deaf=False, self_mute=False)
            state.voice_client = voice_client
            print("[Auto-Rejoin] Back in")
        except Exception as e:
            print(f"[Auto-Rejoin] Failed: {e}")


async def joincam(handler: "CommandHandler", args: list[str]) -> None:
    """Join a voice channel with video on (camera). args: <vc_id>"""
    if not args:
        raise ValueError("usage: /joincam <vc_id>")
    cid = int(args[0])
    ch = handler.session.get_channel(cid)
    if not isinstance(ch, discord.VoiceChannel):
        raise RuntimeError("not a voice channel")

    state = handler.voice_state
    async with state._lock:
        if state.is_connected():
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                pass
            state.voice_client = None

        try:
            vc = await ch.connect(timeout=10.0, reconnect=False, self_mute=True)
        except Exception as e:
            raise RuntimeError(f"failed to join: {e}")

        try:
            await ch.guild.change_voice_state(channel=ch, self_video=True, self_mute=True)
        except Exception as e:
            print(f"video flag failed: {e}")

        state.current_guild_id = ch.guild.id
        state.current_channel_id = ch.id
        state.voice_client = vc

    print(f"✓ Joined {ch.name} with cam")
