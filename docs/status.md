# Current Status

## 프로젝트 목표

이 레포는 `Telegram DM`에서 `Codex CLI`를 직접 제어하는 브리지를 제공합니다.  
현재 기준 아키텍처는 `Telegram Bot API -> telegram_bot.py -> codex-bridge -> codex exec`입니다.  
운영 런타임은 레포 내부 `.venv`입니다.

## 현재 구현 상태

- `OpenClaw` 의존 없음
- 로컬 LLM 의존 없음
- 평문 메시지는 active `Codex` 세션으로 전달
- Telegram 슬래시 명령은 `/help`만 허용
- 봇 시작 시 `setMyCommands`로 `/help`만 등록
- `/help`는 버튼 메뉴만 표시
- 버튼 메뉴:
  - `세션`
  - `모델`
  - `Fast`
  - `Thinking`
  - `권한`
  - `최근 출력`
  - `현재 상태`
  - `취소`
- `Fast`는 실제 Codex `fast_mode` 토글이며, 터미널 `/fast`와 같은 `2X plan usage` 모드
- `Thinking`은 `low/medium/high/xhigh`만 담당하고 `Fast`와 분리됨
- 세션 메뉴에서:
  - `디렉토리 설정`
  - 최근 세션 선택
  - `새 세션 만들기`
  - `현재 세션 삭제`
- 세션 목록은 현재 디렉토리와 동일한 `cwd` 세션만 표시
- 세션 디렉토리 브라우저에서:
  - 폴더 버튼으로 안쪽으로 이동
  - `../` 버튼으로 상위 폴더 이동
  - 현재 폴더 기준 최근 세션 미리보기 확인
  - `이 폴더를 현재 디렉토리로 설정`
- 세션 목록은 최신 활동 순으로 정렬
- 세션 목록은 각 세션의 전체 `cwd`, 생성 시각, 수정 시각을 표시
- 새 세션 만들기는 `~/`부터 폴더 브라우저를 열고, 현재 폴더의 바로 아래 하위 폴더만 보여줌
- 세션 브라우저에서:
  - 폴더 버튼으로 안쪽으로 이동
  - `../` 버튼으로 상위 폴더 이동
  - `현재 폴더로 세션 시작`
  - `새 폴더 만들기`를 누른 뒤 다음 일반 메시지로 폴더 이름을 보내 새 폴더 생성 후 세션 시작
- 현재 세션 삭제는 active 세션만 archive 처리
- `최근 출력`은 현재 active 세션을 우선 기준으로 읽음
- `현재 상태`는 아래 값을 보여줌
  - active session id/name/cwd
  - session scope cwd
  - fast mode
  - permission
  - model
  - reasoning
  - session count
  - `contextWindow`
  - `lastTurnTokens`
  - `sessionTotalTokens`
  - `remainingContextApprox`

## 현재 제약

- `remainingContextApprox`는 정확한 공식 잔여 컨텍스트가 아니라 rollout의 최신 `token_count` 이벤트 기준 근사치입니다.
- `Codex` 자체는 OpenAI 외부 서비스 의존이 남아 있습니다.
- Telegram은 한 봇 토큰당 polling 주체가 하나여야 하므로, 같은 토큰으로 여러 poller를 동시에 띄우면 안 됩니다.
- 세션 삭제는 hard delete가 아니라 Codex state DB의 `archived=1` 처리입니다.

## 현재 파일 구조

- [README.md](../README.md)
- [AGENTS.md](../AGENTS.md)
- [telegram_bot.py](../telegram_codex_relay/telegram_bot.py)
- [codex-bridge](../telegram_codex_relay/bin/codex-bridge)
- [config.example.json](../telegram_codex_relay/config.example.json)
- [test_simulation.py](../telegram_codex_relay/tests/test_simulation.py)
- [install_user_service.sh](../scripts/install_user_service.sh)
- [uninstall_user_service.sh](../scripts/uninstall_user_service.sh)
- [get_chat_id.py](../scripts/get_chat_id.py)

## 런타임 파일

아래는 커밋하지 않습니다.

- `telegram_codex_relay/config.json`
- `telegram_codex_relay/state/codex_bridge_state.json`
- `telegram_codex_relay/state/runtime_state.json`

## 현재 검증 기준

- 단위/시뮬레이션 테스트 통과
- `python3 -m py_compile` 통과
- 실제 `Codex bridge`로 새 세션 생성 확인
- 실제 `Codex bridge`로 `resume -> read` 즉시 확인
- 실제 `Codex bridge`로 최소 프롬프트 실행 확인
- 실제 `Codex bridge`로 현재 세션 archive 삭제 확인
- `scripts/get_chat_id.py` 실행 확인
- `systemd --user` 서비스 설치 스크립트로 실제 서비스 기동 확인

## 최근 검증 메모

2026-03-20 로컬 검증 기준:

- `scripts/run_tests.sh` 25개 통과
- 새 레포 경로의 `codex-bridge`로 `new-session -> prompt -> delete-session` 실검증 완료
- 새 레포 경로의 `codex-bridge`로 `resume -> read -> restore` 실검증 완료
- 새 레포 경로의 `codex-bridge`로 `fast off -> status -> fast on -> status` 실검증 완료
- 새 레포 경로의 `codex-bridge`로 서로 다른 작업 디렉토리에 대해 `set-workdir -> sessions-json` 실검증 완료
- 실제 `Codex CLI` 도움말 기준 `resume --all`이 cwd filtering 해제 옵션임을 확인했고, 브리지는 기본값을 동일 cwd 필터로 맞춤
- Telegram Bot API `getMyCommands` 기준 `/help`만 등록된 것 확인
- `codex-telegram-bridge.service` 재시작 후 `active` 확인
- `codex-telegram-bridge.service`가 `/data2/iena/codex-telegram-bridge/.venv/bin/python`으로 실행되는 것 확인
- 현재 운영 서비스는 conda base가 아니라 레포 내부 `.venv`만 사용
- 설치 스크립트와 서비스는 conda base에 패키지를 설치하지 않음
- 현재 서버에서 `systemctl --user is-enabled codex-telegram-bridge.service` = `enabled` 확인
- 현재 서버에서 `loginctl show-user ubuntu -p Linger` = `Linger=yes` 확인
- 기존 사용자 서비스 `telegram-codex-relay.service`는 중지했고, 현재는 `codex-telegram-bridge.service`가 새 레포 경로를 사용 중

## 비용과 외부 의존성

- `Telegram Bot API`: 기본적으로 무료
- `Codex`: 계속 외부 OpenAI 의존, 플랜/한도 영향 있음
- `OpenClaw`: 현재 구조에서 제거됨
- 외부 API를 완전히 없애려면 `Codex` 대신 로컬 모델 기반으로 재설계해야 함
