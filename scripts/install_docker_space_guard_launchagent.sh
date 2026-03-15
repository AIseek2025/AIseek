#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_PLIST="$ROOT_DIR/deploy/macos/com.aiseek.docker-space-guard.plist"
DST_PLIST="$HOME/Library/LaunchAgents/com.aiseek.docker-space-guard.plist"
LABEL="com.aiseek.docker-space-guard"
UID_NUM="$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$UID_NUM" "$DST_PLIST" >/dev/null 2>&1 || true
launchctl bootout "gui/$UID_NUM" "$SRC_PLIST" >/dev/null 2>&1 || true

cp "$SRC_PLIST" "$DST_PLIST"
plutil -lint "$DST_PLIST"

launchctl bootstrap "gui/$UID_NUM" "$DST_PLIST"
launchctl enable "gui/$UID_NUM/$LABEL"
launchctl kickstart -k "gui/$UID_NUM/$LABEL"

echo "installed: $DST_PLIST"
launchctl print "gui/$UID_NUM/$LABEL" | head -n 30 || true
