# content_plan.json을 읽어 오늘자 릴스를 만들고 인스타그램에 게시하는 단일 엔트리포인트
import argparse
import datetime as dt
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
PLAN = ROOT / "content_plan.json"
STATE = ROOT / "state.json"
TEMPLATE = ROOT / "templates" / "scene.html"
BGM_DIR = ROOT / "assets" / "bgm"
OUT = ROOT / "out"

KST = dt.timezone(dt.timedelta(hours=9))
W, H, FPS = 1080, 1920, 30
XFADE = 0.25          # 장면 전환 시간
WINDOW_MIN = 45       # publish_at 기준 실행 허용 창
# Instagram API with Instagram Login 계열. 페이스북 페이지 연결이 필요 없고 크리에이터 계정에서 동작한다.
# 페이스북 로그인 방식(graph.facebook.com)을 쓰는 토큰이라면 이 값을 바꿔야 한다.
GRAPH = "https://graph.instagram.com/v21.0"

load_dotenv(ROOT / ".env")


# ---------- 공통 ----------

def log(msg):
    """스케줄러로 실행되면 표준출력이 사라지므로 파일에도 남긴다."""
    line = f"[{dt.datetime.now(KST):%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(ROOT / "daily.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(msg):
    """실패를 텔레그램으로 알림. 설정이 없으면 조용히 넘어간다."""
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": msg},
            timeout=15,
        )
    except Exception as e:
        log(f"알림 전송 실패: {e}")


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"published": {}}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 1. 오늘자 항목 선택 ----------

def pick_post(plan, state, force_day=None, now=None):
    if force_day:
        for p in plan["posts"]:
            if p["day"] == force_day:
                return p
        raise SystemExit(f"day {force_day} 없음")

    now = now or dt.datetime.now(KST)
    for p in plan["posts"]:
        if p["date"] != now.date().isoformat():
            continue
        if str(p["day"]) in state["published"]:
            log(f"day{p['day']} 이미 게시됨. 종료")
            return None
        # 발행 예정 시각 45분 전부터 실행. 지난 시각이면 재시도로 간주해 계속 허용
        if now >= dt.datetime.fromisoformat(p["publish_at"]) - dt.timedelta(minutes=WINDOW_MIN):
            return p
        log(f"day{p['day']} 발행 시각 전. 종료")
        return None
    log("오늘 예정된 게시물 없음. 종료")
    return None


# ---------- 2. 장면 렌더링 ----------

def render_scenes(post, outdir):
    from playwright.sync_api import sync_playwright

    tpl = TEMPLATE.read_text(encoding="utf-8")
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for i, sc in enumerate(post["scenes"]):
            page.set_content(
                tpl.replace("{{layout}}", sc["layout"])
                   .replace("{{badge}}", f"DAY {post['day']} / 30")
                   .replace("{{title}}", html.escape(sc["title"]))
                   .replace("{{sub}}", html.escape(sc["sub"]))
                   .replace("{{title_empty}}", "" if sc["title"] else "empty")
                   .replace("{{sub_empty}}", "" if sc["sub"] else "empty")
            )
            path = outdir / f"s{i + 1:02d}.png"
            page.screenshot(path=str(path))
            paths.append(path)
        browser.close()
    log(f"장면 {len(paths)}장 렌더 완료")
    return paths


# ---------- 3. 영상 조립 ----------

def build_video(post, pngs, outdir):
    """정지 PNG에 zoompan으로 완만한 줌을 주고 xfade로 이어 붙인다."""
    scenes = post["scenes"]
    n = len(scenes)
    dur = post["duration_sec"]

    # 각 장면을 XFADE만큼 늘려둔다. 전환에서 깎이는 시간을 미리 보정해 최종 길이를 duration_sec에 맞춘다
    lens = [(sc["t"][1] - sc["t"][0]) + (XFADE if i < n - 1 else 0) for i, sc in enumerate(scenes)]

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in pngs:
        cmd += ["-i", str(p)]

    bgm = BGM_DIR / f"{post['bgm']}.mp3"
    if bgm.exists():
        cmd += ["-i", str(bgm)]
    else:
        log(f"BGM 없음({bgm.name}). 무음으로 생성")
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

    filters = []
    for i, sec in enumerate(lens):
        frames = max(1, round(sec * FPS))
        # 장면마다 줌 방향을 번갈아 바꿔 단조로움을 줄인다
        z = f"min(1+0.0006*on,1.10)" if i % 2 == 0 else f"max(1.10-0.0006*on,1.0)"
        filters.append(
            f"[{i}:v]scale=1620:2880,setsar=1,"
            f"zoompan=z='{z}':d={frames}:x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
            f":s={W}x{H}:fps={FPS}[v{i}]"
        )

    prev, acc = "v0", lens[0]
    for i in range(1, n):
        out = f"x{i}"
        filters.append(
            f"[{prev}][v{i}]xfade=transition=fade:duration={XFADE}:offset={acc - XFADE:.3f}[{out}]"
        )
        acc += lens[i] - XFADE
        prev = out
    filters.append(f"[{prev}]format=yuv420p[vout]")

    ai = n
    if bgm.exists():
        filters.append(
            f"[{ai}:a]atrim=0:{dur},apad=whole_dur={dur},volume=0.35,"
            f"afade=t=out:st={max(0, dur - 0.6):.2f}:d=0.6[aout]"
        )
    else:
        filters.append(f"[{ai}:a]atrim=0:{dur}[aout]")

    video = outdir / "reel.mp4"
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]", "-t", str(dur),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(video),
    ]
    subprocess.run(cmd, check=True)
    log(f"영상 조립 완료: {video.name} ({video.stat().st_size / 1e6:.1f}MB)")
    return video


# ---------- 4. 캡션 ----------

def build_caption(plan, post):
    tags = plan["hashtag_sets"][post["hashtag_set"]]
    line = " ".join(tags["large"] + tags["medium"] + tags["small"] + tags["brand"])
    caption = f"{post['caption']}\n\n.\n.\n.\n{line}"
    if len(caption) > 2200:
        raise ValueError(f"day{post['day']} 캡션 {len(caption)}자 > 2200자")
    return caption


# ---------- 5. 호스팅 ----------

def upload_hosting(video, cover):
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
    )
    v = cloudinary.uploader.upload_large(str(video), resource_type="video", folder="reels")
    c = cloudinary.uploader.upload(str(cover), folder="reels")
    log("Cloudinary 업로드 완료")
    return v["secure_url"], c["secure_url"]


# ---------- 6. 게시 ----------

def publish_reel(video_url, cover_url, caption):
    ig_id, token = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]

    r = requests.post(
        f"{GRAPH}/{ig_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "cover_url": cover_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=60,
    )
    r.raise_for_status()
    creation_id = r.json()["id"]
    log(f"컨테이너 생성: {creation_id}")

    # 인코딩은 비동기다. FINISHED가 될 때까지 기다린다
    deadline = time.time() + 300
    while time.time() < deadline:
        s = requests.get(
            f"{GRAPH}/{creation_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        ).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"인코딩 실패: {s.get('status')}")
        log(f"인코딩 대기 중... ({code})")
        time.sleep(5)
    else:
        raise TimeoutError(f"인코딩 5분 초과. creation_id={creation_id}")

    r = requests.post(
        f"{GRAPH}/{ig_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=60,
    )
    r.raise_for_status()
    media_id = r.json()["id"]
    log(f"게시 완료: {media_id}")
    return media_id


# ---------- 환경 점검 ----------

REQUIRED_ENV = [
    "IG_USER_ID", "IG_ACCESS_TOKEN",
    "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
]


def check_env():
    ok = True
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("ffmpeg: OK")
    except Exception:
        print("ffmpeg: MISSING — PATH에 등록하세요")
        ok = False

    try:
        import playwright  # noqa: F401
        print("playwright: OK")
    except ImportError:
        print("playwright: MISSING — pip install playwright && playwright install chromium")
        ok = False

    for k in REQUIRED_ENV:
        if os.getenv(k):
            print(f"{k}: OK")
        else:
            print(f"{k}: MISSING — .env에 추가하세요")
            ok = False

    # 키가 있어도 토큰이 만료됐을 수 있다. 실제로 한 번 호출해 확인한다
    if os.getenv("IG_ACCESS_TOKEN") and os.getenv("IG_USER_ID"):
        try:
            r = requests.get(
                f"{GRAPH}/{os.environ['IG_USER_ID']}",
                params={"fields": "username,account_type", "access_token": os.environ["IG_ACCESS_TOKEN"]},
                timeout=20,
            )
            if r.status_code == 200:
                d = r.json()
                print(f"토큰 검증: OK — @{d.get('username')} ({d.get('account_type')})")
            else:
                print(f"토큰 검증: 실패 HTTP {r.status_code} — {r.json().get('error', {}).get('message')}")
                ok = False
        except Exception as e:
            print(f"토큰 검증: 호출 실패 {type(e).__name__}")
            ok = False

    # 값이 채워져 있어도 대시보드의 가려진 표시(****)를 복사했을 수 있다. 실제로 인증해 본다
    if all(os.getenv(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")):
        try:
            import cloudinary
            import cloudinary.api

            cloudinary.config(
                cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
                api_key=os.environ["CLOUDINARY_API_KEY"],
                api_secret=os.environ["CLOUDINARY_API_SECRET"],
            )
            cloudinary.api.ping()
            print("Cloudinary 인증: OK")
        except Exception as e:
            print(f"Cloudinary 인증: 실패 — {str(e)[:120]}")
            ok = False

    if not TEMPLATE.exists():
        print(f"{TEMPLATE.name}: MISSING")
        ok = False

    missing_bgm = [b for b in json.loads(PLAN.read_text(encoding="utf-8"))["meta"]["bgm_pool"]
                   if not (BGM_DIR / f"{b}.mp3").exists()]
    if missing_bgm:
        print(f"BGM 없음: {', '.join(missing_bgm)} — 무음으로 생성됩니다")

    print("\n통과" if ok else "\n실패")
    return 0 if ok else 1


# ---------- 메인 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, help="특정 day를 강제 실행 (테스트용)")
    ap.add_argument("--dry-run", action="store_true", help="영상까지만 만들고 업로드하지 않음")
    ap.add_argument("--check-env", action="store_true", help="실행 환경 점검")
    args = ap.parse_args()

    if args.check_env:
        return check_env()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    state = load_state()

    post = pick_post(plan, state, args.day)
    if not post:
        return 0

    log(f"day{post['day']} 시작 — {post['topic']}")
    outdir = OUT / f"day{post['day']:02d}"
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        pngs = render_scenes(post, outdir)
        video = build_video(post, pngs, outdir)
        caption = build_caption(plan, post)

        if args.dry_run:
            log(f"dry-run 종료. {video}")
            return 0

        video_url, cover_url = upload_hosting(video, pngs[post["cover_scene"]])
        media_id = publish_reel(video_url, cover_url, caption)

        state["published"][str(post["day"])] = {
            "at": dt.datetime.now(KST).isoformat(),
            "media_id": media_id,
            "topic": post["topic"],
        }
        save_state(state)
        return 0

    except Exception as e:
        log(f"실패: {e}")
        notify(f"[인스타 자동화] day{post['day']} 실패\n{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
