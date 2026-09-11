# 발행 대상 선택 로직(중복 방지·발행창·밀린 항목 따라잡기)을 검증하는 자체 점검 스크립트
import datetime as dt
import json

from daily import CATCHUP_DAYS, KST, WINDOW_MIN, pick_post

PLAN = json.loads(open("content_plan.json", encoding="utf-8").read())
BY_DAY = {p["day"]: p for p in PLAN["posts"]}


def at(iso):
    return dt.datetime.fromisoformat(iso).replace(tzinfo=KST)


def st(*days):
    return {"published": {str(d): {"at": "", "media_id": "x"} for d in days}}


def day_of(result):
    return result["day"] if result else None


def run():
    # 계획 전제 확인. 날짜가 바뀌면 아래 케이스도 함께 고쳐야 한다
    assert BY_DAY[1]["publish_at"].startswith("2026-09-08T08:00")
    assert BY_DAY[2]["publish_at"].startswith("2026-09-09T21:00")
    assert BY_DAY[3]["publish_at"].startswith("2026-09-10T08:00")

    # --- 오늘 항목 ---
    # 발행 시각 정각
    assert day_of(pick_post(PLAN, st(1), now=at("2026-09-09T21:00:00"))) == 2
    # 발행창(45분) 경계
    edge = at("2026-09-09T21:00:00") - dt.timedelta(minutes=WINDOW_MIN)
    assert day_of(pick_post(PLAN, st(1), now=edge)) == 2
    # 발행 시각이 지난 뒤 — 실패했을 수 있으므로 같은 날 재시도
    assert day_of(pick_post(PLAN, st(1), now=at("2026-09-09T23:30:00"))) == 2
    # 이미 게시됨 — 중복 방지
    assert pick_post(PLAN, st(1, 2), now=at("2026-09-09T21:30:00")) is None
    # 오늘 것이 밀린 것보다 우선
    assert day_of(pick_post(PLAN, st(1), now=at("2026-09-10T08:00:00"))) == 3

    # --- 밀린 항목 따라잡기 (day2 누락 사고 재현) ---
    # day2가 인코딩 실패로 빠진 뒤 다음 날. 예전 로직은 영영 건너뛰었다
    assert day_of(pick_post(PLAN, st(1, 3), now=at("2026-09-10T21:00:00"))) == 2
    # 오늘 것이 아직 발행창 전이고 밀린 것도 없으면 아무것도 하지 않는다
    assert pick_post(PLAN, st(1), now=at("2026-09-09T07:30:00")) is None
    # 오늘 것을 이미 올렸다면 밀린 것 중 가장 오래된 것부터 따라잡는다
    assert day_of(pick_post(PLAN, st(1, 4), now=at("2026-09-11T21:30:00"))) == 2

    # --- 따라잡기 한도 ---
    # CATCHUP_DAYS를 넘긴 항목은 건너뛴다
    far = at("2026-09-09T21:00:00") + dt.timedelta(days=CATCHUP_DAYS + 2)
    assert day_of(pick_post(PLAN, st(1), now=far)) != 2

    # --- 날짜 종속 콘텐츠 ---
    # day18은 추석 당일(09-25) 인사. 지난 뒤에는 올리지 않는다
    assert BY_DAY[18].get("date_sensitive") is True
    done = st(*[d for d in range(1, 31) if d != 18])
    assert pick_post(PLAN, done, now=at("2026-09-26T10:30:00")) is None

    # --- 계획 범위 밖 ---
    # 전부 게시된 뒤에는 아무것도 하지 않는다
    assert pick_post(PLAN, st(*range(1, 31)), now=at("2026-09-20T10:30:00")) is None
    # 계획이 끝나고 한참 뒤
    assert pick_post(PLAN, st(1), now=at("2026-11-01T21:00:00")) is None

    # --- force_day는 상태와 무관하게 그 항목을 준다 ---
    assert day_of(pick_post(PLAN, st(1, 2, 3), force_day=2)) == 2

    print("pick_post 13개 케이스 통과")


if __name__ == "__main__":
    run()
