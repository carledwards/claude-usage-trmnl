#!/usr/bin/env python3
"""
claude_usage_scraper.py — Scrape Claude CLI /usage stats and dump as JSON

How it works:
  1. Spawns `claude` in a pseudo-terminal (pexpect)
  2. Waits for the interactive prompt to appear
  3. Sends /usage to open the usage modal
  4. Renders the terminal through pyte (a proper terminal emulator)
  5. Parses the three metrics: session %, week-all %, week-sonnet %
  6. Prints JSON to stdout; debug info goes to stderr

Usage:
  python3 claude_usage_scraper.py             # normal run
  python3 claude_usage_scraper.py --debug     # extra verbosity
"""

import sys
import time
import json
import re
import shutil
import pexpect
import pyte

# ── Terminal dimensions ──────────────────────────────────────────────────────
# Wider cols means less line-wrapping inside the TUI; tweak if needed.
COLS = 180
ROWS = 45

# ── Regex helpers ────────────────────────────────────────────────────────────
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

DEBUG = "--debug" in sys.argv


def dbg(*args):
    if DEBUG:
        print("[DEBUG]", *args, file=sys.stderr)


def info(*args):
    print("[scraper]", *args, file=sys.stderr)


# ── pyte helpers ─────────────────────────────────────────────────────────────

def render_screen(screen: pyte.Screen) -> str:
    """Flatten a pyte Screen into a plain-text string (no ANSI codes)."""
    lines = []
    for row in range(screen.lines):
        chars = [screen.buffer[row][col].data for col in range(screen.columns)]
        lines.append("".join(chars).rstrip())
    # Drop trailing blank lines
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def feed(stream: pyte.ByteStream, data: bytes | None):
    if data:
        stream.feed(data)


# ── Scraper core ─────────────────────────────────────────────────────────────

def read_pending(child, stream, timeout: float = 1.5) -> bytes:
    """Drain all pending output from child into the pyte stream."""
    chunks = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = child.read_nonblocking(4096, timeout=0.2)
            if chunk:
                chunks.append(chunk)
        except pexpect.EOF:
            break          # process exited — stop reading
        except pexpect.TIMEOUT:
            continue       # no data right now, keep waiting until deadline
    data = b"".join(chunks)
    dbg(f"read_pending collected {len(data)} bytes")
    if DEBUG and data:
        dbg(f"  raw (first 300): {data[:300]}")
    feed(stream, data)
    dbg(f"read_pending got {len(data)} bytes")
    return data


def scrape() -> dict:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return {"ok": False, "error": "claude not found in PATH"}

    info(f"Using claude at: {claude_bin}")

    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)

    # ── Spawn ────────────────────────────────────────────────────────────────
    # Runs from wherever the script is invoked (PWD).
    # Pre-requisite: run `claude` once manually in that directory first so
    # Claude has already accepted the folder trust prompt — it remembers it.
    child = pexpect.spawn(
        claude_bin,
        encoding=None,           # raw bytes — pyte needs bytes
        dimensions=(ROWS, COLS),
        timeout=30,
    )
    child.setecho(False)

    # ── Wait for initial prompt ──────────────────────────────────────────────
    info("Waiting for interactive prompt…")
    try:
        child.expect([b"> ", b"\xe2\x95\xb0"], timeout=25)
        feed(stream, child.before)
        if child.after not in (pexpect.TIMEOUT, pexpect.EOF):
            feed(stream, child.after)
        info("Prompt matched.")

    except pexpect.TIMEOUT:
        # Feed whatever was captured during the wait — don't discard it
        if child.before:
            dbg(f"TIMEOUT — child.before has {len(child.before)} bytes, feeding to pyte")
            dbg(f"  raw: {child.before[:400]}")
            feed(stream, child.before)
        info("Timed out waiting for prompt — proceeding anyway")
    except pexpect.EOF:
        return {"ok": False, "error": "claude exited unexpectedly before showing a prompt"}

    time.sleep(2.0)                          # extra buffer for slow startup
    read_pending(child, stream, timeout=2.0)

    screen_after_launch = render_screen(screen)
    dbg("Screen after launch:\n" + screen_after_launch)

    # ── Send /usage ──────────────────────────────────────────────────────────
    info("Sending /usage…")
    child.send("/usage\r")   # TUI needs CR, not LF
    time.sleep(2.5)
    read_pending(child, stream, timeout=2.0)

    # ── Wait for usage data to load ──────────────────────────────────────────
    # Claude Code may show a loading state before the actual metrics appear.
    # Retry reading until we see "% used" or hit the max attempts.
    final_screen = render_screen(screen)
    max_retries = 5
    for attempt in range(max_retries):
        if "% used" in final_screen:
            break
        info(f"Usage data not loaded yet, retrying ({attempt + 1}/{max_retries})…")
        time.sleep(2.0)
        read_pending(child, stream, timeout=2.0)
        final_screen = render_screen(screen)

    info("=== RENDERED SCREEN ===")
    info(final_screen)
    info("=== END SCREEN ===")

    # ── Parse ─────────────────────────────────────────────────────────────────
    metrics = extract_metrics(final_screen)

    # ── Clean exit ────────────────────────────────────────────────────────────
    info("Exiting…")
    child.send("\x1b")          # close modal
    time.sleep(0.4)
    try:
        child.send("/exit\n")
        child.expect(pexpect.EOF, timeout=6)
    except (pexpect.TIMEOUT, pexpect.EOF):
        pass
    finally:
        child.close(force=True)

    return {
        "ok": True,
        "metrics": metrics,
        "raw_screen": final_screen,   # keep this until parsing is confirmed good
    }


# ── Metric parser ─────────────────────────────────────────────────────────────

def extract_metrics(text: str) -> dict:
    """
    Parse the three usage blocks from the /usage screen.

    Actual format observed in Claude Code v2.1.81:
        Current session
        ▌                                                  1% used
        Resets 5pm (America/Los_Angeles)

        Current week (all models)
        █                                                  2% used
        Resets Mar 27 at 9am (America/Los_Angeles)

        Current week (Sonnet only)
        █                                                  2% used
        Resets Mar 23 at 7am (America/Los_Angeles)

    Returns:
        {
          "session":      {"pct": 1,  "reset": "5pm (America/Los_Angeles)"},
          "week_all":     {"pct": 2,  "reset": "Mar 27 at 9am (America/Los_Angeles)"},
          "week_sonnet":  {"pct": 2,  "reset": "Mar 23 at 7am (America/Los_Angeles)"},
        }
    """
    metrics: dict = {}
    lines = text.split("\n")

    for i, line in enumerate(lines):
        low = line.lower().strip()

        # Identify which block this header line introduces
        if "current session" in low and "session" not in metrics:
            key = "session"
        elif "current week" in low and "sonnet" not in low and "week_all" not in metrics:
            key = "week_all"
        elif "current week" in low and "sonnet" in low and "week_sonnet" not in metrics:
            key = "week_sonnet"
        else:
            continue

        # The next few lines contain the bar + "X% used" and "Resets ..."
        block = "\n".join(lines[i : i + 4])
        entry = _parse_block(block)
        if entry:
            metrics[key] = entry

    return metrics


def _parse_block(block: str) -> dict | None:
    """
    Extract pct + reset string from a block of lines following a header.

    Handles:
      "1% used"   or   "47% used"
      "Resets 5pm (America/Los_Angeles)"
      "Resets Mar 27 at 9am (America/Los_Angeles)"
    """
    entry: dict = {}

    # Percentage — "1% used" or "47%"
    pct_m = re.search(r"(\d+)\s*%", block)
    if pct_m:
        entry["pct"] = int(pct_m.group(1))

    # Reset line — "Resets <everything after>"
    reset_m = re.search(r"Resets\s+(.+)", block)
    if reset_m:
        entry["reset"] = reset_m.group(1).strip()

    return entry if entry else None


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    result = scrape()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
