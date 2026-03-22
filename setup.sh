#!/usr/bin/env bash
# setup.sh — Create the virtual environment and install dependencies
#
# Usage:
#   chmod +x setup.sh && ./setup.sh
#
# Run this before testing with ./run.sh or installing with ./install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Checking Python 3..."
python3 --version

# ── Virtual environment ──────────────────────────────────────────────────────

if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "==> Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
else
    echo "==> Virtual environment already exists."
fi

echo "==> Installing dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# ── .env check ───────────────────────────────────────────────────────────────

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    echo ""
    echo "⚠  No .env file found."
    echo "   Copy the example and add your TRMNL webhook URL:"
    echo ""
    echo "     cp .env.example .env"
    echo "     # then edit .env with your webhook URL"
    echo ""
    exit 1
fi

# ── Claude check ─────────────────────────────────────────────────────────────

CLAUDE_BIN=$(which claude 2>/dev/null || true)
if [[ -z "$CLAUDE_BIN" ]]; then
    echo ""
    echo "⚠  'claude' not found in PATH."
    echo "   Make sure Claude Code is installed: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

echo ""
echo "✓ Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Trust this folder in Claude Code (if you haven't already):"
echo "         cd $SCRIPT_DIR && claude"
echo "         (accept the prompt, then type /exit)"
echo ""
echo "    2. Test the full pipeline:"
echo "         ./run.sh"
echo ""
echo "    3. Once the test succeeds, install the scheduled job:"
echo "         ./install.sh"
