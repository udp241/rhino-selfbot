# rhino-selfbot

CLI selfbot built on [discord.py-self](https://github.com/dolfies/discord.py-self).
Runs from a terminal — no in-Discord prefix commands. You type, it does.

## install

Python 3.10+.

```
python -m venv .venv
.venv\Scripts\activate          # windows
# source .venv/bin/activate     # linux/mac
pip install -r requirements.txt
```

drop your token in `config.json`:

```json
{
  "token": "your_token_here",
  "openweather_key": "",
  "bitly_key": ""
}
```

## run

```
python main.py
```

You'll see your servers, then a `>` prompt. Type `help` for the full list.

## the basics

- `servers` / `s` — list guilds
- `channels <gid>` — list channels
- `enter <gid>` — pick a current server
- `watch <ch_id>` — live-print messages in a channel
- `qs <ch_id> <msg...>` — quick send

Most "post to channel" commands take a `<ch_id>` as their first arg so
you can fire them off without entering the server first.

## what's in here

140+ commands. `help` shows them grouped. Highlights:

- **info** — `whois`, `profile`, `tokeninfo`, `weather`, `geoip`, `mac`,
  `btc`/`eth`, `joke`, `advice`
- **DM ops** — `cleandm`, `archive`, `closealldm`, `botclosedm`,
  `groupleaver`
- **personal** — `note`, `bm`, `remind`, `dnote`, `mentions`, `avatars`
- **presence** — `status` cycler, `afk` auto-reply, `game`/`stream`/etc,
  full `rpc` (Rich Presence with assets/buttons), `btcstream`
- **self-edit** — `bio`, `pfp`, `banner`, `globalname`, `hypesquad`,
  `cyclenick`, `nick`, `color`
- **server admin** — `kick`, `ban`, `unban`, `roleinfo`, `serverinfo`,
  `delroles`/`delchannels`/`massunban` (each takes `--confirm`),
  `rainbow`, `copyguild`, `backup save/load/list`
- **memes** — `swat`, `fry`, `tweet`, `dick`, `howgay`, `slot`, `8ball`,
  `minesweeper`, `cat`/`dog`/`fox`, plus action GIFs
  (`hug`/`pat`/`kiss`/`slap`/`smug`/`tickle`/`feed`)
- **text fx** — `clearchat`, `flood`, `lmgtfy`, `ascii`, `hastebin`,
  `encode`/`decode`, `leet`, `devowel`, `reverse`, `bold`, `spoiler`,
  `everyonelink`, `junknick`
- **bumping** — `bump` (Disboard slash command) and legacy `autobump`
- **snipe** — last deleted message per channel

## notes

**rate limits.** Everything bulk paces itself (~1.1s per op) and lets
the library handle 429s. Cleaning thousands of messages takes a while;
that's correct, not a bug.

**voice.** Selfbot voice is unstable on modern Discord (DAVE rollout).
Joining sometimes 4016s. `rejoin` retries every 5 min while enabled.
Nothing to do about that on the user-token side.

**destructive admin.** `delroles` / `delchannels` / `massunban` won't
fire without `--confirm` on the same line. Read the warning, add it.

**dmall** sends to your **friends list**, not every member of a guild.
That's by design.

## API keys (optional)

- `weather` needs `openweather_key` (free at openweathermap.org)
- `bitly` needs `bitly_key` (free tier at bitly.com)

Everything else uses a no-key API or runs locally.

## persistence

- `data/selfbot.db` — reminders, notes, bookmarks, status, AFK, RPC config
- `archives/` — DM archives (one db + folder per channel)
- `exports/` — relationship dumps, proxy lists
- `backups/` — guild structure JSON
- `logs/` — rotating log (5MB × 5)
