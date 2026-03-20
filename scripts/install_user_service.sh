#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${CODEX_TELEGRAM_BRIDGE_CONFIG:-$REPO_ROOT/telegram_codex_relay/config.json}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
UNIT_NAME="codex-telegram-bridge.service"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_PATH="$UNIT_DIR/$UNIT_NAME"
TEMPLATE_PATH="$REPO_ROOT/systemd/codex-telegram-bridge.service.template"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "config 파일이 없습니다: $CONFIG_PATH" >&2
  echo "telegram_codex_relay/config.example.json 을 복사해 config.json 을 먼저 만드세요." >&2
  exit 1
fi

mkdir -p "$UNIT_DIR"

sed \
  -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
  -e "s|__CONFIG_PATH__|$CONFIG_PATH|g" \
  -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" \
  "$TEMPLATE_PATH" > "$UNIT_PATH"

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"

echo "설치 완료: $UNIT_PATH"
systemctl --user --no-pager status "$UNIT_NAME" || true
