# Install And First Run

## 전제 조건

- Linux 환경
- `/usr/bin/python3` 또는 venv 생성 가능한 시스템 Python
- `Codex CLI` 설치 및 로그인 완료
- Telegram 봇 생성 완료
- `telegram_codex_relay/config.json` 작성 완료

## 1. 레포 클론

```bash
git clone https://github.com/Nyan-SouthKorea/codex-telegram-bridge.git
cd codex-telegram-bridge
```

## 2. 테스트 실행

```bash
scripts/run_tests.sh
```

이 스크립트는 `.venv`가 있으면 그 Python을 우선 사용합니다.

## 3. 브리지 상태 확인

직접 브리지 상태를 볼 수 있습니다.

```bash
.venv/bin/python telegram_codex_relay/bin/codex-bridge status
```

## 4. 수동 실행

먼저 foreground에서 확인하려면:

```bash
.venv/bin/python telegram_codex_relay/telegram_bot.py
```

이 상태에서 Telegram DM에서 `/help`를 보내면 됩니다.

## 5. 사용자 서비스 설치

`systemd --user`를 쓴다면 아래 스크립트로 설치합니다. 이 스크립트는 `.venv`가 없으면 자동 생성하고, 서비스도 `.venv/bin/python`으로 고정합니다.

```bash
scripts/install_user_service.sh
```

설치 후 확인:

```bash
systemctl --user status codex-telegram-bridge.service
```

## 6. 첫 사용 흐름

1. `/help`
2. `세션`
3. 처음 열면 `config.json`의 `workdir`가 `/resume` 기본 기준 폴더로 자동 반영됩니다.
4. 필요하면 `디렉토리 설정`
5. 폴더를 눌러 이동하거나 `../`로 상위 폴더 이동
6. 원하는 폴더에서 `이 폴더를 현재 디렉토리로 설정`
7. 이후 세션 메뉴는 그 폴더에서 터미널로 `codex`를 실행한 뒤 `/resume` 했을 때와 같은 `동일 cwd` 세션만 보여줍니다.
8. 세션 메뉴에서 보이는 세션을 선택하거나, 필요하면 `새 세션 만들기`
9. 새 세션을 만들 때는 폴더를 눌러 이동하거나 `../`로 상위 폴더 이동
10. `현재 폴더로 세션 시작` 또는 `새 폴더 만들기`
11. `새 폴더 만들기`를 눌렀다면 다음 일반 메시지로 폴더 이름 전송
12. `/help`
13. `모델`
14. 모델 선택
15. 자동으로 뜬 `Thinking` 메뉴에서 선택
16. `/help`
17. 필요하면 `Fast`를 눌러 `fast_mode`를 켜거나 끔
18. `권한`
19. `Full` 선택
20. 평문으로 작업 지시 전송

응답 형식:

- Codex 본문 응답은 `codex> ...`
- 상태/설정 결과는 `relay> ...`
- 오류는 `error> ...`

세션 관리 메모:

- 세션 메뉴의 `현재 세션 종료`는 터미널 `codex`의 `/exit`와 같은 의미로 active 세션만 닫고 기록은 유지합니다.
- 세션 메뉴의 `현재 세션 삭제`는 active 세션을 archive 처리합니다.

## 7. smoke test 예시

Telegram에서 순서대로:

1. `/help`
2. `Fast`
3. `현재 상태`
4. `세션`
5. `디렉토리 설정`
6. 원하는 폴더에서 `이 폴더를 현재 디렉토리로 설정`
7. 세션 메뉴에서 세션 확인
8. `새 세션 만들기`
9. 원하는 폴더에서 `현재 폴더로 세션 시작`
10. `모델`
11. `GPT-5.4`
12. `Thinking`
13. `XHigh`
14. `권한`
15. `Full`
16. 평문으로 `pwd만 한 줄로 답해`
17. `최근 출력`

이 흐름이 전부 통과하면 기본 기능은 정상입니다.
