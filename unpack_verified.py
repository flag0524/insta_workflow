"""Unpack only reviewed media, never executable files or paths outside verified_media."""
from pathlib import Path, PurePosixPath
import stat
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'verified_media_20261025.zip'


def unpack(root=ROOT, archive=ARCHIVE):
    root = Path(root).resolve()
    archive = Path(archive)
    if not archive.is_file():
        print('Actual media archive absent; evidence-gated Reels remain held.')
        return 0
    with ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 300 or sum(i.file_size for i in infos) > 64 * 1024 * 1024:
            raise ValueError('Evidence archive exceeds limits')
        checked = []
        for info in infos:
            name = info.filename
            path = PurePosixPath(name)
            if '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive member')
            if len(path.parts) < 3 or path.parts[0] != 'verified_media':
                raise ValueError('Archive member outside evidence folder')
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Archive symlinks forbidden')
            target = (root / Path(*path.parts)).resolve()
            if not target.is_relative_to(root / 'verified_media'):
                raise ValueError('Archive member escapes evidence folder')
            if info.is_dir():
                continue
            if target.suffix.lower() not in ('.json', '.png', '.jpg', '.jpeg', '.webp', '.mp4'):
                raise ValueError('Executable or unsupported archive member')
            checked.append((info, target))
        for info, target in checked:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
    print(f'Extracted {len(checked)} evidence files; each manifest still requires hash/review validation.')
    return len(checked)


if __name__ == '__main__':
    unpack()
