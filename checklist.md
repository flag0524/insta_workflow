# 체크리스트

표기 — `[x]` 실행까지 검증 완료 / `[~]` 코드는 작성했으나 실행 검증 못 함 (API 키 필요) / `[ ]` 미착수

## 0. 계획 (완료)

- [x] 니치·타깃·스택 확정
- [x] `plan.md` — 자동 실행 흐름, 릴스 설계 규칙, 제약 3가지
- [x] `content_plan.json` — 30일 릴스 데이터
- [x] `validate.py` — 계획 데이터 규칙 검사 → 통과 (30건 / 747초 / 에러 0)
- [x] 트렌딩 오디오 하이브리드 여부 결정 → **미도입, 전량 자동**

## 1. 계정·API 준비 (사용자 수동 — 여기가 남은 병목)

- [ ] 인스타 계정을 프로페셔널로 전환
- [ ] 페이스북 페이지 생성 후 인스타 계정과 연결
- [ ] developers.facebook.com에서 Meta 앱 생성
- [ ] 권한 요청 — `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list`
- [ ] 장기 액세스 토큰 발급 (60일)
- [ ] IG User ID 확인
- [ ] Cloudinary 무료 계정 + API 키
- [ ] 텔레그램 봇 토큰 + chat_id (선택)
- [ ] `.env.example`을 `.env`로 복사해 값 입력 → verify: `python daily.py --check-env`가 "통과" 출력

## 2. 로컬 환경 (완료)

- [x] Python 3.11.9 확인
- [x] `pip install playwright cloudinary` (requests·dotenv는 이미 설치돼 있었음)
- [x] `playwright install chromium`
- [x] ffmpeg 8.1.2 확인 → `ffmpeg -version` 정상
- [ ] 로열티 프리 BGM 4곡을 `assets/bgm/`에 배치 — 파일명은 `calm_tech_01.mp3`, `upbeat_lofi_02.mp3`, `minimal_pulse_03.mp3`, `warm_acoustic_04.mp3`
      (없어도 무음으로 동작합니다. 다만 릴스에 무음은 불리하니 발행 전 채우는 게 좋습니다)

## 3. 렌더링 (완료)

- [x] `templates/scene.html` — layout 5종 분기 (hook/point/code/compare/cta)
- [x] 안전 영역 적용 (상단 220px, 하단 320px)
- [x] 장면 PNG 렌더 → verify: day1 6장이 1080x1920으로 생성됨
- [x] 자막 오버플로 확인 → verify: 렌더 결과를 눈으로 확인. 14자가 잘리지 않음
- [x] 레이아웃 1차 수정 → 폰트 확대, hook을 중앙 정렬로 변경 (아래 2/3가 비어 보이는 문제)

## 4. 영상 조립 (완료)

- [x] ffmpeg zoompan + xfade 필터 체인
- [x] 장면 길이에 전환 시간 보정 → 최종 길이가 `duration_sec`과 정확히 일치
- [x] BGM 믹싱 + 끝 페이드아웃 (파일 없으면 무음 폴백)
- [x] verify: day1 = 45.000초 / h264 / yuv420p / 30fps / 1080x1920 / aac
- [x] verify: day4(소수점 타임코드, 4장면) = 10.000초 정확
- [ ] verify: 실제 폰에서 재생 확인 — `out/day01/reel.mp4`를 폰으로 옮겨 확인 필요

## 5. 업로드 (코드 완료, 검증 대기)

- [~] Cloudinary 업로드 → 공개 URL 반환
- [~] Graph API 컨테이너 생성 (`media_type=REELS`)
- [~] `status_code` 폴링 (5초 간격, 최대 5분)
- [~] `media_publish` 호출
- [ ] verify: 테스트 1건이 실제 계정에 릴스로 게시됨 ← **1번 완료 후 가능**

## 6. 스케줄링·운영 (코드 완료, 검증 대기)

- [~] `state.json` 기록·중복 방지
- [~] 실패 시 텔레그램 알림
- [ ] verify: 같은 날 두 번 실행해도 1건만 게시
- [ ] verify: 토큰을 일부러 틀리게 하고 알림 수신 확인
- [ ] 작업 스케줄러 3개 등록 (07:15 / 09:45 / 20:15)
- [ ] "놓친 작업 즉시 실행" 옵션 활성화
- [ ] verify: PC 재부팅 후에도 트리거 유지

## 7. 운영 중 점검

- [ ] 1주차 종료 후 인사이트에서 재생 완료율 확인
- [ ] 팔로워 활동 시간대 확인 → 발행 슬롯 재조정
- [ ] 훅 유형별 성과 비교 (H1~H5)
- [ ] 30일 종료 후 다음 사이클 계획 갱신

## 규칙

`content_plan.json`을 수정하면 **반드시** `python validate.py`를 돌립니다.
