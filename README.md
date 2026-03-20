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
- `/help`는 버튼 메뉴 표시
- `세션`, `모델`, `Thinking`, `권한`, `최근 출력`, `현재 상태`, `취소` 버튼 지원
- 세션 브라우저에서 `~/`부터 폴더를 내려가며 새 세션 생성
- 현재 active 세션만 버튼으로 archive 삭제
- `/status`에 컨텍스트 잔량 근사치 표시

운영 참고:

- `Telegram Bot API`는 기본적으로 무료입니다.
- `Codex`는 계속 OpenAI 쪽을 사용하므로 플랜/사용량 한도 영향은 남습니다.
- 외부 API를 완전히 없애려면 `Codex`를 버리고 로컬 모델 경로로 다시 설계해야 합니다.
