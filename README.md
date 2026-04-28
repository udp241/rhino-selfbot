# rhino-selfbot

CLI + chat-prefix selfbot built on [discord.py-self](https://github.com/dolfies/discord.py-self).
Run from a terminal, or trigger commands in any channel with `$`.

## install

Python 3.10+.

```
python -m venv .venv
.venv\Scripts\activate          # windows
# source .venv/bin/activate     # linux/mac
pip install -r requirements.txt
```

Copy `config.example.json` to `config.json` and add your token:

```json
{
  "token": "your_token_here",
  "prefix": "$",
  "openweather_key": "",
  "bitly_key": "",
  "cuttly_key": ""
}
```

## run

```
python main.py
```

You'll see your servers, then a `>` prompt. Type `help` for the full list.
In any channel, type `$help` to get the same listing as an embed.

## the basics

- `servers` / `s` — list guilds
- `channels <gid>` — list channels
- `enter <gid>` — pick a current server
- `watch <ch_id>` — live-print messages in a channel
- `qs <ch_id> <msg...>` — quick send

Most "post to channel" commands take a `<ch_id>` as their first arg so
you can fire them off without entering the server first. From Discord
with the `$` prefix, the channel is auto-injected — just type `$spam 5 hi`.

## what's in here

150+ commands. `help` shows them grouped. Highlights:

- **info** — `whois`, `profile`, `tokeninfo`, `weather`, `geoip`, `mac`,
  `btc`/`eth`, `shorten` (tinyurl/bitly/cuttly), `qr` (QR code generator),
  `joke`, `advice`
- **message ops** — `clear` (deletes your messages, works in DMs/groups/guilds),
  `archive`, `qs`, `qdel` (send + auto-delete), `typing`, `snipe`, `editall`,
  `hidemention` (zero-width steganography)
- **DM ops** — `closedm` (with `bots` filter), `groupleaver`
- **personal** — `note`, `bm`, `remind`, `sched` (scheduled channel messages),
  `copycat`, `dnote`, `mentions` (with `notify` for live @mention DMs),
  `avatars`
- **presence** — `status` cycler, `afk` auto-reply, `game`/`stream`/etc.,
  full `rpc` (Rich Presence with assets/buttons), `btcstream`
- **self-edit** — `bio`, `pfp`, `banner`, `globalname`, `hypesquad`,
  `cyclenick`, `nick`, `color`, `av`, `reverseav`
- **server admin** — `kick`, `ban`, `unban`, `roleinfo`, `serverinfo`,
  `guildicon`/`guildbanner`, `guildrename`, `fetchmembers`, `delwebhook`
  (kill leaked webhooks), `delroles`/`delchannels`/`massunban` (each takes
  `--confirm`), `rainbow`, `copyguild`, `backup save/load/list`
- **memes** — `swat`, `fry`, `tweet`, `dick`, `howgay`, `slot`, `8ball`,
  `minesweeper`, `cat`/`dog`/`fox`, `tokengrab`, `fakeipban`, `fakenitro`,
  `mashmembers`, plus action GIFs
  (`hug`/`pat`/`kiss`/`slap`/`smug`/`tickle`/`feed`)
- **text fx** — `clearchat`, `flood`, `lmgtfy`, `ascii`, `hastebin`,
  `encode`/`decode`, `leet`, `devowel`, `reverse`, `bold`, `spoiler`,
  `invis`, `everyonelink`, `junknick`, `fakeaddress`, `mashnames`
- **bumping** — `bump` (Disboard slash command) and legacy `autobump`
- **snipe** — last deleted message per channel

## notes

**rate limits.** Everything bulk paces itself (~0.6–1.1s per op) and
honors 429 retry-after headers. Cleaning thousands of messages or
acking dozens of guilds takes a while; that's correct, not a bug.

**voice.** Selfbot voice is unstable on modern Discord (DAVE rollout).
Joining sometimes 4016s. `rejoin` retries every 5 min while enabled.
Nothing to do about that on the user-token side.

**destructive admin.** `delroles` / `delchannels` / `massunban` won't
fire without `--confirm` on the same line. Read the warning, add it.

**dmall** sends to your **friends list**, not every member of a guild.
That's by design.

**triggers delete first.** When you type `$spam 5 hi` in a channel,
the trigger message vanishes immediately, then the action runs.

## API keys (optional)

- `weather` needs `openweather_key` (free at openweathermap.org)
- `bitly` needs `bitly_key` (free tier at bitly.com)
- `cuttly` needs `cuttly_key` (free at cutt.ly)

Everything else uses a no-key API or runs locally.

## persistence

- `data/selfbot.db` — reminders, notes, bookmarks, scheduled msgs, status, AFK, RPC config, copycat targets
- `archives/` — DM archives (one db + folder per channel)
- `exports/` — relationship dumps, member lists, proxy lists, avatar history
- `backups/` — guild structure JSON
- `logs/` — rotating log (5MB × 5)
