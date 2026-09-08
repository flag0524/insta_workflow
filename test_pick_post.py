# 발행 대상 선택 로직(중복 방지·발행창·재시도)을 검증하는 자체 점검 스크립트
import datetime as dt
import json

from daily import KST, WINDOW_MIN, pick_post

PLAN = json.loads(open("content_plan.json", encoding="utf-8").read())


def at(iso):
    return dt.datetime.fromisoformat(iso).replace(tzinfo=KST)


def run():
    empty = {"published": {}}

    # day1은 2026-09-09 21:00 발행 예정
    d1 = PLAN["posts"][0]
    assert d1["day"] == 1 and d1["publish_at"].startswith("2026-09-09T21:00")

    # 발행 시각 정각 — 선택돼야 한다
    assert pick_post(PLAN, empty, now=at("2026-09-09T21:00:00"))["day"] == 1

    # 발행 창(45분) 안 — 선택돼야 한다
    assert pick_post(PLAN, empty, now=at("2026-09-09T20:20:00"))["day"] == 1

    # 발행 창보다 이른 시각 — 아직 아니다
    assert pick_post(PLAN, empty, now=at("2026-09-09T19:00:00")) is None

    # 발행 시각이 지난 뒤 — 실패했을 수 있으므로 재시도로 계속 잡혀야 한다
    assert pick_post(PLAN, empty, now=at("2026-09-09T23:30:00"))["day"] == 1

    # 이미 게시된 날 — 두 번째 실행에서는 걸러져야 한다 (중복 방지)
    done = {"published": {"1": {"at": "2026-09-09T21:03:00+09:00", "media_id": "x"}}}
    assert pick_post(PLAN, done, now=at("2026-09-09T21:30:00")) is None

    # 계획에 없는 날짜 — 아무것도 하지 않는다
    assert pick_post(PLAN, empty, now=at("2026-09-08T21:00:00")) is None
    assert pick_post(PLAN, empty, now=at("2026-10-09T21:00:00")) is None

    # 마지막 날도 정상 선택
    assert pick_post(PLAN, empty, now=at("2026-10-08T21:00:00"))["day"] == 30

    # 게시된 날이 있어도 다른 날은 영향 없음
    assert pick_post(PLAN, done, now=at("2026-09-10T08:00:00"))["day"] == 2

    # 발행 창 경계 정확히 45분 전
    edge = at("2026-09-09T21:00:00") - dt.timedelta(minutes=WINDOW_MIN)
    assert pick_post(PLAN, empty, now=edge)["day"] == 1

    print("pick_post 10개 케이스 통과")


if __name__ == "__main__":
    run()
