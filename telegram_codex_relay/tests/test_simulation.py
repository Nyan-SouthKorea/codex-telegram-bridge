import json
import tempfile
import unittest
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

    def get_updates(self, offset=None, timeout=30):
        return []


class SimulatedBot(DirectTelegramCodexBot):
    def __init__(self, tmpdir: Path):
        self.fake_state = {
            "workdir": str(tmpdir),
            "model": "gpt-5.4",
            "reasoning_effort": "low",
            "permission": "full",
            "active_session_id": "sess-active",
            "active_session_name": "Primary Session",
            "last_execution_session_id": "sess-active",
            "last_execution_session_name": "Primary Session",
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
                    "name": "Primary Session",
                    "cwd": str(Path(self.config.workdir) / "project-a"),
                    "createdAt": 101,
                    "updatedAt": 111,
                    "active": True,
                },
                {
                    "id": "sess-2",
                    "name": "Second Session",
                    "cwd": str(Path(self.config.workdir) / "project-b"),
                    "createdAt": 100,
                    "updatedAt": 110,
                    "active": False,
                },
                {
                    "id": "sess-3",
                    "name": "Nested Session",
                    "cwd": str(Path(self.config.workdir) / "project-a" / "nested"),
                    "createdAt": 99,
                    "updatedAt": 109,
                    "active": False,
                },
            ]
            if len(args) >= 3:
                scope = str(Path(args[2]).resolve())
                prefix = scope if scope == "/" else f"{scope.rstrip('/')}/"
                sessions = [
                    session
                    for session in sessions
                    if str(Path(session["cwd"]).resolve()) == scope or str(Path(session["cwd"]).resolve()).startswith(prefix)
                ]
            return json.dumps(sessions, ensure_ascii=False)
        if args[:1] == ["status"]:
            return "Codex relay 상태:\n- activeSessionId: sess-active"
        if args[:1] == ["read"]:
            return "최근 Codex 출력:\n[1]\nhello"
        if args[:2] == ["resume", "sess-2"]:
            self.fake_state["active_session_id"] = "sess-2"
            self.fake_state["active_session_name"] = "Second Session"
            self.fake_state["workdir"] = str(Path(self.config.workdir) / "project-b")
            return "Codex 세션을 전환했습니다.\n- id: sess-2\n- name: Second Session\n- cwd: /tmp/project-b"
        if args[:1] == ["new-session"]:
            self.fake_state["active_session_id"] = "sess-new"
            self.fake_state["active_session_name"] = "[tg] ~/new-project"
            self.fake_state["workdir"] = args[1]
            return f"Codex 새 세션을 만들었습니다.\n- id: sess-new\n- cwd: {args[1]}\n- title: [tg] ~/new-project"
        if args[:1] == ["set-workdir"]:
            self.fake_state["workdir"] = args[1]
            return (
                "현재 디렉토리를 저장했습니다.\n"
                f"- cwd: {args[1]}\n"
                "- /resume 목록은 이 폴더와 하위 폴더 기준으로 표시됩니다."
            )
        if args[:1] == ["delete-session"]:
            self.fake_state["active_session_id"] = None
            self.fake_state["active_session_name"] = None
            return "현재 Codex 세션을 삭제했습니다.\n- id: sess-active\n- name: Primary Session\n- cwd: /tmp/project-a"
        if args[:2] == ["model", "gpt-5.4-mini"]:
            self.fake_state["model"] = "gpt-5.4-mini"
            return "Codex 모델 오버라이드를 저장했습니다: gpt-5.4-mini"
        if args[:2] == ["thinking", "fast"]:
            self.fake_state["reasoning_effort"] = "low"
            return "Codex thinking 오버라이드를 저장했습니다: low\n- Fast는 `model_reasoning_effort=low` 별칭입니다."
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
        self.assertEqual(sent["inline_keyboard"][1][0]["text"], "Low (Fast)")

    def test_resume_menu_includes_create_and_delete_buttons(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 11, "text": "/resume"})
        sent = self.bot.api.sent[-1]
        self.assertIn("Codex 세션", sent["text"])
        self.assertIn("세션 기준 폴더:", sent["text"])
        self.assertIn("created:", sent["text"])
        self.assertIn(str(Path(self.bot.config.workdir) / "project-a"), sent["text"])
        self.assertEqual(sent["inline_keyboard"][0][0]["text"], "디렉토리 설정")
        self.assertEqual(sent["inline_keyboard"][0][1]["text"], "새 세션 만들기")
        self.assertEqual(sent["inline_keyboard"][1][0]["text"], "현재 세션 삭제")

    def test_resume_menu_filters_sessions_by_current_directory(self):
        self.bot.fake_state["workdir"] = str(Path(self.bot.config.workdir) / "project-a")
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 12, "text": "/resume"})
        sent = self.bot.api.sent[-1]
        self.assertIn(str(Path(self.bot.config.workdir) / "project-a"), sent["text"])
        self.assertIn(str(Path(self.bot.config.workdir) / "project-a" / "nested"), sent["text"])
        self.assertNotIn(str(Path(self.bot.config.workdir) / "project-b"), sent["text"])
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["sessions-json", "12", str(Path(self.bot.config.workdir) / "project-a")])

    def test_model_callback_sets_model_and_opens_thinking_menu(self):
        self.bot.handle_callback(
            {
                "id": "cb-1",
                "data": "tgbtn:model:gpt-5.4-mini",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["model", "gpt-5.4-mini"])
        self.assertEqual(self.bot.api.sent[0]["text"], "Codex 모델 오버라이드를 저장했습니다: gpt-5.4-mini")
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

    def test_fast_command_redirects_to_thinking_menu(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 76, "text": "/fast"})
        sent = self.bot.api.sent[-1]
        self.assertIn("thinking 변경은 Thinking 버튼 메뉴에서 선택합니다.", sent["text"])
        self.assertIn("Codex thinking 선택", sent["text"])
        self.assertIn("Fast는 `model_reasoning_effort=low`를 저장하는 별칭입니다.", sent["text"])

    def test_fast_callback_reports_saved_low_state(self):
        self.bot.handle_callback(
            {
                "id": "cb-fast",
                "data": "tgbtn:thinking:fast",
                "message": {"chat": {"id": 111111111}},
            }
        )
        sent = self.bot.api.sent[-1]
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["thinking", "fast"])
        self.assertIn("Codex thinking 오버라이드를 저장했습니다: low", sent["text"])
        self.assertIn("현재 저장값: low (Fast)", sent["text"])
        self.assertIn("토큰 생성 속도 2배를 보장하지 않습니다.", sent["text"])
        self.assertEqual(self.bot.api.answered[-1]["text"], "thinking 저장: low (Fast)")

    def test_plain_text_starts_prompt_and_sends_processing_notice(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 77, "text": "파일 하나 만들어줘"})
        self.assertEqual(self.bot.prompt_calls[0]["prompt_text"], "파일 하나 만들어줘")
        self.assertEqual(self.bot.api.sent[-1]["text"], "Codex에 전달했습니다. 처리 중입니다.")

    def test_busy_prompt_returns_busy_message(self):
        self.bot.prompt_error = "이미 Codex 작업이 실행 중입니다."
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 78, "text": "또 작업"})
        self.assertEqual(self.bot.api.sent[-1]["text"], "이미 Codex 작업이 실행 중입니다.")

    def test_status_command_appends_runtime_when_busy(self):
        self.bot.runtime_busy = True
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 79, "text": "/status"})
        self.assertIn("Runtime:", self.bot.api.sent[-1]["text"])
        self.assertIn("activeSessionId: sess-active", self.bot.api.sent[-1]["text"])

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
        self.bot.write_runtime_state(resume_browser_path=str(browser_root), resume_browser_page=0, resume_browser_token="token-r")
        text, buttons = self.bot.build_resume_browser_menu()
        self.assertIn("세션 디렉토리 선택", text)
        self.assertIn("현재 /resume 기준 폴더", text)
        self.assertIn("Primary Session", text)
        self.assertIn("Nested Session", text)
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
        self.assertIn("현재 디렉토리를 저장했습니다.", self.bot.api.sent[0]["text"])
        self.assertIn("세션 기준 폴더:", self.bot.api.sent[1]["text"])

    def test_new_folder_message_creates_directory_and_session(self):
        parent = self.tmpdir / "parent"
        parent.mkdir()
        self.bot.set_pending_new_folder_parent(parent)
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 82, "text": "fresh-folder"})
        self.assertTrue((parent / "fresh-folder").is_dir())
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["new-session", str(parent / "fresh-folder")])
        self.assertIsNone(self.bot.pending_new_folder_parent())

    def test_cancel_clears_pending_new_folder_input(self):
        parent = self.tmpdir / "parent"
        parent.mkdir()
        self.bot.set_pending_new_folder_parent(parent)
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 83, "text": "/cancel"})
        self.assertIsNone(self.bot.pending_new_folder_parent())
        self.assertIn("새 폴더 생성 입력을 취소했습니다.", self.bot.api.sent[0]["text"])

    def test_session_delete_deletes_current_active_session(self):
        self.bot.handle_callback(
            {
                "id": "cb-5",
                "data": "tgbtn:session:delete",
                "message": {"chat": {"id": 111111111}},
            }
        )
        self.assertEqual(self.bot.bridge_calls[0]["args"], ["delete-session"])
        self.assertIn("현재 Codex 세션을 삭제했습니다.", self.bot.api.sent[0]["text"])

    def test_unknown_command_redirects_to_help(self):
        self.bot.handle_message({"chat": {"id": 111111111}, "message_id": 80, "text": "/unknown"})
        self.assertIn("지원하지 않는 명령입니다", self.bot.api.sent[-1]["text"])
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

    def test_cmd_thinking_fast_is_explicit_low_alias(self):
        state = {"reasoning_effort": "xhigh"}

        output = bridge.cmd_thinking(state, "fast")

        self.assertEqual(state["reasoning_effort"], "low")
        self.assertIn("저장했습니다: low", output)
        self.assertIn("Fast는 `model_reasoning_effort=low` 별칭", output)


if __name__ == "__main__":
    unittest.main()
