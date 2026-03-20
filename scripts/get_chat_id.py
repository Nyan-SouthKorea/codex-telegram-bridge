#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "telegram_codex_relay" / "config.json"


def load_token_from_config() -> str | None:
    if not DEFAULT_CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    token = str(data.get("bot_token") or "").strip()
    return token or None


def telegram_request(token: str, method: str, payload: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={"content-type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Telegram HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"Telegram network error: {exc}") from exc
    parsed = json.loads(raw)
    if not parsed.get("ok"):
        raise SystemExit(f"Telegram API error: {raw}")
    return parsed


def recent_chats(updates: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for update in updates:
        message = update.get("message")
        if not message and update.get("callback_query"):
            message = (update.get("callback_query") or {}).get("message")
        if not message:
            continue
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "").strip()
        if not chat_id:
            continue
        username = str(chat.get("username") or "").strip()
        first_name = str(chat.get("first_name") or "").strip()
        last_name = str(chat.get("last_name") or "").strip()
        title = str(chat.get("title") or "").strip()
        seen[chat_id] = {
            "chat_id": chat_id,
            "chat_type": str(chat.get("type") or "").strip(),
            "username": username,
            "display_name": " ".join(part for part in [first_name, last_name] if part).strip() or title or "-",
        }
    return list(seen.values())


def main() -> int:
    token = sys.argv[1].strip() if len(sys.argv) > 1 else (load_token_from_config() or "")
    if not token:
        print("bot token이 필요합니다.", file=sys.stderr)
        print("사용 예시: python3 scripts/get_chat_id.py 123456789:AA...", file=sys.stderr)
        print(f"또는 {DEFAULT_CONFIG_PATH} 에 bot_token을 먼저 채우세요.", file=sys.stderr)
        return 2
    result = telegram_request(token, "getUpdates", {"timeout": 1, "limit": 20, "allowed_updates": ["message", "callback_query"]})
    chats = recent_chats(result.get("result") or [])
    if not chats:
        print("최근 업데이트에서 chat_id를 찾지 못했습니다.")
        print("Telegram에서 봇 DM을 열고 /start 또는 hi 를 먼저 보내세요.")
        return 0
    print("최근 감지된 Telegram chats:")
    for item in chats:
        print(
            "- "
            f"chat_id={item['chat_id']} | "
            f"type={item['chat_type']} | "
            f"username={item['username'] or '-'} | "
            f"display_name={item['display_name']}"
        )
    print("")
    print("개인 DM 기준 type=private 인 chat_id를 config.json 의 allowed_chat_id 로 사용하면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
