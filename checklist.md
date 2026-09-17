# 체크리스트

표기 — `[x]` 실행까지 검증 완료 / `[~]` 코드는 작성했으나 실행 검증 못 함 (API 키 필요) / `[ ]` 미착수

## 0. 계획 (완료)

- [x] 니치·타깃·스택 확정
- [x] `plan.md` — 자동 실행 흐름, 릴스 설계 규칙, 제약 3가지
- [x] `content_plan.json` — 30일 릴스 데이터
- [x] `validate.py` → 통과 (30건 / 747초 / 에러 0)
- [x] 트렌딩 오디오 하이브리드 여부 결정 → **미도입, 전량 자동**

## 1. 계정·API 준비

- [x] 인스타 계정 프로페셔널 전환 — `@flag_21` / MEDIA_CREATOR / 게시물 12개
- [x] API 계열 확정 — **Instagram Login** (`graph.instagram.com`). 페이스북 페이지 연결 불필요
- [x] 액세스 토큰 확보 → verify: `--check-env`의 토큰 검증 OK
- [x] 게시 권한 확인 → `content_publishing_limit` 조회 성공 (0/100 사용)
- [x] IG User ID 확인 → `28152757404390183` (사용자명이 아니라 숫자 ID)
- [ ] **Cloudinary 무료 계정 + API 키 3개** ← **남은 유일한 병목**
- [ ] 텔레그램 봇 토큰 + chat_id (선택이지만 권장 — 없으면 실패를 `daily.log`로만 알 수 있음)
- [ ] verify: `python daily.py --check-env`가 "통과" 출력

## 2. 로컬 환경 (완료)

- [x] Python 3.11.9 확인
- [x] **시스템 python**에 playwright·cloudinary 설치
      경로: `C:\Users\flag2\AppData\Local\Programs\Python\Python311\python.exe`
      (PATH의 `python`은 에이전트 venv를 가리킵니다. 스케줄러는 시스템 python을 씁니다)
- [x] `playwright install chromium`
- [x] ffmpeg 8.1.2 확인
- [x] BGM 4곡 — `make_bgm.py`로 ffmpeg 사인파 합성 생성 (실측 mean -28.8dB)
- [ ] BGM을 실제 음원으로 교체 (선택) — 합성음은 최소한의 대체재입니다.
      유튜브 오디오 라이브러리나 Pixabay Music에서 받아 같은 파일명으로 덮어쓰면 됩니다

## 3. 렌더링 (완료)

- [x] `templates/scene.html` — layout 5종 (hook/point/code/compare/cta)
- [x] 안전 영역 적용 (상단 220px, 하단 320px)
- [x] 장면 PNG 렌더 → 1080x1920 확인
- [x] 자막 오버플로 확인 → 눈으로 확인, 14자 잘리지 않음
- [x] 레이아웃 1차 수정 → 폰트 확대, hook을 중앙 정렬로 변경

## 4. 영상 조립 (완료)

- [x] ffmpeg zoompan + xfade 필터 체인
- [x] 전환으로 깎이는 시간 보정 → 최종 길이가 `duration_sec`과 정확히 일치
- [x] BGM 믹싱 + 끝 페이드아웃 (파일 없으면 무음 폴백)
- [x] **30일 전량 dry-run → 30/30 성공, 실패 0건**
- [x] 스펙 확인: h264 / yuv420p / 30fps / 1080x1920 / aac
- [ ] verify: 실제 폰에서 재생 확인 — `out/day01/reel.mp4`를 옮겨 확인 필요

## 5. 업로드 (완료 — 실전 게시 성공)

- [x] Cloudinary 업로드 → 공개 URL 반환
- [x] Graph API 컨테이너 생성 (`media_type=REELS`)
- [x] `status_code` 폴링 (실측 인코딩 72초)
- [x] `media_publish` 호출
- [x] **verify: day1이 실제 계정에 REELS로 게시됨**
      https://www.instagram.com/reel/DdBRh_mk8ey/ (2026-09-08 17:38)

## 6. 스케줄링·운영

- [x] `state.json` 기록·중복 방지 → `test_pick_post.py` 13개 케이스 통과
- [x] 발행창 45분 경계, 발행 시각 경과 후 재시도 검증
- [x] 밀린 게시물 따라잡기(catch-up) 로직 — 자정 넘어가면 실패분이 영구 누락되던 버그 수정
- [x] 동시 실행 방지 파일 락(`daily.lock`) — 밀린 트리거 2개가 같은 순간 겹쳐 파일 레이스가 났던 사고 수정
- [x] `daily.log` 파일 로깅 추가 (로컬 스케줄러 실행 시 표준출력이 사라지므로)

### ~~Windows 작업 스케줄러~~ (2026-09-17부로 GitHub Actions로 대체, 아래 6-1 참고)

- [x] ~~작업 스케줄러 3개 등록~~ → **비활성화함** (`Disable-ScheduledTask`, 삭제 아님)
- [x] ~~"놓친 작업 즉시 실행" 활성화~~
- [x] ~~verify: 스케줄러 수동 실행~~ — 로컬 PC 전원 의존성 자체가 레이스 사고의 원인이라 폐기

## 6-1. GitHub Actions 이전 (신규)

- [x] `.github/workflows/daily-post.yml` 작성 — cron 3개(UTC 환산) + `workflow_dispatch` + `concurrency` 직렬화
- [x] `requirements.txt` 작성
- [x] `state.json`을 `.gitignore`에서 제외하고 git 추적 대상으로 전환, 현재 이력 커밋
- [x] 워크플로우 마지막 단계에 게시 이력 자동 커밋·푸시 추가
- [x] YAML 문법 파싱 검증
- [x] 로컬 스케줄러 비활성화
- [ ] **GitHub 리포지토리에 시크릿 7개 등록** ← 사용자가 직접 (Settings → Secrets and variables → Actions)
      `IG_USER_ID`, `IG_ACCESS_TOKEN`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `TELEGRAM_TOKEN`(선택), `TELEGRAM_CHAT_ID`(선택)
- [ ] verify: Actions 탭에서 `workflow_dispatch`로 수동 1회 실행 → 성공 확인
- [ ] verify: 실행 후 `state.json`이 자동 커밋되는지 확인
- [ ] verify: 예약된 cron 트리거가 실제 시각(±지연)에 실행되는지 하루 지켜보기
- [~] 실패 시 텔레그램 알림 (토큰 등록 전이라 미검증)

## 7. 운영 중 점검

- [ ] 1주차 종료 후 인사이트에서 재생 완료율 확인
- [ ] 팔로워 활동 시간대 확인 → 발행 슬롯 재조정
- [ ] 훅 유형별 성과 비교 (H1~H5)
- [ ] 30일 종료 후 다음 사이클 계획 갱신

## 규칙

- `content_plan.json`을 수정하면 **반드시** `python validate.py`
- `daily.py`를 수정하면 **반드시** `python test_pick_post.py`
