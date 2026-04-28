"""
Nitro and Server Boost status.

CLI:
    /premium                  -- subscription + boost summary
    /premium subs             -- list active subscriptions
    /premium boosts           -- list active boosts (which servers)
    /premium slots            -- list boost slots (free/used)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, GREY, WHITE, YELLOW, GREEN, RED, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def premium_cmd(handler: "CommandHandler", args: list[str]) -> None:
    sub = args[0] if args else "summary"
    client = handler.session

    if sub in ("summary", ""):
        # Pull all three together for an at-a-glance view
        try:
            subs = await client.subscriptions() if hasattr(client, "subscriptions") else []
        except discord.HTTPException:
            subs = []
        try:
            slots = await client.premium_guild_subscription_slots() if hasattr(client, "premium_guild_subscription_slots") else []
        except discord.HTTPException:
            slots = []
        try:
            active_boosts = await client.premium_guild_subscriptions() if hasattr(client, "premium_guild_subscriptions") else []
        except discord.HTTPException:
            active_boosts = []

        info(f"Active subscriptions: {WHITE}{len(subs)}{RESET}")
        for s in subs:
            stype = getattr(s, "type", "?")
            status = getattr(s, "status", "?")
            ends = getattr(s, "current_period_end", None)
            ends_str = ends.isoformat() if ends else "?"
            print(f"  - {YELLOW}{stype}{RESET}  status: {status}  renews: {GREY}{ends_str}{RESET}")

        used = sum(1 for s in slots if getattr(s, "subscription_id", None))
        info(f"Boost slots: {WHITE}{used}/{len(slots)}{RESET} used")

        info(f"Currently boosting: {WHITE}{len(active_boosts)}{RESET} server(s)")
        for b in active_boosts:
            guild = getattr(b, "guild", None)
            gname = guild.name if guild else "(unknown)"
            ends = getattr(b, "ends_at", None)
            ends_str = f" (until {ends.isoformat()})" if ends else ""
            print(f"  - {gname}{ends_str}")
        return

    if sub == "subs":
        try:
            subs = await client.subscriptions()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        for s in subs:
            print(f"  {YELLOW}{getattr(s, 'type', '?')}{RESET}  status: {getattr(s, 'status', '?')}")
            print(f"    period: {getattr(s, 'current_period_start', '?')} -> {getattr(s, 'current_period_end', '?')}")
            print(f"    payment: {getattr(s, 'payment_source_id', '?')}  currency: {getattr(s, 'currency', '?')}")
        return

    if sub == "boosts":
        try:
            boosts = await client.premium_guild_subscriptions()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        for b in boosts:
            guild = getattr(b, "guild", None)
            gname = guild.name if guild else "(unknown)"
            gid = getattr(guild, "id", "?")
            ends = getattr(b, "ends_at", None)
            ends_str = ends.isoformat() if ends else "?"
            print(f"  {GREY}{gid}{RESET}  {WHITE}{gname}{RESET}  ends: {ends_str}")
        return

    if sub == "slots":
        try:
            slots = await client.premium_guild_subscription_slots()
        except discord.HTTPException as e:
            raise RuntimeError(f"failed: {e}")
        info(f"You have {WHITE}{len(slots)}{RESET} boost slot(s):")
        for s in slots:
            sid = getattr(s, "id", "?")
            sub_id = getattr(s, "subscription_id", None)
            cancelled = getattr(s, "canceled", False)
            cooldown = getattr(s, "cooldown_ends_at", None)
            if sub_id:
                state = f"{RED}IN USE{RESET} (sub: {sub_id})"
            else:
                state = f"{GREEN}FREE{RESET}"
            extras = []
            if cancelled:
                extras.append(f"{RED}cancelled{RESET}")
            if cooldown:
                extras.append(f"cooldown until {cooldown.isoformat()}")
            print(f"  slot {GREY}{sid}{RESET}: {state}  {'  '.join(extras)}")
        return

    raise ValueError(f"unknown premium subcommand: {sub}")
