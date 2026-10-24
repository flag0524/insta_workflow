"""Fail-closed rendering of reviewed, real tool captures. No generated UI fallback."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time


class VerificationPending(ValueError):
    """The post cannot be published until its evidence is reviewed."""


def _date(value, field):
    if not isinstance(value, str) or not value.strip():
        raise VerificationPending(f"Missing {field}")
    try:
        dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise VerificationPending(f"Invalid {field}") from exc
    return value


def inspect_verified(post, root: Path) -> dict:
    """Validate manifest and hashes; return reviewed fields plus resolved asset paths.

    assets: [{file: relative path, sha256: 64 hex digits, duration_sec: 0..120}].
    All paths, including symlinks, must resolve inside this post's directory.
    """
    root = Path(root).resolve()
    ident = post.get('id')
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident):
        raise VerificationPending('Invalid post id')
    base = (root / 'verified_media' / ident).resolve()
    if not base.is_relative_to(root):
        raise VerificationPending('Evidence directory escapes root')
    manifest = base / 'manifest.json'
    if not manifest.resolve().is_relative_to(base):
        raise VerificationPending('Manifest escapes evidence directory')
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise VerificationPending('Reviewed manifest missing or unreadable') from exc
    if not isinstance(data, dict) or data.get('approved') is not True:
        raise VerificationPending('Manifest is not approved')
    if data.get('evidence_type') != 'actual_tool_capture':
        raise VerificationPending('Actual tool captures required')
    for field in ('verified_by', 'tool_model', 'narration', 'caption', 'actual_results'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise VerificationPending(f'Missing reviewed {field}')
    _date(data.get('verified_at'), 'verified_at')
    if 'capture_date' in data:
        _date(data['capture_date'], 'capture_date')
    if len(data['narration']) > 3000:
        raise VerificationPending('Narration exceeds 3000 characters')
    assets = data.get('assets')
    if not isinstance(assets, list) or not 1 <= len(assets) <= 60:
        raise VerificationPending('Provide 1..60 actual assets')
    checked = []
    for asset in assets:
        if not isinstance(asset, dict):
            raise VerificationPending('Invalid asset record')
        filename = asset.get('file')
        # Reject Windows and POSIX traversal regardless of the host OS.
        if (not isinstance(filename, str) or not filename or '\\' in filename
                or ':' in filename or Path(filename).is_absolute()
                or '..' in Path(filename).parts):
            raise VerificationPending('Unsafe asset path')
        target = (base / filename).resolve()
        if not target.is_relative_to(base) or target.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.mp4'):
            raise VerificationPending('Asset escapes directory or has unsupported format')
        duration = asset.get('duration_sec')
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or not 0 < duration <= 120):
            raise VerificationPending('Asset duration must be >0 and <=120 seconds')
        expected = asset.get('sha256')
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            raise VerificationPending('Recorded sha256 required')
        try:
            if not target.is_file() or target.stat().st_size == 0:
                raise VerificationPending('Asset missing or empty')
            digest = hashlib.sha256()
            with target.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
        except OSError as exc:
            raise VerificationPending('Asset unreadable') from exc
        if digest.hexdigest() != expected.lower():
            raise VerificationPending('Asset sha256 mismatch')
        checked.append(dict(asset, path=target))
    return dict(data, assets=checked, manifest_path=manifest)


def _fetch_tts(text):
    """Free Korean Translate TTS. Never fall back to silent audio."""
    import requests
    error = None
    for attempt in range(3):
        try:
            response = requests.get(
                'https://translate.google.com/translate_tts',
                params={'ie': 'UTF-8', 'client': 'tw-ob', 'tl': 'ko', 'q': text},
                timeout=(10, 45))
            response.raise_for_status()
            if 'audio/' not in response.headers.get('Content-Type', '').lower() or not response.content:
                raise ValueError('TTS returned no audio')
            return response.content
        except (requests.RequestException, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise RuntimeError('Korean TTS failed; reel blocked') from error


def _segments(text, limit=200):
    text = text.strip()
    while text:
        cut = min(limit, len(text))
        if len(text) > limit:
            boundary = text.rfind(' ', 0, limit + 1)
            if boundary > limit // 2:
                cut = boundary
        yield text[:cut]
        text = text[cut:].strip()


def _font():
    candidates = [os.environ.get('VERIFIED_MEDIA_FONT', ''),
                  'C:/Windows/Fonts/malgun.ttf',
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                  '/usr/share/fonts/truetype/nanum/NanumGothic.ttf']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise RuntimeError('Korean font missing: set VERIFIED_MEDIA_FONT; reel blocked')


def build_verified_reel(post, root: Path, outdir: Path, fetch_tts=None) -> tuple:
    """Return (videoPath, coverPath). Inject fetch_tts(text)->MP3 bytes for tests.

    Requires ffmpeg on PATH (or FFMPEG env var) and a Korean font. Only real
    assets are scaled/padded; no application UI or results are synthesized.
    Manifest caption is the reviewed posting caption, not generated copy.
    """
    verified = inspect_verified(post, root)
    ffmpeg = os.environ.get('FFMPEG', 'ffmpeg')
    font = _font()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verified-', dir=outdir) as scratch:
        work = Path(scratch)
        # Simple relative filter paths avoid Windows drive/colon escaping.
        shutil.copyfile(font, work / 'font.ttf')
        tts = fetch_tts or _fetch_tts
        parts = []
        for index, text in enumerate(_segments(verified['narration'])):
            audio = tts(text)
            if not isinstance(audio, (bytes, bytearray)) or not audio:
                raise RuntimeError('TTS missing; silent reel blocked')
            name = f'tts{index}.mp3'
            (work / name).write_bytes(audio)
            parts.append(f"file '{name}'")
        (work / 'audio.txt').write_text('\n'.join(parts), encoding='utf-8')
        def run(args):
            # cwd is subprocess-local; never changes caller/global cwd.
            proc = subprocess.run([ffmpeg, '-y', '-hide_banner', *args], cwd=work,
                                  capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
            if proc.returncode:
                raise RuntimeError('Media rendering failed; reel blocked: ' + proc.stderr[-2500:])
            return proc
        run(['-f', 'concat', '-safe', '0', '-i', 'audio.txt', '-vn', '-ar', '44100', '-ac', '1', 'voice.wav'])
        import wave
        with wave.open(str(work / 'voice.wav'), 'rb') as wav:
            length = wav.getnframes() / wav.getframerate()
        if not 0.2 <= length <= 180:
            raise RuntimeError('Invalid narration duration; reel blocked')
        hook = verified.get('hook', '실제 도구 시연')
        if not isinstance(hook, str):
            raise VerificationPending('Hook must be text')
        # Reviewed hook wins; neutral fallback avoids inventing performance claims.
        (work / 'hook.txt').write_text(hook[:40], encoding='utf-8')
        date_label = '검증 ' + verified['verified_at'][:10]
        if verified.get('capture_date'):
            date_label = '실제 캡처 ' + verified['capture_date'][:10] + ' | ' + date_label
        (work / 'date.txt').write_text(date_label, encoding='utf-8')
        filters = ['scale=1080:1500:force_original_aspect_ratio=decrease',
                   'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black', 'setsar=1', 'fps=30',
                   'drawtext=fontfile=font.ttf:textfile=hook.txt:expansion=none:fontsize=48:fontcolor=white:x=(w-tw)/2:y=80',
                   'drawtext=fontfile=font.ttf:textfile=date.txt:expansion=none:fontsize=28:fontcolor=white:x=(w-tw)/2:y=170']
        captions = list(_segments(verified['narration'], 22))
        for i, text in enumerate(captions):
            (work / f'sub{i}.txt').write_text(text, encoding='utf-8')
            start, end = length * i / len(captions), length * (i + 1) / len(captions)
            filters.append(f"drawtext=fontfile=font.ttf:textfile=sub{i}.txt:expansion=none:fontsize=44:fontcolor=white:box=1:boxcolor=black@0.85:boxborderw=16:x=(w-tw)/2:y=1770:enable='gte(t,{start:.4f})*lt(t,{end:.4f})'")
        assets = verified['assets']
        total = sum(a['duration_sec'] for a in assets)
        clips = []
        for i, asset in enumerate(assets):
            duration = length * asset['duration_sec'] / total
            inputs = ['-stream_loop', '-1'] if asset['path'].suffix.lower() == '.mp4' else ['-loop', '1']
            clip = f'clip{i}.mp4'
            run([*inputs, '-i', str(asset['path']), '-t', f'{duration:.6f}', '-an',
                 '-vf', 'scale=1080:1500:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30',
                 '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', clip])
            clips.append(f"file '{clip}'")
        (work / 'clips.txt').write_text('\n'.join(clips), encoding='utf-8')
        # Clips are already normalized, so apply text without rescaling them.
        run(['-f', 'concat', '-safe', '0', '-i', 'clips.txt', '-i', 'voice.wav',
             '-vf', ','.join(filters[4:]), '-map', '0:v:0', '-map', '1:a:0',
             '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
             '-t', str(length), '-shortest', '-movflags', '+faststart', 'reel.mp4'])
        run(['-i', 'reel.mp4', '-frames:v', '1', 'cover.jpg'])
        video, cover = outdir / f"{post['id']}.mp4", outdir / f"{post['id']}_cover.jpg"
        shutil.copyfile(work / 'reel.mp4', video)
        shutil.copyfile(work / 'cover.jpg', cover)
    return video, cover
