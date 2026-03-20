# Docs Index

## 작업 시작 게이트

- 비사소한 작업 단위는 항상 [../AGENTS.md](../AGENTS.md)에서 시작합니다.
- 새 작업 시작, 단계 전환, 결과 정리, 커밋/푸시 전, 후속 실행 시작 전에는 `AGENTS.md -> docs/README.md -> docs/status.md` 순서로 다시 확인합니다.
- 문서 비교, 대규모 리팩토링, 컨텍스트를 많이 쓰는 작업은 먼저 짧은 계획 문서를 만들거나 기존 계획 문서를 갱신합니다.

## 먼저 읽기

1. [docs/status.md](status.md)
2. [docs/setup/telegram.md](setup/telegram.md)
3. [docs/setup/install.md](setup/install.md)

## 문서 역할

- [../AGENTS.md](../AGENTS.md)
  에이전트 작업 규칙의 단일 기준 문서
- [docs/status.md](status.md)
  현재 구조, 현재 기능, 현재 제약, 현재 검증 상태를 기록하는 기준 문서
- [docs/architecture.md](architecture.md)
  시스템 구조와 각 파일의 책임
- [docs/security.md](security.md)
  비밀값 관리, 공개 레포 운영 주의사항
- [docs/setup/telegram.md](setup/telegram.md)
  Telegram 앱과 `BotFather`로 봇을 만드는 상세 절차
- [docs/setup/install.md](setup/install.md)
  클론 후 설정, 테스트, 서비스 설치, 최초 실행 절차
- [docs/operations/service.md](operations/service.md)
  `systemd --user` 운영과 로그 확인 방법

## 문서 규칙

- 현재 사실은 `docs/status.md`를 우선합니다.
- 에이전트 규칙 본문은 루트 `AGENTS.md` 하나에만 둡니다.
- 상세 설정법은 setup 문서에 둡니다.
- 운영 명령은 operations 문서에 둡니다.
- 동일 내용을 여러 문서에 중복으로 길게 복사하지 않습니다.
- 상위 문서는 얇게 유지하고 현재 기준만 남깁니다.
- 임시 조사 메모나 긴 작업 계획은 목적이 분명한 별도 문서로 분리합니다.
