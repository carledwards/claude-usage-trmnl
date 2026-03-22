#!/usr/bin/env bash
# install.sh — Install the launchd scheduled job
#
# Usage:
#   ./install.sh
#
# Prerequisites:
#   - Run ./setup.sh first (creates venv, installs deps)
#   - Test with ./run.sh to verify everything works

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_LABEL="com.claude-usage-trmnl.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

# ── Verify setup has been run ────────────────────────────────────────────────

if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "⚠  Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    echo "⚠  No .env file found. Run ./setup.sh first."
    exit 1
fi

# ── Find claude binary path ─────────────────────────────────────────────────

CLAUDE_BIN=$(which claude 2>/dev/null || true)
if [[ -z "$CLAUDE_BIN" ]]; then
    echo "⚠  'claude' not found in PATH."
    echo "   Make sure Claude Code is installed: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi
CLAUDE_DIR=$(dirname "$CLAUDE_BIN")

# ── Pre-flight check ────────────────────────────────────────────────────────

echo ""
echo "==> Pre-flight check"
echo ""
echo "    Before installing the scheduled job, make sure you have:"
echo ""
echo "    1. Trusted this folder in Claude Code:"
echo "         cd $SCRIPT_DIR && claude"
echo "         (accept the prompt, then type /exit)"
echo ""
echo "    2. Tested the full pipeline manually:"
echo "         ./run.sh"
echo "         (should show metrics and 'Posted successfully')"
echo ""
read -rp "    Have you completed both steps above? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo ""
    echo "    No problem. Complete the steps above, then re-run ./install.sh"
    exit 0
fi

# ── Confirmation ─────────────────────────────────────────────────────────────

echo ""
echo "    This will install a launchd job that runs every 5 minutes."
echo "    It will execute: $SCRIPT_DIR/run.sh"
echo "    Logs go to: /tmp/${PLIST_LABEL}.log and /tmp/${PLIST_LABEL}.err"
echo ""
read -rp "    Proceed with installation? [y/N] " install_confirm
if [[ ! "$install_confirm" =~ ^[Yy]$ ]]; then
    echo ""
    echo "    Installation cancelled."
    exit 0
fi

# ── Generate launchd plist ───────────────────────────────────────────────────

echo ""
echo "==> Generating launchd plist..."

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>

  <key>Label</key>
  <string>${PLIST_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT_DIR}/run.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${SCRIPT_DIR}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${CLAUDE_DIR}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>

  <!-- Run every 5 minutes (300 seconds) -->
  <key>StartInterval</key>
  <integer>300</integer>

  <key>StandardOutPath</key>
  <string>/tmp/${PLIST_LABEL}.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/${PLIST_LABEL}.err</string>

  <key>RunAtLoad</key>
  <false/>

</dict>
</plist>
EOF

echo "    Wrote: $PLIST_PATH"

# ── Load the agent ───────────────────────────────────────────────────────────

# Unload first if already loaded (ignore errors)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

echo "==> Loading launchd agent..."
launchctl load "$PLIST_PATH"

echo ""
echo "✓ Installed! The scraper will run every 5 minutes."
echo ""
echo "  NOTE: macOS may show a notification asking to allow \"bash\" to run"
echo "  in the background. You must allow this for the scheduled job to work."
echo ""
echo "  Useful commands:"
echo "    Run now:      launchctl start $PLIST_LABEL"
echo "    View logs:    tail -f /tmp/${PLIST_LABEL}.log"
echo "    View errors:  tail -f /tmp/${PLIST_LABEL}.err"
echo "    Uninstall:    ./uninstall.sh"
