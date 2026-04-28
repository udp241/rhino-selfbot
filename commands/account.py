"""
Account-level info that's useful at a glance.

CLI:
    /account              -- summary: id, country, AFK, required actions, disclosures
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.branding import info, GREY, WHITE, YELLOW, GREEN, RED, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


async def account_cmd(handler: "CommandHandler", args: list[str]) -> None:
    client = handler.session

    user = client.user
    print(f"  User:           {WHITE}{user}{RESET}  {GREY}(id: {user.id}){RESET}")

    cc = getattr(client, "country_code", None)
    print(f"  Country code:   {cc or '?'}")

    afk = client.is_afk() if hasattr(client, "is_afk") else "?"
    afk_str = f"{YELLOW}yes{RESET}" if afk else "no"
    print(f"  AFK:            {afk_str}")

    install_id = getattr(client, "installation_id", None)
    if install_id:
        print(f"  Install ID:     {GREY}{install_id}{RESET}")

    rtc_regions = getattr(client, "preferred_rtc_regions", None) or []
    if rtc_regions:
        print(f"  RTC regions:    {', '.join(rtc_regions)}")

    required = getattr(client, "required_action", None)
    if required:
        print(f"  {RED}Required action: {required}{RESET}")
    else:
        print(f"  Required action: {GREEN}none{RESET}")

    disclose = getattr(client, "disclose", None) or []
    if disclose:
        print(f"  {YELLOW}Disclosures from Discord:{RESET}")
        for d in disclose:
            print(f"    - {d}")

    pending = list(getattr(client, "pending_payments", []))
    if pending:
        print(f"  {YELLOW}Pending payments: {len(pending)}{RESET}")

    suggestions = getattr(client, "friend_suggestion_count", 0)
    print(f"  Friend suggestions: {suggestions}")

    guilds = client.guilds
    print(f"  Guilds:         {WHITE}{len(guilds)}{RESET}")
    print(f"  Friends:        {WHITE}{len(getattr(client, 'friends', []))}{RESET}")
    print(f"  Blocked:        {WHITE}{len(getattr(client, 'blocked', []))}{RESET}")
    print(f"  Latency:        {client.latency * 1000:.0f}ms")
