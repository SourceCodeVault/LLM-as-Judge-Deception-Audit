"""
CORRESPONDENCE AUDITOR - Mainframe-style TUI banner.

Mimics a JES2 separator page + ISPF panel + IPL console output,
the visual triple-threat of authentic z/OS terminal output.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import platform
import getpass
import sys

# --- Graceful Fallback Logic ---
try:
    import pyfiglet
    from rich.console import Console
    from rich.text import Text
    HAS_TUI_LIBS = True
except ImportError:
    HAS_TUI_LIBS = False

# --- Constants ----------------------------------------------------------------
# 132 cols is the historic IBM 1403 line printer width. JES2 banner pages
# were always rendered at this width. Anything narrower is a compromise.
PANEL_WIDTH = 132
FIGLET_FONT = "pagga"  # The # character font — e.g. slant, standard

# ANSI/Rich color scheme tuned for green-phosphor + ISPF cyan/yellow nostalgia
STYLE_RULE       = "bold yellow"
STYLE_BANNER     = "bold white on black"
STYLE_FIELD_KEY  = "bold cyan"
STYLE_FIELD_VAL  = "bold green"
STYLE_SYSTEM_MSG = "green"
STYLE_JES_MSG    = "bold yellow"
STYLE_SEC_MSG    = "bold bright_cyan"
STYLE_OK         = "bold bright_green"
STYLE_DIM        = "dim white"
STYLE_PF         = "bold white on blue"
STYLE_PROMPT     = "bold yellow"


# --- Helpers ------------------------------------------------------------------
def _center_block(art: str, width: int) -> str:
    """Center each line of a multi-line block within `width`."""
    lines = art.split("\n")
    art_width = max(len(line) for line in lines)
    pad = max(0, (width - art_width) // 2)
    return "\n".join(" " * pad + line for line in lines)


def _julian_date(d: datetime.date) -> str:
    """Mainframe Julian date format: YYYY.DDD"""
    return f"{d.year}.{d.timetuple().tm_yday:03d}"


def _kv_row(pairs: list[tuple[str, str]], console: Console) -> None:
    """Render a row of KEY : VALUE fields, padded to fill PANEL_WIDTH."""
    # Each cell is "KEY : VALUE" — distribute evenly across the width
    cell_width = PANEL_WIDTH // len(pairs)
    t = Text()
    for i, (k, v) in enumerate(pairs):
        cell = Text()
        cell.append("   ")
        cell.append(f"{k:<8}", style=STYLE_FIELD_KEY)
        cell.append(" : ", style=STYLE_DIM)
        cell.append(f"{v:<14}", style=STYLE_FIELD_VAL)
        # Pad cell to cell_width
        while cell.cell_len < cell_width:
            cell.append(" ")
        t.append_text(cell)
    console.print(t)


# --- Main banner --------------------------------------------------------------
def print_header(title: str = "CORRESPONDENCE AUDITOR", version: str = "2.0.0") -> None:
    """Render the full TUI header panel using real system telemetry."""
    
    if not HAS_TUI_LIBS:
        print(f"\n{'='*60}\n{title}\n{'='*60}")
        return

    console = Console(width=PANEL_WIDTH, highlight=False)
    now = datetime.datetime.now()
    
    # --- Gather Real Data ---
    real_user = getpass.getuser().upper()[:8]
    node_name = platform.node().upper()[:12]
    os_name = platform.system().upper()
    py_version = f"PY {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    run_id = hashlib.sha1(now.isoformat().encode()).hexdigest()[:8].upper()

    rule = "═" * PANEL_WIDTH
    thin_rule = "─" * PANEL_WIDTH

    # === Top system bar ===
    console.print(Text(rule, style=STYLE_RULE))
    top = Text()
    top.append(" P I P E L I N E   I N I T I A L I Z A T I O N", style=STYLE_RULE)
    right = Text()
    right.append("HOST ", style=STYLE_FIELD_KEY)
    right.append(f"{node_name}", style=STYLE_FIELD_VAL)
    right.append("   OS ", style=STYLE_FIELD_KEY)
    right.append(f"{os_name}", style=STYLE_FIELD_VAL)
    right.append(" ")
    pad = PANEL_WIDTH - top.cell_len - right.cell_len
    top.append(" " * pad)
    top.append_text(right)
    console.print(top)
    console.print(Text(rule, style=STYLE_RULE))
    console.print()

    # === Figlet block letters ===
    words = title.split()
    for word in words:
        art = pyfiglet.figlet_format(word, font=FIGLET_FONT, width=400).rstrip("\n")
        centered = _center_block(art, PANEL_WIDTH)
        for line in centered.split("\n"):
            console.print(Text(line, style=STYLE_BANNER))
    console.print()

    # === Real Metadata Panel ===
    console.print(Text(rule, style=STYLE_RULE))
    _kv_row([("PROCESS", "CORRAUDT"),
             ("USER",    real_user),
             ("RUN ID",  run_id),
             ("DATE",    now.strftime("%Y-%m-%d"))], console)
    _kv_row([("RUNTIME", py_version),
             ("PHASE",   "PRE-FLIGHT"),
             ("STATUS",  "OK"),
             ("TIME",    now.strftime("%H:%M:%S"))], console)
    console.print(Text(rule, style=STYLE_RULE))
    console.print()

    # === Real System Console Messages ===
    msgs = [
        ("SYS.01", STYLE_SEC_MSG, f"SESSION INITIATED BY {real_user} AT {now.strftime('%H:%M:%S')} LOCAL"),
        ("ENV.02", STYLE_SYSTEM_MSG, f"ENVIRONMENT: {os_name} ON {node_name} | {py_version}"),
        ("APP.03", STYLE_JES_MSG, f"CORRESPONDENCE AUDITOR V{version} CORE LOADED"),
        ("SEC.04", STYLE_OK, "AWAITING RUN CONFIGURATION AND DEPLOYMENT TARGETS..."),
    ]
    for code, style, msg in msgs:
        line = Text()
        line.append(code, style=style)
        line.append(" ")
        line.append(msg, style=STYLE_DIM)
        console.print(line)
        
    # We drop the PF keys entirely, as they are deceptive UI.
    console.print(Text(thin_rule, style=STYLE_DIM))
    console.print()


if __name__ == "__main__":
    print_header("CORRESPONDENCE AUDITOR")
