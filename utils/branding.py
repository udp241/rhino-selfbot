"""
Rhino branding — banner, colors, log prefixes, console title.
Matches the style of the C tools (isp.c, icmp.c, paping, nsl.exe).
"""

from __future__ import annotations

import os
import sys

# --- Colors (ANSI 256-color, like paping) -------------------------------

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

# Cyan family
CYAN = "\x1b[38;5;51m"        # bright cyan, banner asterisks
CYAN_DIM = "\x1b[38;5;37m"    # darker cyan, borders

# Status colors
GREEN = "\x1b[38;5;120m"      # success
RED = "\x1b[38;5;203m"        # error
YELLOW = "\x1b[38;5;221m"     # warning / prompts
GREY = "\x1b[38;5;245m"       # secondary text
WHITE = "\x1b[38;5;255m"

VERSION = "1.0.0"
COPYRIGHT = "Copyright (c) 2026 @rhino241"


def enable_ansi_on_windows() -> None:
    """On Windows 10+, flip the console into VT mode so ANSI escapes render."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def set_title(title: str = "Rhino is a God") -> None:
    """Set the terminal/console window title."""
    if os.name == "nt":
        try:
            os.system(f'title {title}')
        except Exception:
            pass
    else:
        # xterm/VT title escape
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()


# --- Banner -------------------------------------------------------------

_BANNER_ART = r"""
   ____  _     _              ____       _  __ _           _
  |  _ \| |__ (_)_ __   ___  / ___|  ___| |/ _| |__   ___ | |_
  | |_) | '_ \| | '_ \ / _ \ \___ \ / _ \ | |_| '_ \ / _ \| __|
  |  _ <| | | | | | | | (_) | ___) |  __/ |  _| |_) | (_) | |_
  |_| \_\_| |_|_|_| |_|\___/ |____/ \___|_|_| |_.__/ \___/ \__|
"""


def banner() -> str:
    border = f"{CYAN}{'*' * 66}{RESET}"
    title_line = f"{CYAN}*{RESET}{CYAN_DIM}{_BANNER_ART}{RESET}"
    info_lines = [
        f"{CYAN}*{RESET}  {WHITE}Rhino Selfbot{RESET} {GREY}v{VERSION}{RESET}",
        f"{CYAN}*{RESET}  {GREY}{COPYRIGHT}{RESET}",
        f"{CYAN}*{RESET}  {GREY}discord.gg/nca{RESET}",
    ]
    return "\n".join([border, title_line] + info_lines + [border])


# --- Log prefixes (matching the C tools' style) -------------------------

ASTERISK = f"{CYAN}*{RESET}"

def info(msg: str) -> None:
    print(f"{ASTERISK} {msg}")

def success(msg: str) -> None:
    print(f"{GREEN}+{RESET} {msg}")

def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")

def error(msg: str) -> None:
    print(f"{RED}-{RESET} {msg}")

def hit(msg: str = "That Bitch Got Hit!!") -> None:
    """The classic Rhino failure tag from isp.c et al."""
    print(f"{RED}-{RESET} {msg}")

def prompt() -> str:
    return f"{CYAN}>{RESET} "


# --- Discord text "embed" helper (real embeds aren't supported on user accounts) ---

def text_embed(title: str | None = None, description: str | None = None,
               fields: list[tuple[str, str]] | None = None,
               footer: str | None = None) -> str:
    """
    Build a V2-style fake-embed as plain text using markdown blockquotes.

    Real Discord embeds are not allowed in Messageable.send() for user
    accounts in discord.py-self. This is the standard workaround.

    Output looks like:
        **Title**
        description goes here
        > **Field1:** value
        > **Field2:** value
        -# footer
    """
    parts: list[str] = []
    if title:
        parts.append(f"**{title}**")
    if description:
        parts.append(description)
    if fields:
        for name, value in fields:
            parts.append(f"> **{name}:** {value}")
    if footer:
        parts.append(f"-# {footer}")
    return "\n".join(parts)
