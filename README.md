# codex-telegram-bridge

`Telegram DM -> direct bot -> codex-bridge -> Codex CLI` 구조로 Codex를 텔레그램에서 제어하는 레포입니다. `OpenClaw`는 사용하지 않습니다.

이 레포는 다음 목적에 맞춰 정리되어 있습니다.

- 텔레그램 봇 생성부터 서비스 설치까지 레포 내부 문서와 스크립트만으로 재현 가능
- 런타임은 레포 내부 `.venv`로 고정
- 실제 비밀값과 런타임 상태는 커밋 제외

시작 순서:

1. [docs/README.md](docs/README.md)
2. [docs/setup/telegram.md](docs/setup/telegram.md)
3. [docs/setup/install.md](docs/setup/install.md)

현재 기능, 현재 제약, 현재 검증 상태는 [docs/status.md](docs/status.md)만 기준으로 봅니다.
