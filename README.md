# codex-telegram-bridge

`Telegram DM -> direct bot -> codex-bridge -> Codex CLI` 구조로 Codex를 텔레그램에서 제어하는 레포입니다. `OpenClaw`는 사용하지 않습니다.

이 레포의 목표는 다음과 같습니다.

- 어디서 클론해도 레포 내부 파일만으로 설치 흐름을 따라갈 수 있음
- 텔레그램 봇 생성, `chat_id` 확인, 서비스 설치를 문서와 스크립트로 재현 가능하게 제공
- 실제 비밀값(`bot_token`, 실제 `chat_id`, 런타임 상태)은 커밋하지 않음

빠른 시작:

1. [docs/README.md](docs/README.md)를 먼저 읽습니다.
2. [docs/setup/telegram.md](docs/setup/telegram.md)에서 `BotFather`로 봇을 만듭니다.
3. `telegram_codex_relay/config.example.json`을 복사해 `telegram_codex_relay/config.json`을 만들고 값을 채웁니다.
4. [docs/setup/install.md](docs/setup/install.md) 순서대로 테스트와 서비스 설치를 진행합니다.

현재 기능:

- 평문 메시지는 현재 active `Codex` 세션으로 바로 전달
- Telegram 슬래시 명령은 `/help`만 지원
- 봇 시작 시 `setMyCommands`로 `/help`만 등록
- `/help`는 버튼 메뉴 표시
- `세션`, `모델`, `Fast`, `Thinking`, `권한`, `최근 출력`, `현재 상태`, `취소` 버튼 지원
- `Fast`는 실제 Codex `fast_mode` 토글이며, 터미널 `/fast`와 같은 `2X plan usage` 모드
- 세션 메뉴에서 `디렉토리 설정` 버튼으로 현재 `/resume` 기준 폴더를 바꿀 수 있음
- 세션 메뉴는 현재 디렉토리와 동일한 `cwd` 세션만 보여줌
- 세션 디렉토리 브라우저는 폴더를 타고 들어가며 현재 폴더의 세션 미리보기를 보여줌
- 세션 브라우저에서 `~/`부터 현재 폴더의 바로 아래 하위 폴더만 보여주며, `../`로 다시 올라갈 수 있음
- 현재 폴더로 세션 시작 또는 새 폴더를 만든 뒤 세션 시작 가능
- 현재 active 세션만 버튼으로 archive 삭제
- 세션 목록에 전체 경로와 생성/수정 시각 표시
- `현재 상태`에 컨텍스트 잔량 근사치와 `sessionScopeCwd` 표시

운영 참고:

- `Telegram Bot API`는 기본적으로 무료입니다.
- `Codex`는 계속 OpenAI 쪽을 사용하므로 플랜/사용량 한도 영향은 남습니다.
- 외부 API를 완전히 없애려면 `Codex`를 버리고 로컬 모델 경로로 다시 설계해야 합니다.
