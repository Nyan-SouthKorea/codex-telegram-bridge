# Telegram Bot Setup

## 준비물

- Telegram 앱 설치 및 로그인
- 이 레포 클론 완료
- `Codex CLI` 설치 및 로그인 완료

## 1. BotFather 열기

가장 쉬운 방법은 Telegram 앱에서 `@BotFather`를 검색하는 것입니다.

순서:

1. Telegram 앱을 엽니다.
2. 상단 검색창에 `BotFather` 또는 `@BotFather`를 입력합니다.
3. `BotFather` 채팅방을 엽니다.
4. `Start`를 누르거나 `/start`를 보냅니다.

## 2. 새 봇 만들기

1. BotFather 채팅에 `/newbot` 을 보냅니다.
2. 표시 이름을 입력합니다.
   예시: `My Codex Bridge`
3. 봇 username을 입력합니다.
   예시: `my_codex_bridge_bot`

username 규칙:

- 반드시 `bot`으로 끝나야 함
- 영문, 숫자, `_`만 가능
- 공백 불가
- 이미 사용 중이면 다른 이름 사용

## 3. 토큰 보관

BotFather는 생성 후 긴 문자열 하나를 줍니다. 이 값이 `bot token`입니다.

예시 형식:

```text
123456789:AA...
```

이 토큰은 비밀번호처럼 취급합니다.

- 공개 레포에 올리면 안 됨
- 스크린샷 공유 금지
- 문서 예시에는 placeholder만 사용

## 4. 봇에게 먼저 DM 보내기

1. Telegram 검색에서 방금 만든 `@your_bot_username`을 찾습니다.
2. 채팅방을 엽니다.
3. `Start`를 누르거나 `hi`를 보냅니다.

이 단계가 필요한 이유:

- `getUpdates`로 실제 `chat_id`를 찾으려면 봇에게 한 번은 메시지가 들어와야 합니다.

## 5. chat_id 확인

레포 루트에서 아래 스크립트를 실행합니다.

```bash
python3 scripts/get_chat_id.py
```

`config.json`이 아직 없다면 토큰을 직접 넘길 수도 있습니다.

```bash
python3 scripts/get_chat_id.py 123456789:AA...
```

이 스크립트는 최근 업데이트에 포함된 채팅들을 보여줍니다.  
개인 DM 기준 `chat_type=private`인 항목의 `chat_id`를 `allowed_chat_id`로 사용하면 됩니다.

## 6. config.json 만들기

예시 파일을 복사합니다.

```bash
cp telegram_codex_relay/config.example.json telegram_codex_relay/config.json
```

그리고 값을 채웁니다.

```json
{
  "bot_token": "123456789:AA...",
  "allowed_chat_id": "123456789",
  "workdir": "/absolute/path/to/your/main-project",
  "poll_timeout_seconds": 30
}
```

설명:

- `bot_token`: BotFather가 준 토큰
- `allowed_chat_id`: 위에서 찾은 개인 DM chat id
- `workdir`: Codex가 기본으로 작업할 메인 레포 또는 작업 폴더
- `poll_timeout_seconds`: 기본값 30이면 충분

## 7. 최소 동작 확인

서비스를 띄우기 전에도 직접 실행할 수 있습니다.

```bash
python3 telegram_codex_relay/telegram_bot.py
```

정상이라면 Telegram DM에서 `/help`에 반응해야 합니다.
