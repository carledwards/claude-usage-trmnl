#!/usr/bin/env bash
# run.sh — Activate venv, load .env, and run post_trmnl.py
#
# This is the script that launchd calls on a schedule.
# It can also be run manually to test the full pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/com.claude-usage-trmnl.agent.log"

# If the log file doesn't exist yet, write a header so someone finding
# this file knows where it came from and how to stop it.
if [[ ! -f "$LOG_FILE" ]]; then
    cat > "$LOG_FILE" <<EOF
# claude-usage-trmnl
# Source:    $SCRIPT_DIR
# Uninstall: $SCRIPT_DIR/uninstall.sh
# Docs:      $SCRIPT_DIR/README.md
#
EOF
fi

# Load .env if present
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Activate the virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Prefix all output with timestamps
stamp() { while IFS= read -r line; do echo "$(date '+%Y-%m-%d %H:%M:%S') $line"; done; }

# Run the scraper → TRMNL poster
python3 "$SCRIPT_DIR/post_trmnl.py" 2>&1 | stamp
