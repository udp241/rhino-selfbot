"""
Server admin commands. These act on guilds where you have the
appropriate permissions, and the destructive ones (delroles, delchannels,
massunban) require a confirmation flag.

CLI:
    /roleinfo <guild_id> <role_id>
    /serverinfo <guild_id>
    /guildicon <ch_id> <guild_id>
    /kick <guild_id> <user_id> [reason...]
    /ban <guild_id> <user_id> [reason...]
    /unban <guild_id> <user_id>
    /delroles <guild_id> --confirm
    /delchannels <guild_id> --confirm
    /massunban <guild_id> --confirm
    /rainbow <guild_id> <role_id>           -- start
    /stoprainbow <guild_id> <role_id>
    /copyguild <source_guild_id>            -- duplicates structure into a new guild
    /changeregions <ch_id> <count>          -- group DM call region cycle
    /firstmsg <ch_id>                       -- (we already have this in info.py; kept here for reference)
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import discord

from utils.branding import info, success, error, warn, GREY, WHITE, YELLOW, RESET

if TYPE_CHECKING:
    from .handler import CommandHandler


_rainbow_running: dict[tuple[int, int], bool] = {}


async def _disable_community_if_enabled(g: discord.Guild) -> bool:
    """
    If Community Mode is on, disable it so we can delete the rules channel
    and public-updates channel. Returns True if Community was on, False if not.
    """
    if "COMMUNITY" not in (g.features or []):
        return False
    try:
        await g.edit(community=False)
        # Discord needs a moment for the feature flag to actually clear.
        await asyncio.sleep(1.5)
        return True
    except discord.HTTPException:
        return True  # was on, couldn't turn off — caller should still skip protected


def _protected_channel_ids(g: discord.Guild) -> set[int]:
    """Channels Discord refuses to delete on a Community guild."""
    ids: set[int] = set()
    for attr in ("rules_channel", "public_updates_channel", "safety_alerts_channel"):
        ch = getattr(g, attr, None)
        if ch is not None:
            ids.add(ch.id)
    return ids


async def _channel(client, cid: int):
    ch = client.get_channel(cid) or await client.fetch_channel(cid)
    if not hasattr(ch, "send"):
        raise RuntimeError("channel can't be sent to")
    return ch


# ---- info commands ---------------------------------------------------

async def roleinfo(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /roleinfo <guild_id> <role_id>")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    role = g.get_role(int(args[1]))
    if not role:
        raise RuntimeError("role not found")
    members = sum(1 for m in g.members if role in m.roles)
    info(f"  {WHITE}{role.name}{RESET}  {GREY}({role.id}){RESET}")
    info(f"  members:     {members}")
    info(f"  color:       {role.color}")
    info(f"  hoist:       {role.hoist}")
    info(f"  mentionable: {role.mentionable}")
    info(f"  position:    {role.position}")
    info(f"  managed:     {role.managed}")
    info(f"  created:     {role.created_at.isoformat() if role.created_at else '?'}")


async def serverinfo(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /serverinfo <guild_id>")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    info(f"  {WHITE}{g.name}{RESET}  {GREY}({g.id}){RESET}")
    info(f"  owner:       {g.owner_id}")
    info(f"  members:     {g.member_count}")
    info(f"  channels:    {len(g.channels)}")
    info(f"  roles:       {len(g.roles)}")
    info(f"  boosts:      {g.premium_subscription_count} (tier {g.premium_tier})")
    if g.icon:
        info(f"  icon:        {g.icon.url}")
    if getattr(g, "banner", None):
        info(f"  banner:      {g.banner.url}")
    if g.description:
        info(f"  description: {g.description}")


async def guildicon(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /guildicon <ch_id> <guild_id>")
    cid, gid = int(args[0]), int(args[1])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    if not g.icon:
        raise RuntimeError("guild has no icon")
    ch = await _channel(handler.session, cid)
    await ch.send(f"**{g.name}**\n{g.icon.url}")


async def guildbanner(handler: "CommandHandler", args: list[str]) -> None:
    """Show current guild's banner image, parallel to guildicon."""
    if len(args) < 2:
        raise ValueError("usage: /guildbanner <ch_id> <guild_id>")
    cid, gid = int(args[0]), int(args[1])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    banner = getattr(g, "banner", None)
    if not banner:
        raise RuntimeError("guild has no banner (need server boost level 2+)")
    ch = await _channel(handler.session, cid)
    await ch.send(f"**{g.name}** banner\n{banner.url}")


async def guildrename(handler: "CommandHandler", args: list[str]) -> None:
    """Rename the current guild. Requires Manage Server permission."""
    if len(args) < 2:
        raise ValueError("usage: /guildrename <guild_id> <new_name...>")
    gid = int(args[0])
    new_name = " ".join(args[1:]).strip()
    if not new_name:
        raise ValueError("new name is empty")
    if len(new_name) > 100:
        raise ValueError("guild name max length is 100 chars")
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    old = g.name
    try:
        await g.edit(name=new_name)
    except discord.Forbidden:
        raise RuntimeError("missing Manage Server permission")
    except discord.HTTPException as e:
        raise RuntimeError(f"rename failed: {e}")
    print(f"renamed: {old!r} -> {new_name!r}")


async def fetchmembers(handler: "CommandHandler", args: list[str]) -> None:
    """Chunk-fetch all members of a guild, dump to a file in ./exports/.
    Useful when you need to pull the full member list at once (the
    Discord client lazy-loads it as you scroll).

    CLI:
        /fetchmembers <guild_id> [count]
    """
    import asyncio
    import time
    from pathlib import Path

    if not args:
        raise ValueError("usage: /fetchmembers <guild_id> [count]")
    gid = int(args[0])
    cap = None
    if len(args) > 1:
        try:
            cap = max(1, int(args[1]))
        except ValueError:
            pass

    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")

    print(f"fetching members of {g.name}...")

    rows: list[tuple[int, str, str, str, str]] = []
    seen = 0

    try:
        async for m in g.fetch_members(limit=cap):
            seen += 1
            joined = m.joined_at.isoformat() if m.joined_at else ""
            display = m.display_name or ""
            roles = ",".join(r.name for r in m.roles if r.name != "@everyone")
            rows.append((m.id, str(m), display, joined, roles))
            if seen % 200 == 0:
                print(f"  ...{seen} so far")
            # Light throttle so we don't blast the chunk endpoint
            if seen % 100 == 0:
                await asyncio.sleep(0.5)
    except discord.HTTPException as e:
        print(f"fetch_members partial — error: {e}")

    out_dir = Path(__file__).resolve().parent.parent / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"members_{gid}_{int(time.time())}.tsv"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("id\tusername\tdisplay_name\tjoined_at\troles\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"wrote {len(rows)} members to {out_path}")


# ---- moderation -----------------------------------------------------

async def _resolve_member(g, uid: int):
    m = g.get_member(uid)
    if m is None:
        try:
            m = await g.fetch_member(uid)
        except discord.HTTPException:
            return None
    return m


async def kick(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /kick <guild_id> <user_id> [reason...]")
    gid, uid = int(args[0]), int(args[1])
    reason = " ".join(args[2:]) or None
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    m = await _resolve_member(g, uid)
    if not m:
        raise RuntimeError("user not found in that guild")
    try:
        await m.kick(reason=reason)
    except discord.Forbidden:
        raise RuntimeError("missing kick permission")
    except discord.HTTPException as e:
        raise RuntimeError(f"kick failed: {e}")
    success(f"kicked {m} from {g.name}")


async def ban(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /ban <guild_id> <user_id> [reason...]")
    gid, uid = int(args[0]), int(args[1])
    reason = " ".join(args[2:]) or None
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    user = handler.session.get_user(uid) or await handler.session.fetch_user(uid)
    try:
        await g.ban(user, reason=reason, delete_message_days=0)
    except discord.Forbidden:
        raise RuntimeError("missing ban permission")
    except discord.HTTPException as e:
        raise RuntimeError(f"ban failed: {e}")
    success(f"banned {user} in {g.name}")


async def unban(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /unban <guild_id> <user_id>")
    gid, uid = int(args[0]), int(args[1])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    user = handler.session.get_user(uid) or await handler.session.fetch_user(uid)
    try:
        await g.unban(user)
    except discord.NotFound:
        raise RuntimeError("user wasn't banned")
    except discord.HTTPException as e:
        raise RuntimeError(f"unban failed: {e}")
    success(f"unbanned {user}")


# ---- destructive admin (require --confirm) --------------------------

def _has_confirm(args: list[str]) -> bool:
    return "--confirm" in args


async def delroles(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /delroles <guild_id> --confirm")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will delete ALL roles in {g.name}. re-run with --confirm to proceed")
        return
    deleted = 0; failed = 0
    for role in list(g.roles):
        if role.is_default() or role.managed:
            continue
        try:
            await role.delete()
            deleted += 1
            await asyncio.sleep(0.4)
        except discord.HTTPException:
            failed += 1
    info(f"deleted {deleted} roles, {failed} failed")


async def delchannels(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /delchannels <guild_id> --confirm")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will delete ALL channels in {g.name}. re-run with --confirm to proceed")
        return

    was_community = await _disable_community_if_enabled(g)
    if was_community:
        info("Community was enabled — disabled it first (and still skipping protected channels just in case)")
    protected = _protected_channel_ids(g)

    deleted = 0; failed = 0; skipped = 0
    for ch in list(g.channels):
        if ch.id in protected:
            skipped += 1
            continue
        try:
            await ch.delete()
            deleted += 1
            await asyncio.sleep(0.4)
        except discord.HTTPException:
            failed += 1
    info(f"deleted {deleted} channels, {failed} failed, {skipped} protected/skipped")


async def massunban(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /massunban <guild_id> --confirm")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will unban EVERYONE in {g.name}. re-run with --confirm to proceed")
        return
    unbanned = 0; failed = 0
    try:
        async for entry in g.bans(limit=None):
            try:
                await g.unban(entry.user)
                unbanned += 1
                await asyncio.sleep(1.2)
            except discord.HTTPException:
                failed += 1
    except discord.Forbidden:
        raise RuntimeError("missing ban permission")
    info(f"unbanned {unbanned}, {failed} failed")


async def massban(handler: "CommandHandler", args: list[str]) -> None:
    """Ban every member of a guild you own. Heavy rate-limit."""
    if not args:
        raise ValueError("usage: /massban <guild_id> --confirm")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will ban ALL {g.member_count} members of {g.name}. re-run with --confirm")
        return
    me_id = handler.session.user.id
    banned = 0; failed = 0; skipped = 0
    info(f"banning all members of {g.name}...")
    for m in list(g.members):
        if m.id == me_id or m.id == g.owner_id:
            skipped += 1
            continue
        try:
            await m.ban(reason="massban", delete_message_days=0)
            banned += 1
            if banned % 10 == 0:
                info(f"  ... {banned} banned")
            await asyncio.sleep(1.2)
        except discord.Forbidden:
            failed += 1
        except discord.HTTPException as e:
            failed += 1
            await asyncio.sleep(2.0)
    info(f"banned {banned}, skipped {skipped} (you/owner), {failed} failed")


async def masskick(handler: "CommandHandler", args: list[str]) -> None:
    """Kick every member of a guild you own. Heavy rate-limit."""
    if not args:
        raise ValueError("usage: /masskick <guild_id> --confirm")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will kick ALL {g.member_count} members of {g.name}. re-run with --confirm")
        return
    me_id = handler.session.user.id
    kicked = 0; failed = 0; skipped = 0
    info(f"kicking all members of {g.name}...")
    for m in list(g.members):
        if m.id == me_id or m.id == g.owner_id:
            skipped += 1
            continue
        try:
            await m.kick(reason="masskick")
            kicked += 1
            if kicked % 10 == 0:
                info(f"  ... {kicked} kicked")
            await asyncio.sleep(1.0)
        except discord.Forbidden:
            failed += 1
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(2.0)
    info(f"kicked {kicked}, skipped {skipped} (you/owner), {failed} failed")


async def masschannel(handler: "CommandHandler", args: list[str]) -> None:
    """Bulk-create channels in a guild. /masschannel <guild_id> <name> [count]"""
    if len(args) < 2:
        raise ValueError("usage: /masschannel <guild_id> <name> [count]")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    name = args[1]
    count = int(args[2]) if len(args) > 2 else 50
    count = max(1, min(count, 250))
    info(f"creating {count} channels named '{name}' in {g.name}...")
    created = 0; failed = 0
    for _ in range(count):
        try:
            await g.create_text_channel(name)
            created += 1
            if created % 10 == 0:
                info(f"  ... {created} created")
            await asyncio.sleep(0.6)
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(2.0)
    info(f"created {created} channels, {failed} failed")


async def massrole(handler: "CommandHandler", args: list[str]) -> None:
    """Bulk-create roles in a guild. /massrole <guild_id> <name> [count]"""
    if len(args) < 2:
        raise ValueError("usage: /massrole <guild_id> <name> [count]")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    name = args[1]
    count = int(args[2]) if len(args) > 2 else 50
    count = max(1, min(count, 250))
    info(f"creating {count} roles named '{name}' in {g.name}...")
    created = 0; failed = 0
    for _ in range(count):
        try:
            color = discord.Colour(random.randint(0, 0xFFFFFF))
            await g.create_role(name=name, colour=color)
            created += 1
            if created % 10 == 0:
                info(f"  ... {created} created")
            await asyncio.sleep(0.6)
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(2.0)
    info(f"created {created} roles, {failed} failed")


async def nuke(handler: "CommandHandler", args: list[str]) -> None:
    """
    Full server teardown: delete all channels, delete all roles, ban all
    members. NO ad-URL injection or junk-create phase. Optional rename.

    /nuke <guild_id> --confirm [--rename <new_name>]

    Heads up: even with rate-limiting, running this is a fast track to
    getting your token flagged for raid behaviour. You've been warned.
    """
    if not args:
        raise ValueError("usage: /nuke <guild_id> --confirm [--rename <text>]")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    if not _has_confirm(args):
        warn(f"this will TEARDOWN {g.name} (delete all channels/roles, ban all members). re-run with --confirm")
        return

    rename: str | None = None
    if "--rename" in args:
        i = args.index("--rename")
        if i + 1 < len(args):
            rename = " ".join(args[i + 1:])

    me_id = handler.session.user.id

    info(f"== nuking {g.name} ==")

    # Phase 0: turn off Community if it's on (otherwise rules / public-updates
    # channels can't be deleted and the run looks "unsuccessful")
    was_community = await _disable_community_if_enabled(g)
    if was_community:
        info("phase 0: Community disabled")
    protected = _protected_channel_ids(g)

    # Phase 1: delete every channel
    info("phase 1: deleting channels...")
    deleted_ch = 0; skipped_ch = 0
    for ch in list(g.channels):
        if ch.id in protected:
            skipped_ch += 1
            continue
        try:
            await ch.delete()
            deleted_ch += 1
            await asyncio.sleep(0.4)
        except discord.HTTPException:
            pass
    info(f"  {deleted_ch} channels deleted ({skipped_ch} protected skipped)")

    # Phase 2: delete every role
    info("phase 2: deleting roles...")
    deleted_r = 0
    for role in list(g.roles):
        if role.is_default() or role.managed:
            continue
        try:
            await role.delete()
            deleted_r += 1
            await asyncio.sleep(0.4)
        except discord.HTTPException:
            pass
    info(f"  {deleted_r} roles deleted")

    # Phase 3: ban every member
    info("phase 3: banning members...")
    banned = 0
    for m in list(g.members):
        if m.id == me_id or m.id == g.owner_id:
            continue
        try:
            await m.ban(reason="nuke", delete_message_days=0)
            banned += 1
            await asyncio.sleep(1.2)
        except discord.HTTPException:
            pass
    info(f"  {banned} banned")

    # Phase 4: optional rename
    if rename:
        try:
            await g.edit(name=rename)
            info(f"  renamed -> {rename}")
        except discord.HTTPException as e:
            error(f"  rename failed: {e}")

    info(f"== nuke complete: {g.name} ==")


async def dmguild(handler: "CommandHandler", args: list[str]) -> None:
    """
    DM every member of a guild. /dmguild <guild_id> --confirm <message...>

    Heavy rate-limit (3s per send). Skips bots, yourself, and members
    whose DMs are closed (Forbidden).
    """
    if len(args) < 3 or "--confirm" not in args:
        raise ValueError("usage: /dmguild <guild_id> --confirm <message...>")
    g = handler.session.get_guild(int(args[0]))
    if not g:
        raise RuntimeError("not in that guild")
    rest = [a for a in args[1:] if a != "--confirm"]
    if not rest:
        raise ValueError("missing message body")
    body = " ".join(rest)

    me_id = handler.session.user.id
    sent = 0; closed = 0; failed = 0
    info(f"DMing {len(g.members)} members of {g.name}...")
    for m in list(g.members):
        if m.bot or m.id == me_id:
            continue
        try:
            await m.send(body)
            sent += 1
            if sent % 10 == 0:
                info(f"  ... {sent} sent")
            await asyncio.sleep(3.0)
        except discord.Forbidden:
            closed += 1
        except discord.HTTPException:
            failed += 1
            await asyncio.sleep(5.0)
    info(f"sent {sent}, {closed} DMs closed, {failed} failed")


# ---- rainbow role ---------------------------------------------------

async def rainbow(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /rainbow <guild_id> <role_id>")
    gid, rid = int(args[0]), int(args[1])
    g = handler.session.get_guild(gid)
    if not g:
        raise RuntimeError("not in that guild")
    role = g.get_role(rid)
    if not role:
        raise RuntimeError("role not found")
    key = (gid, rid)
    if _rainbow_running.get(key):
        info("already running for this role")
        return
    _rainbow_running[key] = True
    info(f"rainbow started on {role.name}. /stoprainbow {gid} {rid} to stop")

    async def _loop():
        try:
            while _rainbow_running.get(key):
                try:
                    await role.edit(colour=discord.Color(random.randint(0, 0xFFFFFF)))
                except discord.HTTPException:
                    break
                await asyncio.sleep(10)
        finally:
            _rainbow_running[key] = False

    asyncio.create_task(_loop())


async def stoprainbow(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /stoprainbow <guild_id> <role_id>")
    _rainbow_running[(int(args[0]), int(args[1]))] = False
    success("rainbow stopped")


# ---- copy guild structure into a new guild --------------------------

async def copyguild(handler: "CommandHandler", args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /copyguild <source_guild_id>")
    src = handler.session.get_guild(int(args[0]))
    if not src:
        raise RuntimeError("not in source guild")
    info(f"creating destination guild for backup of {src.name}...")
    try:
        dst = await handler.session.create_guild(name=f"backup-{src.name[:80]}")
    except discord.HTTPException as e:
        raise RuntimeError(f"create_guild failed: {e}")
    await asyncio.sleep(3)

    # Wipe default channels in destination
    for ch in list(dst.channels):
        try:
            await ch.delete()
        except discord.HTTPException:
            pass

    # Recreate categories and channels
    for cat in src.categories:
        try:
            new_cat = await dst.create_category(cat.name)
        except discord.HTTPException:
            continue
        for ch in cat.channels:
            try:
                if isinstance(ch, discord.TextChannel):
                    await new_cat.create_text_channel(ch.name)
                elif isinstance(ch, discord.VoiceChannel):
                    await new_cat.create_voice_channel(ch.name)
            except discord.HTTPException:
                continue
        await asyncio.sleep(0.5)

    # Copy icon if source has one
    if src.icon:
        try:
            from io import BytesIO
            import aiohttp
            async with aiohttp.ClientSession() as http:
                async with http.get(src.icon.url) as r:
                    blob = await r.read()
            await dst.edit(icon=blob)
        except Exception:
            pass

    success(f"backup guild created: {dst.name} ({dst.id})")


# ---- changeregions (group DM call region cycle) --------------------

async def changeregions(handler: "CommandHandler", args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /changeregions <ch_id> <count>")
    cid, count = int(args[0]), int(args[1])
    ch = handler.session.get_channel(cid)
    if not isinstance(ch, discord.GroupChannel):
        raise RuntimeError("must be a group DM channel")

    # Group DM call regions are changed via PATCH /channels/{id}/call.
    # discord.py-self doesn't expose this on GroupChannel.edit, so we
    # fall back to the underlying http client + Route.
    try:
        from discord.http import Route
    except ImportError:
        raise RuntimeError("can't import discord.http.Route")

    regions = ["us-east", "us-west", "us-central", "europe",
               "japan", "brazil", "russia", "singapore", "sydney"]
    for i in range(count):
        region = random.choice(regions)
        try:
            route = Route("PATCH", "/channels/{channel_id}/call",
                          channel_id=ch.id)
            await handler.session.http.request(route, json={"region": region})
            info(f"  region -> {region}")
        except Exception as e:
            error(f"region {region}: {e}")
        await asyncio.sleep(2)
    success(f"cycled regions {count} times")
