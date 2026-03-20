# Current Status

## 프로젝트 목표

이 레포는 `Telegram DM`에서 `Codex CLI`를 직접 제어하는 브리지를 제공합니다.  
현재 기준 아키텍처는 `Telegram Bot API -> telegram_bot.py -> codex-bridge -> codex exec`입니다.

## 현재 구현 상태

- `OpenClaw` 의존 없음
- 로컬 LLM 의존 없음
- 평문 메시지는 active `Codex` 세션으로 전달
- `/help`는 버튼 메뉴만 표시
- 버튼 메뉴:
  - `세션`
  - `모델`
  - `Thinking`
  - `권한`
  - `최근 출력`
  - `현재 상태`
  - `취소`
- `/resume`은 세션 메뉴를 엶
- 세션 메뉴에서:
  - 최근 세션 선택
  - `새 세션 만들기`
  - `현재 세션 삭제`
- 새 세션 만들기는 `~/`부터 폴더 브라우저를 열고, 폴더 버튼으로 내려가서 `이 폴더로 세션 생성`으로 완료
- 현재 세션 삭제는 active 세션만 archive 처리
- `/status`는 아래 값을 보여줌
  - active session id/name/cwd
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
- 실제 `Codex bridge`로 최소 프롬프트 실행 확인
- 실제 `Codex bridge`로 현재 세션 archive 삭제 확인
- `scripts/get_chat_id.py` 실행 확인
- `systemd --user` 서비스 설치 스크립트로 실제 서비스 기동 확인

## 최근 검증 메모

2026-03-20 로컬 검증 기준:

- `scripts/run_tests.sh` 통과
- 새 레포 경로의 `codex-bridge`로 `new-session -> prompt -> delete-session` 실검증 완료
- 기존 사용자 서비스 `telegram-codex-relay.service`는 중지했고, 현재는 `codex-telegram-bridge.service`가 새 레포 경로를 사용 중

## 비용과 외부 의존성

- `Telegram Bot API`: 기본적으로 무료
- `Codex`: 계속 외부 OpenAI 의존, 플랜/한도 영향 있음
- `OpenClaw`: 현재 구조에서 제거됨
- 외부 API를 완전히 없애려면 `Codex` 대신 로컬 모델 기반으로 재설계해야 함
