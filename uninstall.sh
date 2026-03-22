#!/usr/bin/env bash
# uninstall.sh — Remove the launchd scheduled job

set -euo pipefail

PLIST_LABEL="com.claude-usage-trmnl.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

if [[ -f "$PLIST_PATH" ]]; then
    echo "==> Unloading launchd agent..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm "$PLIST_PATH"
    echo "✓ Removed: $PLIST_PATH"
else
    echo "No plist found at $PLIST_PATH — nothing to uninstall."
fi
