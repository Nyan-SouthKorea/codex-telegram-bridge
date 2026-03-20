# Architecture

## 개요

현재 구조는 아래와 같습니다.

1. 사용자가 Telegram DM에서 메시지를 보냅니다.
2. [telegram_bot.py](../telegram_codex_relay/telegram_bot.py)가 polling으로 업데이트를 받습니다.
3. 평문이면 active `Codex` 세션으로 전달합니다.
4. 슬래시 명령이나 버튼 콜백이면 로컬 규칙으로 처리합니다.
5. 실제 Codex 관련 상태 변경과 세션 조작은 [codex-bridge](../telegram_codex_relay/bin/codex-bridge)가 담당합니다.
6. `codex-bridge`는 `codex exec`와 Codex state DB를 사용합니다.

## 파일 책임

- [telegram_bot.py](../telegram_codex_relay/telegram_bot.py)
  Telegram polling, 버튼 렌더링, 현재 실행 취소, prompt 비동기 처리
- [codex-bridge](../telegram_codex_relay/bin/codex-bridge)
  세션 목록, 세션 전환, 새 세션 생성, 세션 이름 변경, 현재 세션 종료, 세션 archive 삭제, 모델/권한/thinking 저장, 상태 조회
- `telegram_codex_relay/state/`
  브리지 상태와 런타임 상태 저장
- `~/.codex`
  Codex CLI 자체 상태와 세션 DB

## 설계 원칙

- Telegram 레이어는 얇게 유지
- `Codex TUI`를 키 입력 자동화로 조작하지 않음
- 상태 전환은 결정형 브리지 명령으로 수행
- 텔레그램에서 필요한 UX는 버튼으로 구현

## 세션 동작

- `permission=full`
  persistent resume 방식
- `permission=read` 또는 `deny`
  isolated one-turn exec 방식
- `현재 세션 종료`
  active 세션 포인터만 해제하고 기록은 유지하며, 다음 평문은 새 active 세션으로 시작
- `이름 변경`
  Telegram에서 받은 새 이름을 Codex state DB와 `session_index.jsonl`에 함께 기록해 세션 표시명을 맞춤

## 컨텍스트 잔량

`remainingContextApprox`는 rollout 로그의 `token_count` 이벤트를 읽어 계산한 근사치입니다.  
Codex가 공식적으로 노출하는 절대 정확한 남은 토큰 카운터는 아닙니다.
