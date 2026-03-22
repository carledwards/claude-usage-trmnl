#!/usr/bin/env python3
"""
post_trmnl.py — Run claude_usage_scraper.py and POST the results to a TRMNL private plugin webhook.

Usage:
  python3 post_trmnl.py

Requires TRMNL_WEBHOOK_URL to be set in .env or as an environment variable.
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

WEBHOOK_URL = os.environ.get("TRMNL_WEBHOOK_URL", "")
SCRAPER = Path(__file__).parent / "claude_usage_scraper.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_scraper() -> dict:
    """Run claude_usage_scraper.py and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(SCRAPER)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude_usage_scraper.py exited {result.returncode}:\n{result.stderr}")
    return json.loads(result.stdout)


def build_payload(metrics: dict) -> dict:
    """
    Convert metrics dict into TRMNL merge_variables payload.

    Input:
        {
          "session":     {"pct": 1,  "reset": "4:59pm (America/Los_Angeles)"},
          "week_all":    {"pct": 2,  "reset": "Mar 27 at 8:59am (...)"},
          "week_sonnet": {"pct": 2,  "reset": "Mar 23 at 7am (...)"},
        }

    Output (TRMNL merge_variables):
        {
          "session_pct":       "1",
          "session_reset":     "4:59pm (America/Los_Angeles)",
          "week_all_pct":      "2",
          "week_all_reset":    "Mar 27 at 8:59am (...)",
          "week_sonnet_pct":   "2",
          "week_sonnet_reset": "Mar 23 at 7am (...)",
          "updated_at":        "Mar 21 at 4:59pm",
        }
    """
    def get(key, field, default="—"):
        return str(metrics.get(key, {}).get(field, default))

    now_fmt = datetime.now().strftime("%b %-d at %-I:%M%p")

    return {
        "session_pct":       get("session",     "pct"),
        "session_reset":     get("session",     "reset"),
        "week_all_pct":      get("week_all",    "pct"),
        "week_all_reset":    get("week_all",    "reset"),
        "week_sonnet_pct":   get("week_sonnet", "pct"),
        "week_sonnet_reset": get("week_sonnet", "reset"),
        "updated_at":        now_fmt,
    }


def post_to_trmnl(merge_variables: dict) -> None:
    """POST merge_variables to the TRMNL webhook."""
    if not WEBHOOK_URL:
        raise ValueError(
            "TRMNL_WEBHOOK_URL is not set. "
            "Copy .env.example to .env and add your webhook URL."
        )

    payload = json.dumps({"merge_variables": merge_variables}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "claude-usage-trmnl/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        status = resp.status
        body = resp.read().decode("utf-8", errors="replace")
    print(f"TRMNL responded: {status}")
    if status not in (200, 201, 202):
        raise RuntimeError(f"Unexpected status {status}: {body}")
    print("Posted successfully.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Running scraper…")
    data = run_scraper()

    if not data.get("ok"):
        print(f"Scraper error: {data.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    metrics = data["metrics"]
    print(f"Metrics: {json.dumps(metrics, indent=2)}")

    merge_vars = build_payload(metrics)
    print(f"Posting to TRMNL: {json.dumps(merge_vars, indent=2)}")

    post_to_trmnl(merge_vars)


if __name__ == "__main__":
    main()
