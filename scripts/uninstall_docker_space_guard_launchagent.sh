#!/usr/bin/env bash
set -euo pipefail

LABEL="com.aiseek.docker-space-guard"
UID_NUM="$(id -u)"
DST_PLIST="$HOME/Library/LaunchAgents/com.aiseek.docker-space-guard.plist"

launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$UID_NUM" "$DST_PLIST" >/dev/null 2>&1 || true
rm -f "$DST_PLIST"

echo "uninstalled: $LABEL"
