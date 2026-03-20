#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TELEGRAM_MAX_CHARS = 3500
CONTROL_BRIDGE_TIMEOUT_MS = 25_000
PROMPT_BRIDGE_TIMEOUT_MS = 210_000
BUTTON_PREFIX = "tgbtn:"
SESSION_BROWSER_PAGE_SIZE = 6
RELAY_DIR = Path(__file__).resolve().parent
REPO_ROOT = RELAY_DIR.parent
DEFAULT_CONFIG_PATH = RELAY_DIR / "config.json"
DEFAULT_BRIDGE_PATH = RELAY_DIR / "bin" / "codex-bridge"
DEFAULT_STATE_DIR = RELAY_DIR / "state"
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "codex_bridge_state.json"
DEFAULT_RUNTIME_STATE_PATH = DEFAULT_STATE_DIR / "runtime_state.json"


@dataclass
class BotConfig:
    bot_token: str
    allowed_chat_id: str
    workdir: str
    bridge_path: str
    state_path: str
    runtime_state_path: str
    poll_timeout_seconds: int = 30


@dataclass
class RunningPrompt:
    job_id: str
    process: subprocess.Popen[str]
    started_at: float
    prompt_preview: str
    cancel_requested: bool = False


class TelegramError(RuntimeError):
    pass


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def config_path_from_env() -> Path:
    raw = os.environ.get("CODEX_TELEGRAM_BRIDGE_CONFIG", "").strip()
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_CONFIG_PATH


def load_config() -> BotConfig:
    config_path = config_path_from_env()
    if not config_path.exists():
        raise RuntimeError(
            "설정 파일을 찾지 못했습니다.\n"
            f"- expected: {config_path}\n"
            "- `telegram_codex_relay/config.example.json`을 복사해 `config.json`으로 만든 뒤 값을 채우세요."
        )
    data = load_json(str(config_path))
    bot_token = str(data["bot_token"]).strip()
    allowed_chat_id = str(data["allowed_chat_id"]).strip()
    if not bot_token:
        raise RuntimeError("`bot_token` 값이 비어 있습니다.")
    if not allowed_chat_id:
        raise RuntimeError("`allowed_chat_id` 값이 비어 있습니다.")
    workdir = str(data.get("workdir") or REPO_ROOT).strip()
    bridge_path = str(data.get("bridge_path") or DEFAULT_BRIDGE_PATH).strip()
    state_path = str(data.get("state_path") or DEFAULT_STATE_PATH).strip()
    runtime_state_path = str(data.get("runtime_state_path") or DEFAULT_RUNTIME_STATE_PATH).strip()
    return BotConfig(
        bot_token=bot_token,
        allowed_chat_id=allowed_chat_id,
        workdir=workdir,
        bridge_path=bridge_path,
        state_path=state_path,
        runtime_state_path=runtime_state_path,
        poll_timeout_seconds=int(data.get("poll_timeout_seconds", 30)),
    )


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def split_chunks(text: str) -> list[str]:
    normalized = text.strip() or "(empty reply)"
    if len(normalized) <= TELEGRAM_MAX_CHARS:
        return [normalized]
    chunks: list[str] = []
    rest = normalized
    while len(rest) > TELEGRAM_MAX_CHARS:
        cut = rest.rfind("\n", 0, TELEGRAM_MAX_CHARS)
        if cut < TELEGRAM_MAX_CHARS // 2:
            cut = TELEGRAM_MAX_CHARS
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


def parse_command(text: str) -> tuple[str, str] | None:
    trimmed = text.strip()
    if not trimmed.startswith("/"):
        return None
    body = trimmed[1:].strip()
    if not body:
        return None
    if " " in body:
        raw_name, args = body.split(" ", 1)
    else:
        raw_name, args = body, ""
    name = raw_name.split("@", 1)[0].lower()
    return name, args.strip()


def button_data(action: str, value: str | None = None) -> str:
    if value:
        return f"{BUTTON_PREFIX}{action}:{value}"
    return f"{BUTTON_PREFIX}{action}"


def format_state_value(value: str | None, default_label: str = "(default)") -> str:
    text = str(value or "").strip()
    return text or default_label


def format_reasoning_value(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    labels = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "xhigh",
    }
    if not normalized:
        return "(default)"
    return labels.get(normalized, normalized)


def format_fast_mode_value(value: Any) -> str:
    return "on" if bool(value) else "off"


def truncate_button_label(value: str, max_chars: int = 28) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def label_with_check(active: bool, label: str) -> str:
    return f"✓ {label}" if active else label


def format_path_label(path_value: str | Path) -> str:
    path = Path(path_value).expanduser()
    home = Path.home()
    try:
        relative = path.relative_to(home)
        return "~" if str(relative) == "." else f"~/{relative}"
    except Exception:
        return str(path)


def format_timestamp(epoch_value: Any) -> str:
    try:
        epoch = int(epoch_value or 0)
    except Exception:
        return "-"
    if epoch <= 0:
        return "-"
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def parse_button_action(value: str) -> tuple[str, str | None] | None:
    text = value.strip()
    if not text.startswith(BUTTON_PREFIX):
        return None
    body = text[len(BUTTON_PREFIX) :].strip()
    if not body:
        return None
    parts = body.split(":")
    action = parts[0].lower()
    arg = ":".join(parts[1:]).strip() if len(parts) > 1 else None
    return action, arg or None


class TelegramApi:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = None
        headers = {"content-type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = Request(url, method="POST", headers=headers, data=data)
        try:
            with urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TelegramError(f"Telegram HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise TelegramError(f"Telegram network error: {exc}") from exc
        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise TelegramError(f"Telegram API error: {body}")
        return parsed

    def delete_webhook(self) -> None:
        self.request("deleteWebhook", {"drop_pending_updates": False})

    def set_help_only_commands(self) -> None:
        self.request(
            "setMyCommands",
            {
                "commands": [
                    {
                        "command": "help",
                        "description": "버튼 메뉴 열기",
                    }
                ]
            },
        )

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return self.request("getUpdates", payload).get("result", [])

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        inline_keyboard: list[list[dict[str, str]]] | None = None,
    ) -> None:
        chunks = split_chunks(text)
        for index, chunk in enumerate(chunks):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if index == 0 and reply_to_message_id:
                payload["reply_parameters"] = {"message_id": reply_to_message_id}
            if index == len(chunks) - 1 and inline_keyboard:
                payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
            self.request("sendMessage", payload)

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        self.request("answerCallbackQuery", payload)


class DirectTelegramCodexBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.api = TelegramApi(config.bot_token)
        self.running_lock = threading.Lock()
        self.running_prompt: RunningPrompt | None = None
        self.write_runtime_state(status="idle")

    def load_bridge_state(self) -> dict[str, Any]:
        try:
            return load_json(self.config.state_path)
        except Exception:
            return {}

    def write_runtime_state(self, **updates: Any) -> None:
        path = Path(self.config.runtime_state_path)
        data: dict[str, Any]
        try:
            data = load_json(str(path))
        except Exception:
            data = {"status": "idle"}
        data.update(updates)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load_runtime_state(self) -> dict[str, Any]:
        try:
            return load_json(self.config.runtime_state_path)
        except Exception:
            return {"status": "idle"}

    def safe_directory(self, raw_path: str | Path | None, fallback: Path) -> Path:
        try:
            candidate = Path(raw_path or fallback).expanduser().resolve()
        except Exception:
            candidate = fallback
        if not candidate.exists() or not candidate.is_dir():
            return fallback
        return candidate

    def session_browser_root(self) -> Path:
        return Path.home()

    def default_scope_path(self) -> Path:
        return self.safe_directory(self.config.workdir, Path.home())

    def ensure_default_resume_scope(self) -> Path:
        default_scope = self.default_scope_path()
        runtime = self.load_runtime_state()
        if bool(runtime.get("session_scope_initialized")):
            return default_scope
        state = self.load_bridge_state()
        current_scope = self.safe_directory(state.get("session_scope_cwd"), default_scope)
        if current_scope != default_scope:
            try:
                self.run_bridge(["set-workdir", str(default_scope)])
            except Exception:
                pass
        self.write_runtime_state(
            session_scope_initialized=True,
            session_scope_user_selected=False,
            default_scope_origin=str(default_scope),
        )
        return default_scope

    def current_scope_path(self) -> Path:
        self.ensure_default_resume_scope()
        state = self.load_bridge_state()
        fallback = self.default_scope_path()
        return self.safe_directory(state.get("session_scope_cwd") or state.get("workdir"), fallback)

    def cli_mode_summary(self, state: dict[str, Any]) -> str:
        return (
            f"model: {format_state_value(state.get('model'))} | "
            f"fast: {format_fast_mode_value(state.get('fast_mode'))} | "
            f"thinking: {format_reasoning_value(state.get('reasoning_effort'))} | "
            f"permission: {format_state_value(state.get('permission'), 'full')}"
        )

    def render_cli_message(self, source: str, title: str, body: str, *, state: dict[str, Any] | None = None) -> str:
        bridge_state = dict(state or self.load_bridge_state())
        lines = [
            f"{source}> {title}",
            f"session: {format_state_value(bridge_state.get('active_session_name'), '(none)')}",
            f"cwd: {format_state_value(bridge_state.get('workdir'), self.config.workdir)}",
            self.cli_mode_summary(bridge_state),
            "",
            body.strip() or "(empty reply)",
        ]
        return "\n".join(lines).strip()

    def browser_state(self, path_key: str, page_key: str, token_key: str, fallback: Path) -> tuple[Path, int, str]:
        data = self.load_runtime_state()
        raw_path = str(data.get(path_key) or fallback)
        path = self.safe_directory(raw_path, fallback)
        try:
            page = max(int(data.get(page_key) or 0), 0)
        except Exception:
            page = 0
        token = str(data.get(token_key) or "")
        return path, page, token

    def set_browser_state(self, path_key: str, page_key: str, token_key: str, path: Path, page: int = 0) -> str:
        normalized = path.expanduser().resolve()
        token = str(int(time.time() * 1000))
        self.write_runtime_state(
            **{
                path_key: str(normalized),
                page_key: max(page, 0),
                token_key: token,
            }
        )
        return token

    def session_browser_state(self) -> tuple[Path, int, str]:
        return self.browser_state(
            "session_browser_path",
            "session_browser_page",
            "session_browser_token",
            self.session_browser_root(),
        )

    def pending_new_folder_parent(self) -> Path | None:
        data = self.load_runtime_state()
        raw = str(data.get("pending_new_folder_parent") or "").strip()
        if not raw:
            return None
        try:
            path = Path(raw).expanduser().resolve()
        except Exception:
            return None
        return path

    def set_pending_new_folder_parent(self, path: Path | None) -> None:
        if path is None:
            self.write_runtime_state(pending_new_folder_parent=None)
            return
        self.write_runtime_state(pending_new_folder_parent=str(path.expanduser().resolve()))

    def set_session_browser_state(self, path: Path, page: int = 0) -> str:
        return self.set_browser_state(
            "session_browser_path",
            "session_browser_page",
            "session_browser_token",
            path,
            page,
        )

    def resume_browser_state(self) -> tuple[Path, int, str]:
        return self.browser_state(
            "resume_browser_path",
            "resume_browser_page",
            "resume_browser_token",
            self.current_scope_path(),
        )

    def set_resume_browser_state(self, path: Path, page: int = 0) -> str:
        return self.set_browser_state(
            "resume_browser_path",
            "resume_browser_page",
            "resume_browser_token",
            path,
            page,
        )

    def list_browser_directories(self, path: Path) -> list[Path]:
        try:
            entries = [entry for entry in path.iterdir() if entry.is_dir()]
        except Exception:
            return []
        return sorted(entries, key=lambda entry: (entry.name.startswith("."), entry.name.lower()))

    def session_button_label(self, index: int, entry: dict[str, Any], active: bool) -> str:
        session_name = str(entry.get("name") or "").strip()
        fallback = Path(str(entry.get("cwd") or "")).name or str(entry.get("id") or index)
        label = f"{index}. {session_name or fallback}"
        return label_with_check(active, truncate_button_label(label, max_chars=30))

    def browser_button_label(self, index: int, entry: Path) -> str:
        label = f"{index}. {entry.name or str(entry)}"
        return truncate_button_label(label, max_chars=30)

    def format_session_entry_lines(self, index: int, entry: dict[str, Any], active: bool) -> list[str]:
        status = "현재 선택됨" if active else "선택 가능"
        return [
            f"[{index}] {entry.get('name') or entry.get('id') or '-'}",
            f"  cwd: {entry.get('cwd') or '-'}",
            f"  created: {format_timestamp(entry.get('createdAt'))}",
            f"  updated: {format_timestamp(entry.get('updatedAt'))}",
            f"  status: {status}",
        ]

    def current_runtime_status(self) -> tuple[str, RunningPrompt | None]:
        with self.running_lock:
            prompt = self.running_prompt
            if prompt and prompt.process.poll() is None:
                return "busy", prompt
            if prompt and prompt.process.poll() is not None:
                self.running_prompt = None
            return "idle", None

    def bridge_command(self, args: list[str]) -> list[str]:
        # Always launch the bridge with the same interpreter as the running bot.
        return [sys.executable, self.config.bridge_path, *args]

    def run_bridge(self, args: list[str], stdin_text: str | None = None, timeout_ms: int = CONTROL_BRIDGE_TIMEOUT_MS) -> str:
        result = subprocess.run(
            self.bridge_command(args),
            input=stdin_text,
            cwd=self.config.workdir,
            env=self.bridge_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_ms / 1000,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "bridge failed").strip())
        return result.stdout.strip()

    def build_help_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        state = self.load_bridge_state()
        text = "\n".join(
            [
                "Codex 텔레그램 사용법",
                "- 평문은 현재 Codex 세션으로 바로 전달됩니다.",
                "- 슬래시 명령은 /help만 지원합니다.",
                "- 설정과 조회는 버튼으로만 합니다.",
                "- 권한이 full이면 지속 세션, read/deny면 격리 1회 실행입니다.",
                "- 세션 메뉴의 `디렉토리 설정`으로 /resume 기준 폴더를 바꿀 수 있습니다.",
                "- `Fast`는 실제 Codex Fast mode 토글입니다.",
                "",
                f"현재 모델: {format_state_value(state.get('model'))}",
                f"현재 Fast mode: {format_fast_mode_value(state.get('fast_mode'))}",
                f"현재 thinking: {format_reasoning_value(state.get('reasoning_effort'))}",
                f"현재 권한: {format_state_value(state.get('permission'), 'full')}",
                f"현재 세션: {format_state_value(state.get('active_session_name'), '(none)')}",
            ]
        )
        fast_enabled = bool(state.get("fast_mode"))
        buttons = [
            [
                {"text": "세션", "callback_data": button_data("menu", "resume")},
                {"text": "모델", "callback_data": button_data("menu", "model")},
            ],
            [
                {"text": label_with_check(fast_enabled, "Fast"), "callback_data": button_data("fast", "toggle")},
                {"text": "Thinking", "callback_data": button_data("menu", "thinking")},
            ],
            [
                {"text": "권한", "callback_data": button_data("menu", "permission")},
                {"text": "최근 출력", "callback_data": button_data("read")},
            ],
            [
                {"text": "현재 상태", "callback_data": button_data("status")},
                {"text": "취소", "callback_data": button_data("cancel")},
            ],
        ]
        return text, buttons

    def build_resume_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        state = self.load_bridge_state()
        scope_path = self.current_scope_path()
        raw = self.run_bridge(["sessions-json", "12", str(scope_path)])
        entries = json.loads(raw)
        rows: list[list[dict[str, str]]] = []
        active_id = str(state.get("active_session_id") or "").strip()
        text_lines = [
            "Codex 세션",
            f"현재 세션: {format_state_value(state.get('active_session_name'), '(none)')}",
            f"세션 기준 폴더: {scope_path}",
            "",
            "표시 규칙: 이 폴더와 동일한 cwd 세션만 보여줍니다.",
            "최근 세션 순서: 최신 활동 순",
            "",
        ]
        rows.append(
            [
                {"text": "디렉토리 설정", "callback_data": button_data("menu", "resume-browser")},
                {"text": "새 세션 만들기", "callback_data": button_data("menu", "session-browser")},
            ]
        )
        rows.append(
            [
                {"text": "현재 세션 삭제", "callback_data": button_data("session", "delete")},
            ]
        )
        if not entries:
            text_lines.append("- 이 폴더와 동일한 cwd 세션이 없습니다.")
        for index, entry in enumerate(entries, start=1):
            active = bool(entry.get("active")) or str(entry.get("id") or "") == active_id
            text_lines.extend(self.format_session_entry_lines(index, entry, active))
            text_lines.append("")
            rows.append(
                [
                    {
                        "text": self.session_button_label(index, entry, active),
                        "callback_data": button_data("resume", str(entry.get("id"))),
                    }
                ]
            )
        rows.append(
            [
                {"text": "도움말", "callback_data": button_data("menu", "help")},
                {"text": "현재 상태", "callback_data": button_data("status")},
            ]
        )
        return "\n".join(text_lines), rows

    def build_resume_browser_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        path, page, _ = self.resume_browser_state()
        scope_path = self.current_scope_path()
        directories = self.list_browser_directories(path)
        preview_raw = self.run_bridge(["sessions-json", "5", str(path)])
        preview_entries = json.loads(preview_raw)
        active_id = str(self.load_bridge_state().get("active_session_id") or "").strip()
        page_count = max((len(directories) - 1) // SESSION_BROWSER_PAGE_SIZE + 1, 1)
        page = min(page, page_count - 1)
        token = self.set_resume_browser_state(path, page)
        start = page * SESSION_BROWSER_PAGE_SIZE
        visible = directories[start : start + SESSION_BROWSER_PAGE_SIZE]
        text_lines = [
            "세션 디렉토리 선택",
            f"현재 폴더: {path}",
            f"현재 /resume 기준 폴더: {scope_path}",
            f"페이지: {page + 1}/{page_count}",
            "",
            "이 폴더를 현재 디렉토리로 설정하면 /resume 목록이 이 폴더와 동일한 cwd 기준으로 바뀝니다.",
        ]
        rows: list[list[dict[str, str]]] = []
        if visible:
            text_lines.extend(["", "보이는 하위 폴더:"])
        for index, entry in enumerate(visible, start=1):
            text_lines.append(f"[{index}] {entry}")
            rows.append(
                [
                    {
                        "text": self.browser_button_label(index, entry),
                        "callback_data": button_data("resbrowse", f"open|{token}|{index - 1}"),
                    }
                ]
            )
        if not visible:
            text_lines.extend(["", "- 하위 폴더가 없습니다."])
        text_lines.extend(["", "현재 폴더 기준 최근 세션 미리보기:"])
        if preview_entries:
            for index, entry in enumerate(preview_entries, start=1):
                active = bool(entry.get("active")) or str(entry.get("id") or "") == active_id
                text_lines.extend(self.format_session_entry_lines(index, entry, active))
                text_lines.append("")
        else:
            text_lines.append("- 이 폴더와 동일한 cwd 세션이 없습니다.")
        nav_row: list[dict[str, str]] = []
        if path.parent != path:
            nav_row.append({"text": "../", "callback_data": button_data("resbrowse", f"up|{token}")})
        if page > 0:
            nav_row.append({"text": "이전", "callback_data": button_data("resbrowse", f"page|{token}|{page - 1}")})
        if page + 1 < page_count:
            nav_row.append({"text": "다음", "callback_data": button_data("resbrowse", f"page|{token}|{page + 1}")})
        if nav_row:
            rows.append(nav_row)
        set_label = "✓ 현재 디렉토리" if path == scope_path else "이 폴더를 현재 디렉토리로 설정"
        rows.append(
            [
                {"text": set_label, "callback_data": button_data("resbrowse", f"set|{token}")},
                {"text": "세션 메뉴", "callback_data": button_data("menu", "resume")},
            ]
        )
        rows.append(
            [
                {"text": "도움말", "callback_data": button_data("menu", "help")},
                {"text": "현재 상태", "callback_data": button_data("status")},
            ]
        )
        return "\n".join(text_lines).strip(), rows

    def build_session_browser_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        path, page, _ = self.session_browser_state()
        pending_parent = self.pending_new_folder_parent()
        directories = self.list_browser_directories(path)
        page_count = max((len(directories) - 1) // SESSION_BROWSER_PAGE_SIZE + 1, 1)
        page = min(page, page_count - 1)
        token = self.set_session_browser_state(path, page)
        start = page * SESSION_BROWSER_PAGE_SIZE
        visible = directories[start : start + SESSION_BROWSER_PAGE_SIZE]
        text_lines = [
            "새 Codex 세션 만들기",
            f"현재 폴더: {path}",
            f"페이지: {page + 1}/{page_count}",
            "",
            "현재 폴더의 바로 아래 하위 폴더만 보여줍니다.",
            "폴더 버튼을 눌러 안으로 들어가거나, ../ 버튼으로 다시 나올 수 있습니다.",
        ]
        if pending_parent is not None:
            text_lines.extend(
                [
                    "",
                    f"새 폴더 이름 입력 대기 중: {pending_parent}",
                    "이름을 일반 메시지로 보내거나 취소 버튼을 누르세요.",
                ]
            )
        rows: list[list[dict[str, str]]] = []
        if visible:
            text_lines.append("")
            text_lines.append("보이는 폴더:")
        for index, entry in enumerate(visible, start=1):
            text_lines.append(f"[{index}] {entry}")
            rows.append(
                [
                    {
                        "text": self.browser_button_label(index, entry),
                        "callback_data": button_data("sessbrowse", f"open|{token}|{index - 1}"),
                    }
                ]
            )
        if not visible:
            text_lines.append("")
            text_lines.append("- 하위 폴더가 없습니다.")
        nav_row: list[dict[str, str]] = []
        if path.parent != path:
            nav_row.append({"text": "../", "callback_data": button_data("sessbrowse", f"up|{token}")})
        if page > 0:
            nav_row.append({"text": "이전", "callback_data": button_data("sessbrowse", f"page|{token}|{page - 1}")})
        if page + 1 < page_count:
            nav_row.append({"text": "다음", "callback_data": button_data("sessbrowse", f"page|{token}|{page + 1}")})
        if nav_row:
            rows.append(nav_row)
        rows.append(
            [
                {"text": "현재 폴더로 세션 시작", "callback_data": button_data("sessbrowse", f"create|{token}")},
                {"text": "새 폴더 만들기", "callback_data": button_data("sessbrowse", f"mkdir|{token}")},
            ]
        )
        rows.append(
            [
                {"text": "세션 메뉴", "callback_data": button_data("menu", "resume")},
                {"text": "도움말", "callback_data": button_data("menu", "help")},
            ]
        )
        rows.append(
            [
                {"text": "현재 상태", "callback_data": button_data("status")},
            ]
        )
        return "\n".join(text_lines), rows

    def build_model_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        state = self.load_bridge_state()
        current_model = str(state.get("model") or "").strip()
        text = "\n".join(
            [
                "Codex 모델 선택",
                f"현재 모델: {format_state_value(state.get('model'))}",
                "",
                "모델을 누르면 바로 저장하고, 다음 메시지에서 thinking 버튼을 이어서 띄웁니다.",
            ]
        )
        buttons = [
            [
                {"text": label_with_check(current_model == "gpt-5.4", "GPT-5.4"), "callback_data": button_data("model", "gpt-5.4")},
                {"text": label_with_check(current_model == "gpt-5.4-mini", "5.4 Mini"), "callback_data": button_data("model", "gpt-5.4-mini")},
            ],
            [
                {"text": label_with_check(current_model == "gpt-5.3-codex", "5.3 Codex"), "callback_data": button_data("model", "gpt-5.3-codex")},
                {"text": label_with_check(current_model == "gpt-5.3-codex-spark", "5.3 Spark"), "callback_data": button_data("model", "gpt-5.3-codex-spark")},
            ],
            [
                {"text": label_with_check(current_model == "gpt-5.2", "5.2"), "callback_data": button_data("model", "gpt-5.2")},
                {"text": label_with_check(current_model == "gpt-5.2-codex", "5.2 Codex"), "callback_data": button_data("model", "gpt-5.2-codex")},
            ],
            [
                {"text": label_with_check(current_model == "gpt-5.1-codex-max", "5.1 Max"), "callback_data": button_data("model", "gpt-5.1-codex-max")},
                {"text": label_with_check(current_model == "gpt-5.1-codex-mini", "5.1 Mini"), "callback_data": button_data("model", "gpt-5.1-codex-mini")},
            ],
            [
                {"text": label_with_check(not current_model, "기본값"), "callback_data": button_data("model", "default")},
                {"text": "도움말", "callback_data": button_data("menu", "help")},
            ],
        ]
        return text, buttons

    def build_thinking_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        state = self.load_bridge_state()
        current = str(state.get("reasoning_effort") or "").strip()
        text = "\n".join(
            [
                "Codex thinking 선택",
                f"현재 thinking: {format_reasoning_value(state.get('reasoning_effort'))}",
                "",
                "Fast mode는 메인 메뉴의 Fast 버튼에서 따로 토글합니다.",
            ]
        )
        buttons = [
            [
                {"text": label_with_check(current == "low", "Low"), "callback_data": button_data("thinking", "low")},
                {"text": label_with_check(current == "medium", "Medium"), "callback_data": button_data("thinking", "medium")},
            ],
            [
                {"text": label_with_check(current == "high", "High"), "callback_data": button_data("thinking", "high")},
                {"text": label_with_check(current == "xhigh", "XHigh"), "callback_data": button_data("thinking", "xhigh")},
            ],
            [
                {"text": label_with_check(not current, "기본값"), "callback_data": button_data("thinking", "default")},
                {"text": "도움말", "callback_data": button_data("menu", "help")},
            ],
        ]
        return text, buttons

    def build_permission_menu(self) -> tuple[str, list[list[dict[str, str]]]]:
        state = self.load_bridge_state()
        current = str(state.get("permission") or "full").strip() or "full"
        text = "\n".join(
            [
                "Codex 권한 선택",
                f"현재 권한: {format_state_value(state.get('permission'), 'full')}",
                "",
                "full은 지속 세션 + 전체 허용, read/deny는 격리 1회 실행입니다.",
            ]
        )
        buttons = [
            [
                {"text": label_with_check(current == "full", "Full"), "callback_data": button_data("permission", "full")},
                {"text": label_with_check(current == "read", "Read"), "callback_data": button_data("permission", "read")},
            ],
            [
                {"text": label_with_check(current == "deny", "Deny"), "callback_data": button_data("permission", "deny")},
                {"text": "도움말", "callback_data": button_data("menu", "help")},
            ],
        ]
        return text, buttons

    def build_menu(self, kind: str) -> tuple[str, list[list[dict[str, str]]]]:
        if kind == "help":
            return self.build_help_menu()
        if kind == "resume":
            return self.build_resume_menu()
        if kind == "resume-browser":
            return self.build_resume_browser_menu()
        if kind == "session-browser":
            return self.build_session_browser_menu()
        if kind == "model":
            return self.build_model_menu()
        if kind == "thinking":
            return self.build_thinking_menu()
        return self.build_permission_menu()

    def prompt_busy_message(self) -> str:
        _, running = self.current_runtime_status()
        if not running:
            return "현재 실행 중인 작업이 없습니다."
        seconds = int(time.time() - running.started_at)
        return (
            "이미 Codex 작업이 실행 중입니다.\n"
            f"- started: {seconds}s ago\n"
            f"- preview: {running.prompt_preview}\n"
            "- 필요하면 취소 버튼을 누른 뒤 다시 시도하세요."
        )

    def create_new_folder_session(self, folder_name: str) -> str:
        parent = self.pending_new_folder_parent()
        if parent is None:
            raise RuntimeError("새 폴더 생성 대기 상태가 아닙니다.")
        raw_name = folder_name.strip()
        if not raw_name:
            raise RuntimeError("새 폴더 이름이 비어 있습니다.")
        if raw_name in {".", ".."}:
            raise RuntimeError("`.` 또는 `..` 는 폴더 이름으로 사용할 수 없습니다.")
        if "/" in raw_name or "\\" in raw_name:
            raise RuntimeError("새 폴더 이름에는 경로 구분자를 넣을 수 없습니다.")
        target = parent / raw_name
        if target.exists():
            raise RuntimeError(f"이미 같은 이름의 경로가 있습니다: {target}")
        target.mkdir(parents=False, exist_ok=False)
        output = self.run_bridge(["new-session", str(target)], timeout_ms=120_000)
        self.set_pending_new_folder_parent(None)
        return output

    def cancel_running_prompt(self) -> str:
        with self.running_lock:
            running = self.running_prompt
            if not running or running.process.poll() is not None:
                self.running_prompt = None
                self.write_runtime_state(status="idle", current_job_id=None, pid=None, prompt_preview=None)
                return "현재 취소할 Codex 실행이 없습니다."
            running.cancel_requested = True
            try:
                os.killpg(running.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.write_runtime_state(
                status="cancel-requested",
                current_job_id=running.job_id,
                pid=running.process.pid,
                prompt_preview=running.prompt_preview,
                cancel_requested=True,
            )
            return f"현재 Codex 실행 취소를 요청했습니다.\n- job: {running.job_id}"

    def start_prompt(self, chat_id: str, prompt_text: str, reply_to_message_id: int | None) -> str | None:
        status, _ = self.current_runtime_status()
        if status == "busy":
            return self.prompt_busy_message()
        command = self.bridge_command(["prompt"])
        proc = subprocess.Popen(
            command,
            cwd=self.config.workdir,
            env=self.bridge_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            start_new_session=True,
        )
        job_id = f"job-{int(time.time() * 1000)}"
        running = RunningPrompt(
            job_id=job_id,
            process=proc,
            started_at=time.time(),
            prompt_preview=truncate_button_label(prompt_text, max_chars=40),
        )
        with self.running_lock:
            self.running_prompt = running
        self.write_runtime_state(
            status="busy",
            current_job_id=job_id,
            pid=proc.pid,
            prompt_preview=running.prompt_preview,
            started_at=running.started_at,
            cancel_requested=False,
        )
        worker = threading.Thread(
            target=self._wait_prompt,
            args=(chat_id, reply_to_message_id, running, prompt_text.strip()),
            daemon=True,
        )
        worker.start()
        return None

    def bridge_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["CODEX_TELEGRAM_BRIDGE_STATE_PATH"] = self.config.state_path
        env["CODEX_TELEGRAM_BRIDGE_DEFAULT_WORKDIR"] = self.config.workdir
        return env

    def _wait_prompt(
        self,
        chat_id: str,
        reply_to_message_id: int | None,
        running: RunningPrompt,
        prompt_text: str,
    ) -> None:
        stdout_text = ""
        stderr_text = ""
        try:
            stdout_text, stderr_text = running.process.communicate(
                input=prompt_text + "\n",
                timeout=PROMPT_BRIDGE_TIMEOUT_MS / 1000,
            )
            code = running.process.returncode
            if code == 0:
                message = stdout_text.strip() or "(empty reply)"
                self.api.send_message(
                    chat_id,
                    self.render_cli_message("codex", "reply", message),
                    reply_to_message_id=reply_to_message_id,
                )
                self.write_runtime_state(
                    status="idle",
                    current_job_id=None,
                    pid=None,
                    prompt_preview=None,
                    last_completed_at=time.time(),
                    last_error=None,
                )
            else:
                if running.cancel_requested:
                    self.write_runtime_state(
                        status="idle",
                        current_job_id=None,
                        pid=None,
                        prompt_preview=None,
                        last_completed_at=time.time(),
                        last_error=None,
                    )
                else:
                    error = (stderr_text or stdout_text or f"bridge failed ({code})").strip()
                    self.api.send_message(
                        chat_id,
                        self.render_cli_message("error", "prompt", f"처리 중 오류가 났습니다.\n{error}"),
                        reply_to_message_id=reply_to_message_id,
                    )
                    self.write_runtime_state(
                        status="idle",
                        current_job_id=None,
                        pid=None,
                        prompt_preview=None,
                        last_completed_at=time.time(),
                        last_error=error,
                    )
        except Exception as exc:
            self.api.send_message(
                chat_id,
                self.render_cli_message("error", "prompt", f"처리 중 오류가 났습니다.\n{exc}"),
                reply_to_message_id=reply_to_message_id,
            )
            self.write_runtime_state(
                status="idle",
                current_job_id=None,
                pid=None,
                prompt_preview=None,
                last_completed_at=time.time(),
                last_error=str(exc),
            )
        finally:
            with self.running_lock:
                if self.running_prompt and self.running_prompt.job_id == running.job_id:
                    self.running_prompt = None

    def append_runtime_status(self, text: str) -> str:
        status, running = self.current_runtime_status()
        if status != "busy" or not running:
            return text
        seconds = int(time.time() - running.started_at)
        extra = "\n".join(
            [
                "",
                "Runtime:",
                "- status: busy",
                f"- currentJobId: {running.job_id}",
                f"- runningForSeconds: {seconds}",
                f"- promptPreview: {running.prompt_preview}",
            ]
        )
        return f"{text}\n{extra}".strip()

    def send_menu(self, chat_id: str, menu: str, reply_to_message_id: int | None = None, notice: str | None = None) -> None:
        text, buttons = self.build_menu(menu)
        if notice:
            text = f"{notice}\n\n{text}"
        self.api.send_message(chat_id, text, reply_to_message_id=reply_to_message_id, inline_keyboard=buttons)

    def handle_message(self, message: dict[str, Any]) -> None:
        chat_id = str(message.get("chat", {}).get("id", "")).strip()
        if chat_id != self.config.allowed_chat_id:
            return
        text = normalize_text(str(message.get("text") or ""))
        if not text:
            return
        message_id = int(message.get("message_id"))
        pending_parent = self.pending_new_folder_parent()
        command = parse_command(text)
        if not command:
            if pending_parent is not None:
                if self.current_runtime_status()[0] == "busy":
                    self.api.send_message(
                        chat_id,
                        self.render_cli_message("relay", "busy", "작업 중에는 새 폴더 세션을 만들 수 없습니다."),
                        reply_to_message_id=message_id,
                    )
                    return
                try:
                    output = self.create_new_folder_session(text)
                except Exception as exc:
                    self.api.send_message(
                        chat_id,
                        self.render_cli_message(
                            "error",
                            "new-session",
                            f"새 폴더 세션 생성에 실패했습니다.\n{exc}\n\n다시 이름을 보내거나 취소 버튼을 누르세요.",
                        ),
                        reply_to_message_id=message_id,
                    )
                    return
                self.api.send_message(
                    chat_id,
                    self.render_cli_message("relay", "new-session", output),
                    reply_to_message_id=message_id,
                )
                self.send_menu(chat_id, "resume")
                return
            busy_error = self.start_prompt(chat_id, text, message_id)
            if busy_error:
                self.api.send_message(
                    chat_id,
                    self.render_cli_message("relay", "busy", busy_error),
                    reply_to_message_id=message_id,
                )
                return
            self.api.send_message(
                chat_id,
                self.render_cli_message("codex", "processing", "Codex에 전달했습니다. 처리 중입니다."),
                reply_to_message_id=message_id,
            )
            return

        name, args = command
        if name in {"help", "start"}:
            self.send_menu(chat_id, "help", reply_to_message_id=message_id)
            return
        notice = f"슬래시 명령은 /help만 지원합니다. `/{name}` 대신 버튼을 사용하세요."
        self.send_menu(chat_id, "help", reply_to_message_id=message_id, notice=notice)

    def handle_callback(self, callback_query: dict[str, Any]) -> None:
        callback_id = str(callback_query.get("id") or "")
        data = normalize_text(str(callback_query.get("data") or ""))
        message = callback_query.get("message") or {}
        chat_id = str(message.get("chat", {}).get("id", "")).strip()
        if chat_id != self.config.allowed_chat_id:
            self.api.answer_callback_query(callback_id)
            return
        action = parse_button_action(data)
        if not action:
            self.api.answer_callback_query(callback_id, "알 수 없는 버튼입니다.")
            return
        kind, value = action
        try:
            if kind == "menu":
                if value != "session-browser":
                    self.set_pending_new_folder_parent(None)
                self.send_menu(chat_id, value or "help")
                self.api.answer_callback_query(callback_id)
                return
            if kind == "read":
                output = self.run_bridge(["read"])
                self.api.send_message(chat_id, self.render_cli_message("relay", "read", output))
                self.api.answer_callback_query(callback_id)
                return
            if kind == "status":
                output = self.run_bridge(["status"])
                self.api.send_message(chat_id, self.render_cli_message("relay", "status", self.append_runtime_status(output)))
                self.api.answer_callback_query(callback_id)
                return
            if kind == "cancel":
                if self.pending_new_folder_parent() is not None:
                    self.set_pending_new_folder_parent(None)
                    self.api.send_message(chat_id, self.render_cli_message("relay", "cancel", "새 폴더 생성 입력을 취소했습니다."))
                    self.send_menu(chat_id, "session-browser")
                    self.api.answer_callback_query(callback_id, "입력 취소")
                    return
                output = self.cancel_running_prompt()
                self.api.send_message(chat_id, self.render_cli_message("relay", "cancel", output))
                self.api.answer_callback_query(callback_id)
                return
            if kind == "resume" and value:
                if self.current_runtime_status()[0] == "busy":
                    self.api.answer_callback_query(callback_id, "작업 중에는 세션 전환을 잠시 막습니다.")
                    return
                output = self.run_bridge(["resume", value])
                self.api.send_message(chat_id, self.render_cli_message("relay", "resume", output))
                self.send_menu(chat_id, "resume")
                self.api.answer_callback_query(callback_id, "세션 전환 완료")
                return
            if kind == "session" and value == "delete":
                if self.current_runtime_status()[0] == "busy":
                    self.api.answer_callback_query(callback_id, "작업 중에는 현재 세션을 삭제할 수 없습니다.")
                    return
                output = self.run_bridge(["delete-session"])
                self.api.send_message(chat_id, self.render_cli_message("relay", "delete-session", output))
                self.send_menu(chat_id, "resume")
                self.api.answer_callback_query(callback_id, "현재 세션 삭제 완료")
                return
            if kind == "sessbrowse" and value:
                parts = value.split("|")
                subaction = parts[0] if parts else ""
                runtime = self.load_runtime_state()
                current_token = str(runtime.get("session_browser_token") or "")
                current_path, current_page, _ = self.session_browser_state()
                if subaction == "start":
                    self.send_menu(chat_id, "session-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if len(parts) < 2 or parts[1] != current_token:
                    self.send_menu(chat_id, "session-browser", notice="세션 브라우저가 갱신되었습니다. 다시 선택하세요.")
                    self.api.answer_callback_query(callback_id, "브라우저를 새로고침했습니다.")
                    return
                if subaction == "up":
                    self.set_pending_new_folder_parent(None)
                    self.set_session_browser_state(current_path.parent if current_path.parent != current_path else current_path, 0)
                    self.send_menu(chat_id, "session-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "page" and len(parts) >= 3:
                    try:
                        target_page = max(int(parts[2]), 0)
                    except ValueError:
                        target_page = 0
                    self.set_pending_new_folder_parent(None)
                    self.set_session_browser_state(current_path, target_page)
                    self.send_menu(chat_id, "session-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "open" and len(parts) >= 3:
                    try:
                        index = int(parts[2])
                    except ValueError:
                        index = -1
                    directories = self.list_browser_directories(current_path)
                    start = current_page * SESSION_BROWSER_PAGE_SIZE
                    visible = directories[start : start + SESSION_BROWSER_PAGE_SIZE]
                    if not (0 <= index < len(visible)):
                        self.send_menu(chat_id, "session-browser", notice="선택한 폴더를 다시 골라주세요.")
                        self.api.answer_callback_query(callback_id, "폴더 목록이 바뀌었습니다.")
                        return
                    self.set_pending_new_folder_parent(None)
                    self.set_session_browser_state(visible[index], 0)
                    self.send_menu(chat_id, "session-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "mkdir":
                    if self.current_runtime_status()[0] == "busy":
                        self.api.answer_callback_query(callback_id, "작업 중에는 새 폴더 세션을 만들 수 없습니다.")
                        return
                    self.set_pending_new_folder_parent(current_path)
                    self.api.send_message(
                        chat_id,
                        self.render_cli_message(
                            "relay",
                            "mkdir",
                            "새 폴더 이름을 다음 메시지로 보내세요.\n"
                            f"- parent: {current_path}\n"
                            "- 취소하려면 취소 버튼",
                        ),
                    )
                    self.api.answer_callback_query(callback_id, "폴더 이름 입력 대기")
                    return
                if subaction == "create":
                    if self.current_runtime_status()[0] == "busy":
                        self.api.answer_callback_query(callback_id, "작업 중에는 새 세션을 만들 수 없습니다.")
                        return
                    self.set_pending_new_folder_parent(None)
                    output = self.run_bridge(["new-session", str(current_path)], timeout_ms=120_000)
                    self.api.send_message(chat_id, self.render_cli_message("relay", "new-session", output))
                    self.send_menu(chat_id, "resume")
                    self.api.answer_callback_query(callback_id, "새 세션 생성 완료")
                    return
                self.api.answer_callback_query(callback_id, "지원하지 않는 세션 버튼입니다.")
                return
            if kind == "resbrowse" and value:
                parts = value.split("|")
                subaction = parts[0] if parts else ""
                runtime = self.load_runtime_state()
                current_token = str(runtime.get("resume_browser_token") or "")
                current_path, current_page, _ = self.resume_browser_state()
                if len(parts) < 2 or parts[1] != current_token:
                    self.send_menu(chat_id, "resume-browser", notice="세션 디렉토리 브라우저가 갱신되었습니다. 다시 선택하세요.")
                    self.api.answer_callback_query(callback_id, "브라우저를 새로고침했습니다.")
                    return
                if subaction == "up":
                    self.set_resume_browser_state(current_path.parent if current_path.parent != current_path else current_path, 0)
                    self.send_menu(chat_id, "resume-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "page" and len(parts) >= 3:
                    try:
                        target_page = max(int(parts[2]), 0)
                    except ValueError:
                        target_page = 0
                    self.set_resume_browser_state(current_path, target_page)
                    self.send_menu(chat_id, "resume-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "open" and len(parts) >= 3:
                    try:
                        index = int(parts[2])
                    except ValueError:
                        index = -1
                    directories = self.list_browser_directories(current_path)
                    start = current_page * SESSION_BROWSER_PAGE_SIZE
                    visible = directories[start : start + SESSION_BROWSER_PAGE_SIZE]
                    if not (0 <= index < len(visible)):
                        self.send_menu(chat_id, "resume-browser", notice="선택한 폴더를 다시 골라주세요.")
                        self.api.answer_callback_query(callback_id, "폴더 목록이 바뀌었습니다.")
                        return
                    self.set_resume_browser_state(visible[index], 0)
                    self.send_menu(chat_id, "resume-browser")
                    self.api.answer_callback_query(callback_id)
                    return
                if subaction == "set":
                    output = self.run_bridge(["set-workdir", str(current_path)])
                    self.write_runtime_state(
                        session_scope_initialized=True,
                        session_scope_user_selected=True,
                        default_scope_origin=str(self.default_scope_path()),
                    )
                    self.api.send_message(chat_id, self.render_cli_message("relay", "set-workdir", output))
                    self.send_menu(chat_id, "resume")
                    self.api.answer_callback_query(callback_id, "현재 디렉토리 설정 완료")
                    return
                self.api.answer_callback_query(callback_id, "지원하지 않는 세션 디렉토리 버튼입니다.")
                return
            if kind == "model" and value:
                output = self.run_bridge(["model", value])
                self.api.send_message(chat_id, self.render_cli_message("relay", "model", output))
                self.send_menu(chat_id, "thinking")
                self.api.answer_callback_query(callback_id, "모델 변경 완료")
                return
            if kind == "fast":
                output = self.run_bridge(["fast", value or "toggle"])
                self.api.send_message(chat_id, self.render_cli_message("relay", "fast", output))
                self.send_menu(chat_id, "help")
                self.api.answer_callback_query(callback_id, "Fast mode 변경 완료")
                return
            if kind == "thinking" and value:
                output = self.run_bridge(["thinking", value])
                state = self.load_bridge_state()
                actual = format_reasoning_value(state.get("reasoning_effort"))
                output = f"{output}\n- 현재 저장값: {actual}"
                self.api.send_message(chat_id, self.render_cli_message("relay", "thinking", output, state=state))
                self.api.answer_callback_query(callback_id, f"thinking 저장: {actual}")
                return
            if kind == "permission" and value:
                output = self.run_bridge(["permission", value])
                self.api.send_message(chat_id, self.render_cli_message("relay", "permission", output))
                self.api.answer_callback_query(callback_id, "권한 변경 완료")
                return
            self.api.answer_callback_query(callback_id, "지원하지 않는 버튼입니다.")
        except Exception as exc:
            self.api.answer_callback_query(callback_id, "오류")
            self.api.send_message(chat_id, self.render_cli_message("error", "callback", f"처리 중 오류가 났습니다.\n{exc}"))

    def process_update(self, update: dict[str, Any]) -> None:
        if "message" in update:
            self.handle_message(update["message"])
        elif "callback_query" in update:
            self.handle_callback(update["callback_query"])

    def run_forever(self) -> None:
        self.api.delete_webhook()
        self.api.set_help_only_commands()
        offset: int | None = None
        while True:
            try:
                updates = self.api.get_updates(offset=offset, timeout=self.config.poll_timeout_seconds)
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    self.process_update(update)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                self.write_runtime_state(last_error=str(exc), last_error_at=time.time())
                time.sleep(2)


def main() -> int:
    config = load_config()
    bot = DirectTelegramCodexBot(config)
    bot.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
