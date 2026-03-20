# Reference Policy Alignment Plan

## 목적

`tmp/레퍼런스로 삼을 기준점 운영 방침` 아래의 모든 문서를 빠짐없이 읽고,  
그 안의 운영 방침을 현재 레포 문서 운영 원칙과 대조해 필요한 override를 반영한다.

이 문서는 이번 작업 동안 컨텍스트가 압축되어도 읽기 순서와 남은 단계를 잃지 않기 위한 기준 문서다.

## 기준 폴더 전수 목록

### 텍스트 문서

1. `tmp/레퍼런스로 삼을 기준점 운영 방침/README.md`
2. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/AGENT.md`
3. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/README.md`
4. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/agent_watchdog_plan.md`
5. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/archive/README.md`
6. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/archive/decisions_2026_03_full_before_refactor.md`
7. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/archive/logbook_2026_03_full_before_refactor.md`
8. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/gifs/jetson_demos/README.md`
9. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/README.md`
10. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/README.md`
11. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/videos/jetson_demos/README.md`
12. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/decisions.md`
13. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/envs/jetson/JETSON_MAXN_SUPER_PERSISTENT_KO.md`
14. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/jetson_transition_plan.md`
15. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/logbook.md`
16. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/project_overview.md`
17. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/status.md`
18. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/개발방침.md`

### 미디어 참조 파일

1. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/gifs/jetson_demos/vad_gui_demo_jetson.gif`
2. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/gifs/jetson_demos/voice_pipeline_demo_01_giraffe_question.gif`
3. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/gifs/jetson_demos/voice_pipeline_demo_02_lunch_recommendation.gif`
4. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/gifs/jetson_demos/wake_word_gui_demo_jetson.gif`
5. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/vad_demo_idle_terminal.png`
6. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/vad_demo_speech_terminal.png`
7. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/vad_gui_idle.png`
8. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/vad_gui_speaking.png`
9. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/wake_word_gui_detected.png`
10. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/jetson_demos/wake_word_gui_idle.png`
11. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/stt_dataset_recorder_gui.png`
12. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/stt_korean_eval50_dataset_files.png`
13. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/voice_pipeline_gui_01_idle_waiting.png`
14. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/voice_pipeline_gui_02_wake_detected_listening.png`
15. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/voice_pipeline_gui_03_stt_processing.png`
16. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/screenshots/stt/voice_pipeline_gui_04_result_displayed.png`
17. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/videos/jetson_demos/vad_gui_demo_jetson.mp4`
18. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/videos/jetson_demos/voice_pipeline_demo_01_giraffe_question.mp4`
19. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/videos/jetson_demos/voice_pipeline_demo_02_lunch_recommendation.mp4`
20. `tmp/레퍼런스로 삼을 기준점 운영 방침/docs/assets/videos/jetson_demos/wake_word_gui_demo_jetson.mp4`

## 현재 레포 문서 전수 목록

1. `AGENTS.md`
2. `README.md`
3. `docs/README.md`
4. `docs/architecture.md`
5. `docs/operations/service.md`
6. `docs/security.md`
7. `docs/setup/install.md`
8. `docs/setup/telegram.md`
9. `docs/status.md`
10. `docs/reference_policy_alignment_plan.md`

## 작업 순서

1. 기준 폴더 문서 전체를 하나도 빼놓지 않고 읽는다.
2. 미디어 참조 파일은 README와 파일 목록 기준으로 존재와 역할을 확인한다.
3. 기준 문서에서 추출한 운영 원칙을 정리한다.
4. 현재 레포 문서를 전부 다시 읽고 적용 계획을 세운다.
5. 문서별로 override가 필요한 항목을 반영한다.
6. 기준 폴더를 삭제한다.
7. 현재 레포 문서를 전부 다시 읽고 중복/누락/구조 문제를 검토한다.
8. 필요한 문서 리팩토링과 상태 갱신을 수행한다.
9. 테스트 또는 검증 명령을 다시 돌린다.

## 기준점에서 채택한 override

- 시작 게이트 강화
  현재 레포에서도 비사소한 작업 단위마다 `AGENTS.md -> docs/README.md -> docs/status.md`를 다시 확인한다.
- 큰 작업 전 계획 문서 선행
  문서 비교, 대규모 리팩토링, 컨텍스트 사용량이 큰 작업은 먼저 짧은 계획 문서를 만들고 갱신한다.
- 현재 상태는 실제 근거로 확인
  서비스/런타임/활성 세션 상태는 기억이 아니라 실제 명령 결과와 상태 조회로 확인한다.
- 상위 문서는 얇게 유지
  현재 레포는 문서 수가 적으므로 reference처럼 `decisions/logbook`를 추가로 복제하지 않고, 기존 문서 역할 분리를 유지한 채 필요한 규칙만 흡수한다.

## 기준점에서 보류한 항목

- watchdog 전용 문서 체계
  reference 프로젝트는 장시간 detached pipeline이 많아 별도 watchdog 정책이 핵심이었지만, 현재 레포의 주 운영 범위는 Telegram bot/service와 bridge라서 동일 구조를 그대로 복제하지 않는다.
- 대규모 archive 체계
  현재 레포 문서 규모에서는 archive 문서군을 새로 늘리기보다 `docs/status.md`와 역할별 문서를 얇게 유지하는 편이 맞다.

## 진행 상태

- [x] 기준 폴더와 현재 레포 문서 목록 조사
- [x] 기준 폴더 텍스트 문서 전체 읽기
- [x] 기준 폴더 미디어 참조 확인
- [x] 현재 레포 문서 전체 읽기와 override 계획 수립
- [x] 문서 운영 방침 override 적용
- [x] 기준 폴더 삭제
- [x] 현재 레포 문서 재독과 중복/누락 검토
- [x] 문서 리팩토링과 상태 갱신
- [x] 검증 재실행

## 현재 정리 결과

- 시작 게이트, 계획 문서 선행, 실제 상태 확인 원칙은 현재 레포 운영 방침에 반영했다.
- 기준점 폴더는 삭제 완료했고, 현재 레포에는 남아 있지 않다.
- 문서 수가 작은 현재 레포 특성상 `decisions/logbook/archive` 체계는 추가하지 않고 기존 얇은 문서 구조를 유지한다.

## 검증 결과

- `scripts/run_tests.sh` 재실행 기준 `33`개 테스트 통과
- `python3 -m py_compile telegram_codex_relay/telegram_bot.py telegram_codex_relay/bin/codex-bridge telegram_codex_relay/tests/test_simulation.py` 통과
