"""Excel-backed, one-format/day publishing. Reviewed real evidence required for reels."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
from verified_media import VerificationPending, inspect_verified, build_verified_reel

ROOT = Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))
PLAN = ROOT / 'content_plan_20261025.json'


def state_bucket(post):
    return 'published' if post['format'] == 'reel' else 'published_carousel'


def validate_plan(plan):
    posts = plan['posts']
    assert plan['meta']['version'] == 2
    assert plan['meta']['account'] == 'flag_21'
    assert len(posts) == 30
    assert len({p['id'] for p in posts}) == 30
    start = dt.date.fromisoformat(plan['meta']['period']['start'])
    assert plan['meta']['period']['end'] == (start + dt.timedelta(days=29)).isoformat()
    counts = {'reel': 0, 'carousel': 0}
    axes = {'기술스택': 0, '트렌드': 0, '자동화': 0}
    for i, p in enumerate(posts):
        assert p['day'] == i + 1
        assert p['date'] == (start + dt.timedelta(days=i)).isoformat()
        at = dt.datetime.fromisoformat(p['publish_at'])
        assert at.date().isoformat() == p['date'] and at.hour == 20 and at.minute == 0
        assert at.utcoffset() == dt.timedelta(hours=9)
        assert p['format'] in counts
        counts[p['format']] += 1
        axes[p['axis']] += 1
        assert p['axis'] == ['기술스택', '트렌드', '자동화'][i % 3]
        assert len(p['hashtags']) == len(set(p['hashtags'])) == 5
        assert all(t.startswith('#') and not any(c.isspace() for c in t) for t in p['hashtags'])
        assert p['topic'] and p['caption'] and p['hook']
        if p['format'] == 'carousel':
            assert len(p['cards']) == 6
            assert all(c['title'] and c['body'] for c in p['cards'])
        else:
            assert p.get('verification_required') is True
            assert p['voiceover_draft'] and p['experiment']['prompt']
    assert counts == {'reel': 15, 'carousel': 15}
    assert set(axes.values()) == {10}
    return True


def is_done(post, state):
    # Date+format IDs cannot collide with legacy numeric day identifiers.
    return post['id'] in state.get(state_bucket(post), {})


def choose_post(plan, state, now=None, force_day=None, dry_run=False):
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    today = now.date()
    if force_day is not None:
        post = next((p for p in plan['posts'] if p['day'] == force_day), None)
        if post is None:
            raise ValueError('DAY outside active plan')
        if dry_run:
            return post
        if is_done(post, state):
            raise ValueError('Already published; forced duplicate blocked')
        pdate = dt.date.fromisoformat(post['date'])
        due = dt.datetime.fromisoformat(post['publish_at'])
        recovery = (pdate == today - dt.timedelta(days=1) and dt.time(7, 15) <= now.time() < dt.time(20))
        if not ((pdate == today and now >= due) or recovery):
            raise ValueError('Forced publication outside allowed schedule blocked')
        return post
    for p in plan['posts']:
        if p['date'] == today.isoformat() and not is_done(p, state):
            if now >= dt.datetime.fromisoformat(p['publish_at']):
                return p
    # Only yesterday; morning recovery applies equally to reels and carousels.
    # Never backfill retired plans or publish an extra backlog item at 20:20.
    if dt.time(7, 15) <= now.time() < dt.time(20):
        yesterday = (today - dt.timedelta(days=1)).isoformat()
        for p in plan['posts']:
            if p['date'] == yesterday and not is_done(p, state):
                return p
    return None


def summary(text):
    print(text, flush=True)
    target = os.getenv('GITHUB_STEP_SUMMARY')
    if target:
        with open(target, 'a', encoding='utf-8') as stream:
            stream.write(text + '\n\n')


def _caption(text, post):
    return text.strip() + '\n\n' + ' '.join(post['hashtags'])


def render_cards(post, outdir):
    from playwright.sync_api import sync_playwright
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
        for i, card in enumerate(post['cards']):
            title, body = html.escape(card['title']), html.escape(card['body'])
            badge = html.escape(f"DAY {post['day']} / 30 · {post['axis']}")
            markup = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><style>
*{{box-sizing:border-box}}body{{margin:0;width:1080px;height:1350px;overflow:hidden;background:#102638;color:#f7fbff;font-family:'Noto Sans CJK KR','Malgun Gothic',sans-serif}}
main{{height:100%;padding:82px 78px;display:flex;flex-direction:column}}
.badge{{font-size:28px;color:#61d7d0;letter-spacing:1px}}.line{{width:90px;height:8px;background:#61d7d0;margin:50px 0 45px}}
h1{{font-size:66px;line-height:1.35;margin:0 0 60px;word-break:keep-all;overflow-wrap:anywhere}}
.body{{font-size:49px;line-height:1.65;word-break:keep-all;overflow-wrap:anywhere;white-space:pre-wrap}}
footer{{margin-top:auto;border-top:1px solid #547080;padding-top:25px;color:#b1c7d4;font-size:25px;line-height:1.7}}
</style><main><div class="badge">{badge} · {i+1}/6</div><div class="line"></div><h1>{title}</h1><div class="body">{body}</div><footer>@flag_21 · 공공기관 AI 실무<br>가상 예시·검수 안내 | 기관 정책·원문 확인 우선</footer></main></html>'''
            page.set_content(markup)
            page.evaluate('document.fonts.ready')
            overflow = page.locator('footer').evaluate('(el) => el.getBoundingClientRect().bottom > 1310')
            if overflow:
                raise RuntimeError('Carousel text overflows safe area; publication blocked')
            path = outdir / f'card_{i+1:02}.png'
            page.screenshot(path=str(path))
            paths.append(path)
        browser.close()
    return paths


def verify_target(legacy):
    import requests
    response = requests.get(f"{legacy.GRAPH}/{os.environ['IG_USER_ID']}",
                            params={'fields': 'username', 'access_token': os.environ['IG_ACCESS_TOKEN']}, timeout=20)
    if response.status_code != 200:
        raise RuntimeError(f'Account verification failed HTTP {response.status_code}')
    if response.json().get('username') != 'flag_21':
        raise RuntimeError('Target account mismatch; publication blocked')


def run(args):
    import daily as legacy
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    validate_plan(plan)
    state = legacy.load_state()
    post = choose_post(plan, state, force_day=args.day, dry_run=args.dry_run)
    if post is None:
        summary('게시할 활성 계획 항목 없음. 기존 미게시분은 새 계획으로 자동 이월하지 않음.')
        return 0
    outdir = ROOT / 'out' / post['id']
    try:
        if post['format'] == 'reel':
            evidence = inspect_verified(post, ROOT)
            video, cover = build_verified_reel(post, ROOT, outdir)
            caption = _caption(evidence['caption'], post)
            if args.dry_run:
                summary(f"DRY RUN: DAY {post['day']} 실제 시연 릴스 렌더 완료. 게시·업로드 없음.")
                return 0
            verify_target(legacy)
            # Ambiguous publish failures are marked pending_manual below, not blindly retried.
            url, cover_url = legacy.upload_hosting(video, cover)
            media = publish_safely(legacy, post, state, url, cover_url, caption)
        else:
            images = render_cards(post, outdir)
            caption = _caption(post['caption'], post)
            if args.dry_run:
                summary(f"DRY RUN: DAY {post['day']} 캐러셀 6장 렌더 완료. 게시·업로드 없음.")
                return 0
            verify_target(legacy)
            urls = legacy.upload_carousel_images(images)
            media = publish_safely(legacy, post, state, urls, None, caption)
        state.setdefault(state_bucket(post), {})[post['id']] = {
            'at': dt.datetime.now(KST).isoformat(), 'media_id': media,
            'topic': post['topic'], 'date': post['date'], 'format': post['format']}
        state.get('blocked', {}).pop(post['id'], None)
        state.get('pending_manual', {}).pop(post['id'], None)
        legacy.save_state(state)
        summary(f"게시 완료: DAY {post['day']} / {post['date']} / {post['format']} / media_id={media}")
        return 0
    except VerificationPending as exc:
        reason = str(exc)
        previous = state.setdefault('blocked', {}).get(post['id'], {})
        today = dt.datetime.now(KST).date().isoformat()
        state['blocked'][post['id']] = {'date': today, 'reason': reason, 'topic': post['topic']}
        legacy.save_state(state)
        summary(f"::warning::DAY {post['day']} 게시 보류 — 실제 시연 검증 미완료: {reason}")
        if previous.get('date') != today:
            legacy.notify(f"[인스타] DAY {post['day']} 실제 시연 검증 미완료로 보류. GitHub 실행 요약 확인.")
        return 0
    except Exception as exc:
        summary(f"::error::DAY {post['day']} 실패: {type(exc).__name__}")
        legacy.notify(f"[인스타] DAY {post['day']} 게시 실패: {type(exc).__name__}. 실행 로그 확인.")
        raise


def publish_safely(legacy, post, state, media_source, cover_url, caption):
    """Fail closed on uncertain publication; never erase legacy publication history."""
    if post['id'] in state.get('pending_manual', {}):
        raise RuntimeError('Previous publication result uncertain; manual reconciliation required')
    import requests
    ig_id, token = os.environ['IG_USER_ID'], os.environ['IG_ACCESS_TOKEN']
    if post['format'] == 'reel':
        creation_id = legacy._create_container(ig_id, token, media_source, cover_url, caption)
    else:
        children = []
        for url in media_source:
            response = requests.post(f'{legacy.GRAPH}/{ig_id}/media',
                data={'image_url': url, 'is_carousel_item': 'true', 'access_token': token}, timeout=60)
            response.raise_for_status()
            children.append(response.json()['id'])
        response = requests.post(f'{legacy.GRAPH}/{ig_id}/media',
            data={'media_type': 'CAROUSEL', 'children': ','.join(children),
                  'caption': caption, 'access_token': token}, timeout=60)
        response.raise_for_status()
        creation_id = response.json()['id']
    code, _ = legacy._wait_encoding(creation_id, token)
    if code != 'FINISHED':
        raise RuntimeError(f'Unpublished container not ready ({code}); safe scheduled retry allowed')
    # Save intent immediately before the publish call, not before upload/encoding.
    # Earlier failures are safe to retry; an ambiguous publish result is not.
    state.setdefault('pending_manual', {})[post['id']] = {
        'at': dt.datetime.now(KST).isoformat(), 'topic': post['topic'], 'creation_id': creation_id}
    legacy.save_state(state)
    response = requests.post(f'{legacy.GRAPH}/{ig_id}/media_publish',
        data={'creation_id': creation_id, 'access_token': token}, timeout=60)
    response.raise_for_status()
    return response.json()['id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--day', type=int)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--readiness', action='store_true')
    args = parser.parse_args()
    if args.readiness:
        plan = json.loads(PLAN.read_text(encoding='utf-8'))
        ready, held = [], []
        for post in plan['posts']:
            if post['format'] == 'reel':
                try:
                    inspect_verified(post, ROOT)
                    ready.append(post['day'])
                except VerificationPending:
                    held.append(post['day'])
        summary(f'실제 시연 검증 완료 DAY: {ready}; 자료 미확보로 보류 DAY: {held}. 캐러셀 15편은 엑셀 문안으로 생성.')
        return 0
    if args.validate_only:
        validate_plan(json.loads(PLAN.read_text(encoding='utf-8')))
        summary('활성 30일 계획 검증 통과')
        return 0
    import daily as legacy
    if not legacy.acquire_lock():
        return 0
    try:
        return run(args)
    finally:
        legacy.release_lock()


if __name__ == '__main__':
    raise SystemExit(main())
