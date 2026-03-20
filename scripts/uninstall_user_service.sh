#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="codex-telegram-bridge.service"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_PATH="$UNIT_DIR/$UNIT_NAME"

systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
rm -f "$UNIT_PATH"
systemctl --user daemon-reload

echo "제거 완료: $UNIT_PATH"
