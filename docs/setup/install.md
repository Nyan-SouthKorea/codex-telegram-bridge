# Install And First Run

## 전제 조건

- Linux 환경
- `python3`
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

## 3. 브리지 상태 확인

직접 브리지 상태를 볼 수 있습니다.

```bash
python3 telegram_codex_relay/bin/codex-bridge status
```

## 4. 수동 실행

먼저 foreground에서 확인하려면:

```bash
python3 telegram_codex_relay/telegram_bot.py
```

이 상태에서 Telegram DM에서 `/help`를 보내면 됩니다.

## 5. 사용자 서비스 설치

`systemd --user`를 쓴다면 아래 스크립트로 설치합니다.

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
3. 필요하면 `디렉토리 설정`
4. 폴더를 눌러 이동하거나 `../`로 상위 폴더 이동
5. 원하는 폴더에서 `이 폴더를 현재 디렉토리로 설정`
6. 세션 메뉴에서 보이는 세션을 선택하거나, 필요하면 `새 세션 만들기`
7. 새 세션을 만들 때는 폴더를 눌러 이동하거나 `../`로 상위 폴더 이동
8. `현재 폴더로 세션 시작` 또는 `새 폴더 만들기`
9. `새 폴더 만들기`를 눌렀다면 다음 일반 메시지로 폴더 이름 전송
10. `/help`
11. `모델`
12. 모델 선택
13. 자동으로 뜬 `Thinking` 메뉴에서 선택
14. `/help`
15. `권한`
16. `Full` 선택
17. 평문으로 작업 지시 전송

## 7. smoke test 예시

Telegram에서 순서대로:

1. `/help`
2. `Low (Fast)`
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
13. `Low (Fast)`
14. `권한`
15. `Full`
16. 평문으로 `pwd만 한 줄로 답해`
17. `최근 출력`

이 흐름이 전부 통과하면 기본 기능은 정상입니다.
