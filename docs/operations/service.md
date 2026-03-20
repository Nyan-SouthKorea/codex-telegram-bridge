# Service Operations

## 설치

```bash
scripts/install_user_service.sh
```

생성 대상:

- `~/.config/systemd/user/codex-telegram-bridge.service`

## 상태 확인

```bash
systemctl --user status codex-telegram-bridge.service
```

## 재시작

```bash
systemctl --user restart codex-telegram-bridge.service
```

## 중지

```bash
systemctl --user stop codex-telegram-bridge.service
```

## 로그 확인

```bash
journalctl --user -u codex-telegram-bridge.service -f
```

## 제거

```bash
scripts/uninstall_user_service.sh
```

## 서비스 미사용 운영

서비스 대신 foreground로도 실행할 수 있습니다.

```bash
python3 telegram_codex_relay/telegram_bot.py
```
