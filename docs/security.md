# Security

## 커밋 금지 항목

- 실제 `bot_token`
- 실제 `allowed_chat_id`
- `config.json`
- `telegram_codex_relay/state/` 아래의 모든 런타임 파일
- 개인 대화 로그 전문

## 공개 레포 원칙

- 예시는 항상 placeholder만 사용
- 실제 운영 값은 사용자가 각자 `config.json`에 넣음
- 실제 서비스 파일은 설치 스크립트가 현재 클론 경로 기준으로 생성

## 접근 제한

- 봇은 `allowed_chat_id` 하나만 허용하도록 설계돼 있습니다.
- 다른 채팅에서 보낸 메시지는 무시합니다.

## 삭제 의미

- `현재 세션 삭제`는 세션 레코드를 archive 처리합니다.
- Codex 내부 데이터를 완전히 물리 삭제하는 기능은 아닙니다.
