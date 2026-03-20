import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

from telegram_codex_relay.telegram_bot import BotConfig, DirectTelegramCodexBot, RunningPrompt

BRIDGE_PATH = Path(__file__).resolve().parents[1] / "bin" / "codex-bridge"
bridge = SourceFileLoader("codex_bridge_for_tests", str(BRIDGE_PATH)).load_module()


class FakeApi:
    def __init__(self):
        self.sent = []
        self.answered = []
        self.commands = None

    def send_message(self, chat_id, text, *, reply_to_message_id=None, inline_keyboard=None):
        self.sent.append(
            {
                "chat_id": str(chat_id),
                "text": text,
                "reply_to_message_id": reply_to_message_id,
                "inline_keyboard": inline_keyboard,
            }
        )

    def answer_callback_query(self, callback_query_id, text=None):
        self.answered.append({"id": callback_query_id, "text": text})

    def delete_webhook(self):
        return None

    def set_help_only_commands(self):
        self.commands = [{"command": "help", "description": "버튼 메뉴 열기"}]
        return None

    def get_updates(self, offset=None, timeout=30):
        return []


class SimulatedBot(DirectTelegramCodexBot):
    def __init__(self, tmpdir: Path):
        self.fake_session_names = {
            "sess-active": "Primary Session",
            "sess-2": "Second Session",
            "sess-3": "Nested Session",
        }
        self.fake_state = {
            "workdir": str(tmpdir),
            "session_scope_cwd": str(tmpdir),
            "model": "gpt-5.4",
            "reasoning_effort": "low",
            "fast_mode": False,
            "permission": "full",
            "active_session_id": "sess-active",
            "active_session_name": self.fake_session_names["sess-active"],
            "last_execution_session_id": "sess-active",
            "last_execution_session_name": self.fake_session_names["sess-active"],
        }
        self.bridge_calls = []
        self.prompt_calls = []
        self.prompt_error = None
        self.cancel_result = "cancelled"
        self.runtime_busy = False
        self.runtime_job_id = "job-1"
        config = BotConfig(
            bot_token="fake-token",
            allowed_chat_id="111111111",
            workdir=str(tmpdir),
            bridge_path=str(tmpdir / "fake-bridge"),
            state_path=str(tmpdir / "state.json"),
            runtime_state_path=str(tmpdir / "runtime.json"),
            poll_timeout_seconds=1,
        )
        super().__init__(config)
        self.api = FakeApi()

    def load_bridge_state(self):
        return dict(self.fake_state)

    def run_bridge(self, args, stdin_text=None, timeout_ms=25_000):
        self.bridge_calls.append({"args": list(args), "stdin_text": stdin_text})
        if args[:1] == ["sessions-json"]:
            sessions = [
                {
                    "id": "sess-active",
                    "name": self.fake_session_names["sess-active"],
                    "cwd": str(Path(self.config.workdir) / "project-a"),
                    "createdAt": 101,
                    "updatedAt": 111,
                    "active": self.fake_state.get("active_session_id") == "sess-active",
                },
                {
                    "id": "sess-2",
                    "name": self.fake_session_names["sess-2"],
                    "cwd": str(Path(self.config.workdir) / "project-b"),
                    "createdAt": 100,
                    "updatedAt": 110,
                    "active": self.fake_state.get("active_session_id") == "sess-2",
                },
                {
                    "id": "sess-3",
                    "name": self.fake_session_names["sess-3"],
                    "cwd": str(Path(self.config.workdir) / "project-a" / "nested"),
                    "createdAt": 99,
                    "updatedAt": 109,
                    "active": self.fake_state.get("active_session_id") == "sess-3",
                },
            ]
            if len(args) >= 3:
                scope = str(Path(args[2]).resolve())
                prefix = scope if scope == "/" else f"{scope.rstrip('/')}/"
                sessions = [
                    session
                    for session in sessions
                    if str(Path(session["cwd"]).resolve()) == scope
                ]
            return json.dumps(sessions, ensure_ascii=False)
        if args[:1] == ["status"]:
            return (
                "Codex relay 상태:\n"
                "- activeSessionId: sess-active\n"
                f"- sessionScopeCwd: {self.fake_state.get('session_scope_cwd')}\n"
                f"- fastMode: {'on' if self.fake_state.get('fast_mode') else 'off'}"
            )
        if args[:1] == ["read"]:
            return "최근 Codex 출력:\n[1]\nhello"
        if args[:2] == ["resume", "sess-2"]:
            self.fake_state["active_session_id"] = "sess-2"
            self.fake_state["active_session_name"] = self.fake_session_names["sess-2"]
            self.fake_state["workdir"] = str(Path(self.config.workdir) / "project-b")
            return f"Codex 세션을 전환했습니다.\n- id: sess-2\n- name: {self.fake_session_names['sess-2']}\n- cwd: /tmp/project-b"
        if args[:1] == ["new-session"]:
            self.fake_session_names["sess-new"] = "[tg] ~/new-project"
            self.fake_state["active_session_id"] = "sess-new"
            self.fake_state["active_session_name"] = self.fake_session_names["sess-new"]
            self.fake_state["workdir"] = args[1]
            return f"Codex 새 세션을 만들었습니다.\n- id: sess-new\n- cwd: {args[1]}\n- title: {self.fake_session_names['sess-new']}"
        if args[:1] == ["rename-session"]:
            session_id = args[1]
            new_name = args[2]
            self.fake_session_names[session_id] = new_name
            if self.fake_state.get("active_session_id") == session_id:
                self.fake_state["active_session_name"] = new_name
            if self.fake_state.get("last_execution_session_id") == session_id:
                self.fake_state["last_execution_session_name"] = new_name
            return (
                "Codex 세션 이름을 변경했습니다.\n"
                f"- id: {session_id}\n"
                f"- name: {new_name}\n"
                f"- cwd: {self.fake_state.get('workdir')}"
            )
        if args[:1] == ["close-session"]:
            active_id = self.fake_state.get("active_session_id")
            active_name = self.fake_state.get("active_session_name")
            self.fake_state["active_session_id"] = None
            self.fake_state["active_session_name"] = None
            return (
                "현재 Codex 세션을 종료했습니다.\n"
                f"- id: {active_id}\n"
                f"- name: {active_name}\n"
                f"- cwd: {self.fake_state.get('workdir')}\n"
                "- 세션 기록은 유지되며 나중에 다시 이어서 열 수 있습니다.\n"
                "- 다음 평문부터는 새 active 세션으로 시작합니다."
            )
        if args[:1] == ["set-workdir"]:
            self.fake_state["session_scope_cwd"] = args[1]
            return (
                "현재 디렉토리를 저장했습니다.\n"
                f"- cwd: {args[1]}\n"
                "- /resume 목록은 이 폴더와 동일한 cwd 세션만 표시됩니다."
            )
        if args[:1] == ["delete-session"]:
            self.fake_state["active_session_id"] = None
            self.fake_state["active_session_name"] = None
            return "현재 Codex 세션을 삭제했습니다.\n- id: sess-active\n- name: Primary Session\n- cwd: /tmp/project-a"
        if args[:2] == ["model", "gpt-5.4-mini"]:
            self.fake_state["model"] = "gpt-5.4-mini"
            return "Codex 모델 오버라이드를 저장했습니다: gpt-5.4-mini"
        if args[:1] == ["fast"]:
            current = bool(self.fake_state.get("fast_mode"))
            target = not current if len(args) == 1 or args[1] == "toggle" else args[1] in {"on", "true", "1", "fast"}
            self.fake_state["fast_mode"] = target
            if target:
                return "Codex Fast mode를 켰습니다.\n- fast_mode=true\n- fastest inference at 2X plan usage"
            return "Codex Fast mode를 껐습니다.\n- fast_mode=false\n- standard inference mode"
        if args[:2] == ["thinking", "low"]:
            self.fake_state["reasoning_effort"] = "low"
            return "Codex thinking 오버라이드를 저장했습니다: low"
        if args[:2] == ["thinking", "xhigh"]:
            self.fake_state["reasoning_effort"] = "xhigh"
            return "Codex thinking 오버라이드를 저장했습니다: xhigh"
        if args[:2] == ["permission", "read"]:
            self.fake_state["permission"] = "read"
            return "Codex 권한 모드를 read로 저장했습니다.\n- exec flags: isolated one-turn exec with read-only"
        raise AssertionError(f"unexpected bridge args: {args}")

    def start_prompt(self, chat_id, prompt_text, reply_to_message_id):
        self.prompt_calls.append(
            {
                "chat_id": str(chat_id),
                "prompt_text": prompt_text,
                "reply_to_message_id": reply_to_message_id,
            }
        )
        return self.prompt_error

    def current_runtime_status(self):
        if self.runtime_busy:
            class Dummy:
                job_id = "job-1"
                started_at = 0
                prompt_preview = "busy prompt"

            return "busy", Dummy()
        return "idle", None

    def cancel_running_prompt(self):
        return self.cancel_result


class TelegramRelaySimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir_ctx = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_ctx.name)
        (self.tmpdir / "project-a" / "nested").mkdir(parents=True, exist_ok=True)
        (self.tmpdir / "project-b").mkdir(parents=True, exist_ok=True)
        self.bot = SimulatedBot(self.tmpdir)

    def tearDown(self):
        self.tmpdir_ctx.cleanup()

    def test_help_command_sends_menu(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 10, "text": "/help"})
        sent = self.bot.api.sent[-1]
        self.assertIn("Codex 텔레그램 사용법", sent["text"])
        self.assertEqual(sent["reply_to_message_id"], 10)
        self.assertEqual(sent["inline_keyboard"][0][0]["text"], "세션")
        self.assertEqual(sent["inline_keyboard"][1][0]["text"], "Fast")
        self.assertIn("현재 Fast mode: off", sent["text"])

    def test_resume_menu_includes_rename_close_and_delete_buttons(self):
        self.bot.fake_state["session_scope_cwd"] = str(Path(self.bot.config.workdir) / "project-a")
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        text, buttons = self.bot.build_resume_menu()
        self.assertIn("Codex 세션", text)
        self.assertIn("세션 기준 폴더:", text)
        self.assertIn("created:", text)
        self.assertIn(str(Path(self.bot.config.workdir) / "project-a"), text)
        self.assertEqual(buttons[0][0]["text"], "디렉토리 설정")
        self.assertEqual(buttons[0][1]["text"], "새 세션 만들기")
        self.assertEqual(buttons[1][0]["text"], "이름 변경")
        self.assertEqual(buttons[1][1]["text"], "현재 세션 종료")
        self.assertEqual(buttons[2][0]["text"], "현재 세션 삭제")
        self.assertIn("Primary Session", buttons[3][0]["text"])

    def test_resume_menu_filters_sessions_by_current_directory(self):
        self.bot.fake_state["session_scope_cwd"] = str(Path(self.bot.config.workdir) / "project-a")
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        text, _ = self.bot.build_resume_menu()
        self.assertIn(str(Path(self.bot.config.workdir) / "project-a"), text)
        self.assertNotIn(str(Path(self.bot.config.workdir) / "project-a" / "nested"), text)
        self.assertNotIn(str(Path(self.bot.config.workdir) / "project-b"), text)
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["sessions-json", "12", str(Path(self.bot.config.workdir) / "project-a")])

    def test_resume_menu_initializes_scope_to_config_workdir_once(self):
        stale_scope = Path(self.bot.config.workdir) / "project-b"
        self.bot.fake_state["session_scope_cwd"] = str(stale_scope)
        text, _ = self.bot.build_resume_menu()
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["set-workdir", str(Path(self.bot.config.workdir))])
        self.assertEqual(self.bot.bridge_calls[1]["args"], ["sessions-json", "12", str(Path(self.bot.config.workdir))])
        self.assertIn(str(Path(self.bot.config.workdir)), text)

    def test_model_callback_sets_model_and_opens_thinking_menu(self):
        self.bot.handle_callback(
            {
                "id": "cb-1",
                "data": "tgbtn:model:gpt-5.4-mini",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["model", "gpt-5.4-mini"])
        self.assertIn("relay> model", self.bot.api.sent[0]["text"])
        self.assertIn("Codex 모델 오버라이드를 저장했습니다: gpt-5.4-mini", self.bot.api.sent[0]["text"])
        self.assertIn("Codex thinking 선택", self.bot.api.sent[1]["text"])
        self.assertEqual(self.bot.api.answered[-1]["text"], "모델 변경 완료")

    def test_resume_callback_switches_session(self):
        self.bot.handle_callback(
            {
                "id": "cb-2",
                "data": "tgbtn:resume:sess-2",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["resume", "sess-2"])
        self.assertIn("Second Session", self.bot.api.sent[-1]["text"])

    def test_fast_command_redirects_to_help(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 76, "text": "/fast"})
        sent = self.bot.api.sent[-1]
        self.assertIn("슬래시 명령은 /help만 지원합니다.", sent["text"])
        self.assertIn("`/fast` 대신 버튼을 사용하세요.", sent["text"])
        self.assertIn("Codex 텔레그램 사용법", sent["text"])

    def test_fast_callback_toggles_fast_mode(self):
        self.bot.handle_callback(
            {
                "id": "cb-fast",
                "data": "tgbtn:fast:toggle",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["fast", "toggle"])
        self.assertIn("Codex Fast mode를 켰습니다.", self.bot.api.sent[0]["text"])
        self.assertIn("현재 Fast mode: on", self.bot.api.sent[1]["text"])
        self.assertEqual(self.bot.api.answered[-1]["text"], "Fast mode 변경 완료")

    def test_plain_text_starts_prompt_and_sends_processing_notice(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 77, "text": "파일 하나 만들어줘"})
        self.assertEqual(self.bot.prompt_calls[0]["prompt_text"], "파일 하나 만들어줘")
        self.assertIn("codex> processing", self.bot.api.sent[-1]["text"])
        self.assertIn("Codex에 전달했습니다. 처리 중입니다.", self.bot.api.sent[-1]["text"])

    def test_busy_prompt_returns_busy_message(self):
        self.bot.prompt_error = "이미 Codex 작업이 실행 중입니다."
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 78, "text": "또 작업"})
        self.assertIn("relay> busy", self.bot.api.sent[-1]["text"])
        self.assertIn("이미 Codex 작업이 실행 중입니다.", self.bot.api.sent[-1]["text"])

    def test_status_button_appends_runtime_when_busy(self):
        self.bot.runtime_busy = True
        self.bot.handle_callback(
            {
                "id": "cb-status",
                "data": "tgbtn:status",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertIn("relay> status", self.bot.api.sent[-1]["text"])
        self.assertIn("Runtime:", self.bot.api.sent[-1]["text"])
        self.assertIn("activeSessionId: sess-active", self.bot.api.sent[-1]["text"])
        self.assertIn("fastMode: off", self.bot.api.sent[-1]["text"])

    def test_permission_callback_updates_mode(self):
        self.bot.handle_callback(
            {
                "id": "cb-3",
                "data": "tgbtn:permission:read",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["permission", "read"])
        self.assertIn("isolated one-turn", self.bot.api.sent[-1]["text"])

    def test_session_browser_create_calls_new_session(self):
        browser_root = self.tmpdir / "browser-root"
        (browser_root / "alpha").mkdir(parents=True)
        self.bot.write_runtime_state(session_browser_path=str(browser_root), session_browser_page=0, session_browser_token="token-1")
        self.bot.handle_callback(
            {
                "id": "cb-4",
                "data": "tgbtn:sessbrowse:create|token-1",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["new-session", str(browser_root)])
        self.assertIn("Codex 새 세션을 만들었습니다.", self.bot.api.sent[0]["text"])

    def test_session_browser_lists_full_visible_paths(self):
        browser_root = self.tmpdir / "browser-root"
        long_name = "a-very-long-directory-name-for-browser-check"
        (browser_root / long_name).mkdir(parents=True)
        self.bot.write_runtime_state(session_browser_path=str(browser_root), session_browser_page=0, session_browser_token="token-1")
        text, buttons = self.bot.build_session_browser_menu()
        self.assertIn(str(browser_root / long_name), text)
        labels = [button["text"] for row in buttons for button in row]
        self.assertIn("../", labels)
        self.assertIn("현재 폴더로 세션 시작", labels)
        self.assertIn("새 폴더 만들기", labels)

    def test_resume_browser_shows_directory_and_session_preview(self):
        browser_root = self.tmpdir / "project-a"
        (browser_root / "nested").mkdir(parents=True, exist_ok=True)
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        self.bot.write_runtime_state(resume_browser_path=str(browser_root), resume_browser_page=0, resume_browser_token="token-r")
        text, buttons = self.bot.build_resume_browser_menu()
        self.assertIn("세션 디렉토리 선택", text)
        self.assertIn("현재 /resume 기준 폴더", text)
        self.assertIn("Primary Session", text)
        self.assertNotIn("Nested Session", text)
        labels = [button["text"] for row in buttons for button in row]
        self.assertIn("이 폴더를 현재 디렉토리로 설정", labels)

    def test_resume_browser_set_updates_current_directory(self):
        target = self.tmpdir / "project-b"
        target.mkdir(parents=True, exist_ok=True)
        self.bot.write_runtime_state(resume_browser_path=str(target), resume_browser_page=0, resume_browser_token="token-r")
        self.bot.handle_callback(
            {
                "id": "cb-r1",
                "data": "tgbtn:resbrowse:set|token-r",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["set-workdir", str(target)])
        self.assertIn("relay> set-workdir", self.bot.api.sent[0]["text"])
        self.assertIn("현재 디렉토리를 저장했습니다.", self.bot.api.sent[0]["text"])
        self.assertIn("세션 기준 폴더:", self.bot.api.sent[1]["text"])
        self.assertIn(str(target), self.bot.api.sent[1]["text"])

    def test_resume_scope_persists_after_resuming_other_session(self):
        scope = Path(self.bot.config.workdir) / "project-a"
        self.bot.fake_state["session_scope_cwd"] = str(scope)
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        self.bot.handle_callback(
            {
                "id": "cb-2",
                "data": "tgbtn:resume:sess-2",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.bot.bridge_calls.clear()
        text, _ = self.bot.build_resume_menu()
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["sessions-json", "12", str(scope)])
        self.assertIn(str(scope), text)

    def test_new_folder_message_creates_directory_and_session(self):
        parent = self.tmpdir / "parent"
        parent.mkdir()
        self.bot.set_pending_new_folder_parent(parent)
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 82, "text": "fresh-folder"})
        self.assertTrue((parent / "fresh-folder").is_dir())
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["new-session", str(parent / "fresh-folder")])
        self.assertIsNone(self.bot.pending_new_folder_parent())

    def test_cancel_command_redirects_to_help(self):
        parent = self.tmpdir / "parent"
        parent.mkdir()
        self.bot.set_pending_new_folder_parent(parent)
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 83, "text": "/cancel"})
        self.assertEqual(self.bot.pending_new_folder_parent(), parent)
        self.assertIn("슬래시 명령은 /help만 지원합니다.", self.bot.api.sent[-1]["text"])

    def test_run_forever_registers_help_only_command(self):
        updates = [{"update_id": 1, "message": {"chat": {"id": 111111111}, "message_id": 1, "text": "/help"}}]

        def fake_get_updates(offset=None, timeout=30):
            if updates:
                return [updates.pop(0)]
            raise KeyboardInterrupt

        self.bot.api.get_updates = fake_get_updates
        with self.assertRaises(KeyboardInterrupt):
            self.bot.run_forever()
        self.assertEqual(self.bot.api.commands, [{"command": "help", "description": "버튼 메뉴 열기"}])

    def test_session_delete_deletes_current_active_session(self):
        self.bot.handle_callback(
            {
                "id": "cb-5",
                "data": "tgbtn:session:delete",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["delete-session"])
        self.assertIn("relay> delete-session", self.bot.api.sent[0]["text"])
        self.assertIn("현재 Codex 세션을 삭제했습니다.", self.bot.api.sent[0]["text"])

    def test_session_rename_button_requests_next_message(self):
        self.bot.handle_callback(
            {
                "id": "cb-rename",
                "data": "tgbtn:session:rename",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.pending_session_rename(), ("sess-active", "Primary Session"))
        self.assertIn("새 세션 이름을 다음 메시지로 보내세요.", self.bot.api.sent[0]["text"])
        self.assertIn("세션 이름 변경 입력 대기 중", self.bot.api.sent[1]["text"])
        self.assertEqual(self.bot.api.answered[-1]["text"], "새 이름 입력 대기")

    def test_pending_session_rename_message_updates_session_name(self):
        self.bot.fake_state["session_scope_cwd"] = str(Path(self.bot.config.workdir) / "project-a")
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        self.bot.set_pending_session_rename("sess-active", "Primary Session")
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 84, "text": "Telegram Renamed Session"})
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["rename-session", "sess-active", "Telegram Renamed Session"])
        self.assertEqual(self.bot.pending_session_rename(), (None, None))
        self.assertEqual(self.bot.fake_state["active_session_name"], "Telegram Renamed Session")
        self.assertEqual(self.bot.fake_state["last_execution_session_name"], "Telegram Renamed Session")
        self.assertIn("relay> rename-session", self.bot.api.sent[0]["text"])
        self.assertIn("Codex 세션 이름을 변경했습니다.", self.bot.api.sent[0]["text"])
        self.assertIn("Telegram Renamed Session", self.bot.api.sent[1]["text"])

    def test_session_close_closes_current_active_session_without_archiving(self):
        self.bot.fake_state["session_scope_cwd"] = str(Path(self.bot.config.workdir) / "project-a")
        self.bot.write_runtime_state(session_scope_initialized=True, session_scope_user_selected=True)
        self.bot.handle_callback(
            {
                "id": "cb-6",
                "data": "tgbtn:session:close",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["close-session"])
        self.assertIn("relay> close-session", self.bot.api.sent[0]["text"])
        self.assertIn("현재 Codex 세션을 종료했습니다.", self.bot.api.sent[0]["text"])
        self.assertIsNone(self.bot.fake_state["active_session_id"])
        self.assertEqual(self.bot.fake_state["last_execution_session_id"], "sess-active")
        self.assertIn("현재 세션: (none)", self.bot.api.sent[1]["text"])
        self.assertIn("Primary Session", self.bot.api.sent[1]["text"])

    def test_unknown_command_redirects_to_help(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 80, "text": "/unknown"})
        self.assertIn("슬래시 명령은 /help만 지원합니다.", self.bot.api.sent[-1]["text"])
        self.assertIn("Codex 텔레그램 사용법", self.bot.api.sent[-1]["text"])

    def test_wait_prompt_uses_communicate_input(self):
        class FakeProcess:
            def __init__(self):
                self.returncode = 0
                self.received_input = None
                self.pid = 1234

            def communicate(self, input=None, timeout=None):
                self.received_input = input
                return "DIRECT_PROMPT_OK", ""

            def poll(self):
                return None

        process = FakeProcess()
        running = RunningPrompt(
            job_id="job-test",
            process=process,
            started_at=0,
            prompt_preview="prompt",
        )

        with patch.object(self.bot, "write_runtime_state") as write_runtime_state:
            self.bot._wait_prompt("111111111", 81, running, "reply with ok")

        self.assertEqual(process.received_input, "reply with ok\n")
        self.assertIn("codex> reply", self.bot.api.sent[-1]["text"])
        self.assertIn("DIRECT_PROMPT_OK", self.bot.api.sent[-1]["text"])
        write_runtime_state.assert_called()


class CodexBridgeUnitTests(unittest.TestCase):
    def make_thread(self, thread_id: str, title: str) -> bridge.ThreadEntry:
        return bridge.ThreadEntry(
            id=thread_id,
            title=title,
            cwd=f"/tmp/{thread_id}",
            created_at=100,
            updated_at=110,
            rollout_path=f"/tmp/{thread_id}.jsonl",
            sandbox_policy="danger-full-access",
            approval_mode="never",
            model_provider="openai",
            cli_version="0.0.0",
        )

    def test_cmd_read_prefers_active_session_over_last_execution(self):
        state = {
            "active_session_id": "active",
            "last_execution_session_id": "older",
            "last_execution_session_name": "Older Session",
        }

        def fake_get_thread(thread_id):
            if thread_id == "active":
                return self.make_thread("active", "Active Session")
            if thread_id == "older":
                return self.make_thread("older", "Older Session")
            return None

        def fake_thread_output_messages(thread, limit=5):
            if thread.id == "active":
                return ["active output"]
            return ["older output"]

        with patch.object(bridge, "get_thread", side_effect=fake_get_thread), patch.object(
            bridge, "thread_output_messages", side_effect=fake_thread_output_messages
        ):
            output = bridge.cmd_read(state, None)

        self.assertIn("Active Session", output)
        self.assertIn("active output", output)

    def test_cmd_fast_toggles_real_fast_mode(self):
        state = {"fast_mode": False}

        output = bridge.cmd_fast(state, None)

        self.assertEqual(state["fast_mode"], True)
        self.assertIn("fast_mode=true", output)
        self.assertIn("2X plan usage", output)

    def test_cmd_close_session_clears_active_only(self):
        state = {
            "active_session_id": "sess-active",
            "active_session_name": "Primary Session",
            "workdir": "/tmp/project-a",
            "last_execution_session_id": "sess-active",
            "last_execution_session_name": "Primary Session",
        }
        thread = bridge.ThreadEntry(
            id="sess-active",
            title="Primary Session",
            cwd="/tmp/project-a",
            created_at=100,
            updated_at=200,
            rollout_path="/tmp/project-a/rollout.jsonl",
            sandbox_policy="danger-full-access",
            approval_mode="never",
            model_provider="openai",
            cli_version="0.0.0",
        )

        with patch.object(bridge, "sync_state_to_threads"), patch.object(bridge, "get_thread", return_value=thread), patch.object(
            bridge, "save_state"
        ) as save_state:
            output = bridge.cmd_close_session(state)

        self.assertIsNone(state["active_session_id"])
        self.assertIsNone(state["active_session_name"])
        self.assertEqual(state["last_execution_session_id"], "sess-active")
        self.assertIn("현재 Codex 세션을 종료했습니다.", output)
        self.assertIn("세션 기록은 유지되며 나중에 다시 이어서 열 수 있습니다.", output)
        save_state.assert_called_once_with(state)

    def test_cmd_rename_session_updates_db_session_index_and_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "state.sqlite"
            state_path = tmpdir_path / "bridge_state.json"
            session_index_path = tmpdir_path / "session_index.jsonl"
            thread_id = "019d096c-7476-7b53-ae4e-faec75f9231d"
            self.create_state_db(db_path, thread_id=thread_id, title="Original Title", updated_at=100)
            state = {
                "active_session_id": thread_id,
                "active_session_name": "Original Title",
                "last_execution_session_id": thread_id,
                "last_execution_session_name": "Original Title",
                "workdir": "/tmp/project-a",
                "session_scope_cwd": "/tmp/project-a",
                "last_list": [],
            }

            with patch.object(bridge, "STATE_PATH", state_path), patch.object(bridge, "SESSION_INDEX_PATH", session_index_path), patch.object(
                bridge, "state_db_path", return_value=db_path
            ):
                output = bridge.cmd_rename_session(state, thread_id, "Renamed From Telegram")
                payload = json.loads(bridge.cmd_sessions_json(state, "5", "/tmp/project-a"))

            self.assertIn("Codex 세션 이름을 변경했습니다.", output)
            self.assertEqual(state["active_session_name"], "Renamed From Telegram")
            self.assertEqual(state["last_execution_session_name"], "Renamed From Telegram")
            self.assertEqual(payload[0]["name"], "Renamed From Telegram")
            session_index_lines = session_index_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertTrue(session_index_lines)
            last_entry = json.loads(session_index_lines[-1])
            self.assertEqual(last_entry["id"], thread_id)
            self.assertEqual(last_entry["thread_name"], "Renamed From Telegram")
            conn = sqlite3.connect(db_path)
            row = conn.execute("select title from threads where id = ?", (thread_id,)).fetchone()
            conn.close()
            self.assertEqual(row[0], "Renamed From Telegram")

    def test_current_scope_cwd_uses_separate_scope_field(self):
        state = {"workdir": "/tmp/active", "session_scope_cwd": "/tmp/scope"}

        self.assertEqual(bridge.current_scope_cwd(state), "/tmp/scope")

    def create_state_db(self, path: Path, *, thread_id: str, title: str, updated_at: int):
        conn = sqlite3.connect(path)
        conn.execute(
            """
            create table threads (
                id text primary key,
                rollout_path text not null,
                created_at integer not null,
                updated_at integer not null,
                source text not null,
                model_provider text not null,
                cwd text not null,
                title text not null,
                sandbox_policy text not null,
                approval_mode text not null,
                tokens_used integer not null default 0,
                has_user_event integer not null default 0,
                archived integer not null default 0,
                archived_at integer,
                git_sha text,
                git_branch text,
                git_origin_url text,
                cli_version text not null default '',
                first_user_message text not null default '',
                agent_nickname text,
                agent_role text,
                memory_mode text not null default 'enabled',
                model text,
                reasoning_effort text
            )
            """
        )
        conn.execute(
            """
            insert into threads (
                id, rollout_path, created_at, updated_at, source, model_provider, cwd, title,
                sandbox_policy, approval_mode, archived, cli_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                thread_id,
                str(path.with_suffix(".jsonl")),
                100,
                updated_at,
                "cli",
                "openai",
                "/tmp/project-a",
                title,
                "danger-full-access",
                "never",
                "0.0.0",
            ),
        )
        conn.commit()
        conn.close()

    def session_index_timestamp(self, epoch_seconds: int) -> str:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def test_cmd_sessions_json_prefers_renamed_session_index_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "state.sqlite"
            state_path = tmpdir_path / "bridge_state.json"
            session_index_path = tmpdir_path / "session_index.jsonl"
            self.create_state_db(db_path, thread_id="sess-1", title="Original Title", updated_at=100)
            session_index_path.write_text(
                json.dumps(
                    {
                        "id": "sess-1",
                        "thread_name": "Renamed From TUI",
                        "updated_at": self.session_index_timestamp(200),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            state = {
                "active_session_id": "sess-1",
                "active_session_name": "Original Title",
                "workdir": "/tmp/project-a",
                "session_scope_cwd": "/tmp/project-a",
                "last_list": [],
            }

            with patch.object(bridge, "STATE_PATH", state_path), patch.object(bridge, "SESSION_INDEX_PATH", session_index_path), patch.object(
                bridge, "state_db_path", return_value=db_path
            ):
                payload = json.loads(bridge.cmd_sessions_json(state, "5", "/tmp/project-a"))

            self.assertEqual(payload[0]["name"], "Renamed From TUI")
            self.assertEqual(state["active_session_name"], "Renamed From TUI")

    def test_list_threads_keeps_newer_db_title_when_session_index_is_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "state.sqlite"
            session_index_path = tmpdir_path / "session_index.jsonl"
            self.create_state_db(db_path, thread_id="sess-1", title="[tg] ~/project-a", updated_at=300)
            session_index_path.write_text(
                json.dumps(
                    {
                        "id": "sess-1",
                        "thread_name": "Old Picker Name",
                        "updated_at": self.session_index_timestamp(200),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(bridge, "SESSION_INDEX_PATH", session_index_path), patch.object(bridge, "state_db_path", return_value=db_path):
                threads = bridge.list_threads(limit=5, cwd_filter="/tmp/project-a")

            self.assertEqual(threads[0].title, "[tg] ~/project-a")


if __name__ == "__main__":
    unittest.main()
