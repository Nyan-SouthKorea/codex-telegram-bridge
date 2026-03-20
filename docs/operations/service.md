# Service Operations

## 설치

```bash
scripts/install_user_service.sh
```

생성 대상:

- `~/.config/systemd/user/codex-telegram-bridge.service`
- 레포 내부 런타임: `.venv/bin/python`
- conda base는 서비스 런타임으로 사용하지 않음
- 오래된 `telegram-codex-relay.service`는 현재 운영 대상이 아니며 제거하는 것을 기준으로 함

## 부팅 후 자동 시작

현재 권장 운영 방식은 `systemd --user + linger` 입니다.

- 서비스: `codex-telegram-bridge.service`
- enable 상태 확인:

```bash
systemctl --user is-enabled codex-telegram-bridge.service
```

- linger 상태 확인:

```bash
loginctl show-user "$USER" -p Linger
```

둘 다 `enabled` / `Linger=yes` 여야 서버 재부팅 후 로그인 없이 자동으로 다시 시작됩니다.

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
.venv/bin/python telegram_codex_relay/telegram_bot.py
```
