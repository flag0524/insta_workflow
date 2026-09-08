# content_plan.json이 plan.md의 릴스 설계 규칙을 지키는지 검사하는 스크립트
import json
import datetime as dt
import collections
import sys

WD = "월화수목금토일"


def main(path="content_plan.json"):
    d = json.load(open(path, encoding="utf-8"))
    meta, posts = d["meta"], d["posts"]
    errs = []

    def bad(msg):
        errs.append(msg)

    # 날짜 · 요일 · 순번
    prev = None
    for i, x in enumerate(posts):
        date = dt.date.fromisoformat(x["date"])
        if prev and (date - prev).days != 1:
            bad(f"day{x['day']}: 날짜가 연속하지 않음")
        prev = date
        if WD[date.weekday()] != x["weekday"]:
            bad(f"day{x['day']}: 요일 {x['weekday']} != 실제 {WD[date.weekday()]}")
        if not x["publish_at"].startswith(x["date"]):
            bad(f"day{x['day']}: publish_at과 date 불일치")
        if x["day"] != i + 1:
            bad(f"day{x['day']}: 순번 어긋남")

    if len(posts) != meta["period"]["days"]:
        bad(f"게시물 {len(posts)}개 != {meta['period']['days']}일")

    # 길이 티어
    tiers = collections.Counter(x["tier"] for x in posts)
    for t, spec in meta["length_tiers"].items():
        lo, hi = spec["range_sec"]
        if tiers[t] != spec["count"]:
            bad(f"tier {t}: {tiers[t]}건 != 계획 {spec['count']}건")
        for x in posts:
            if x["tier"] == t and not lo <= x["duration_sec"] <= hi:
                bad(f"day{x['day']}: {x['duration_sec']}초가 {t} 범위 {lo}-{hi} 밖")

    # 장면 타임라인 · 레이아웃 · 자막 길이
    rule = meta["subtitle_rule"]
    for x in posts:
        s = x["scenes"]
        if s[0]["t"][0] != 0:
            bad(f"day{x['day']}: 첫 장면이 0초에서 시작하지 않음")
        if s[-1]["t"][1] != x["duration_sec"]:
            bad(f"day{x['day']}: 마지막 장면 끝 {s[-1]['t'][1]} != 길이 {x['duration_sec']}")
        for a, b in zip(s, s[1:]):
            if a["t"][1] != b["t"][0]:
                bad(f"day{x['day']}: 장면 사이 공백 {a['t']} -> {b['t']}")
        if x["cover_scene"] >= len(s):
            bad(f"day{x['day']}: cover_scene 범위 초과")
        for j, sc in enumerate(s):
            if sc["layout"] not in meta["layouts"]:
                bad(f"day{x['day']} s{j}: 알 수 없는 layout {sc['layout']}")
            limit = rule["code_layout_max_chars"] if sc["layout"] == "code" else rule["max_chars_per_line"]
            for f in ("title", "sub"):
                if len(sc[f]) > limit:
                    bad(f"day{x['day']} s{j} [{sc['layout']}] {f}: {len(sc[f])}자 > {limit}자 — {sc[f]}")

    # 참조 무결성
    for x in posts:
        if x["hook_type"] not in meta["hook_types"]:
            bad(f"day{x['day']}: 알 수 없는 hook_type")
        if x["hashtag_set"] not in d["hashtag_sets"]:
            bad(f"day{x['day']}: 알 수 없는 hashtag_set")
        if x["bgm"] not in meta["bgm_pool"]:
            bad(f"day{x['day']}: 알 수 없는 bgm")
        if x["loop_type"] not in ("seamless", "cta_end"):
            bad(f"day{x['day']}: 알 수 없는 loop_type")
        if x["tier"] == "loop" and x["loop_type"] != "seamless":
            bad(f"day{x['day']}: loop 티어인데 seamless가 아님")

    # 훅 연속 반복 금지
    h = [x["hook_type"] for x in posts]
    for i in range(len(h) - 1):
        if h[i] == h[i + 1]:
            bad(f"day{i + 1}-day{i + 2}: 훅 유형 {h[i]} 연속")

    # 해시태그 세트
    for k, v in d["hashtag_sets"].items():
        tags = v["large"] + v["medium"] + v["small"] + v["brand"]
        if len(tags) != 17:
            bad(f"해시태그 세트 {k}: {len(tags)}개 != 17개")
        if len(set(tags)) != len(tags):
            bad(f"해시태그 세트 {k}: 중복 태그 있음")
        if len(tags) > 30:
            bad(f"해시태그 세트 {k}: 인스타 한도 30개 초과")

    # 캡션
    for x in posts:
        if len(x["caption"]) > 2200:
            bad(f"day{x['day']}: 캡션 {len(x['caption'])}자 > 2200자")

    print(f"게시물 {len(posts)}건 · 총 {sum(x['duration_sec'] for x in posts)}초")
    print("티어:", dict(tiers))
    print("훅:", dict(sorted(collections.Counter(h).items())))
    print("필러:", dict(collections.Counter(x["pillar"] for x in posts)))
    print("발행 시각:", dict(sorted(collections.Counter(x["publish_at"][11:16] for x in posts).items())))
    print()
    if errs:
        print(f"실패 {len(errs)}건")
        for e in errs:
            print("  X", e)
        return 1
    print("통과")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
