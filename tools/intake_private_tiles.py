#!/usr/bin/env python3
"""Verify every nested handoff member and every tile; emit metadata, never art, in Git."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from legacy_assets import private_path

OUTER_SHA = 'f36929c43d775058678a708a1da7a140ea13e0e9243d5f4fc2b5e304fa54500b'
BUNDLE_SHA = '18581f104aa725eb615a205d428a10b46bd670b956876b99fa92ce32ebdc1514'
COUNTS = dict(A=4897, B=2973, C=6965)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def intake(source, out, report):
    out = private_path(out)
    raw = Path(source).read_bytes()
    if digest(raw) != OUTER_SHA:
        raise ValueError('Handoff SHA256 mismatch')
    files, frames = [], []
    out.mkdir(parents=True, exist_ok=True)
    with ZipFile(io.BytesIO(raw)) as outer:
        for entry in outer.infolist():
            name = entry.filename
            if entry.is_dir():
                continue
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or entry.file_size > 32_000_000:
                raise ValueError('Unsafe ZIP member')
            data = outer.read(entry)  # full CRC verification, including scripts and documentation
            files.append(dict(name=name, bytes=len(data), sha256=digest(data), read_status='PASS_FULL_BYTES'))
            if not name.endswith('.zip'):
                dest = out / 'handoff' / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                if path.suffix in ('.py', '.gd', '.md', '.json'):
                    data.decode('utf-8')
                continue
            if digest(data) != BUNDLE_SHA:
                raise ValueError('Nested atlas ZIP SHA256 mismatch')
            with ZipFile(io.BytesIO(data)) as nested:
                expected = {'MANIFEST.json', 'README.txt'} | {
                    f'Tile{g}_{suffix}' for g in COUNTS for suffix in ['frame_map.json', 'palette0_atlas.png']}
                if set(nested.namelist()) != expected or len(nested.namelist()) != len(expected):
                    raise ValueError('Missing, duplicated or unexpected nested member')
                bundle = {n: nested.read(n) for n in nested.namelist()}
                manifest = json.loads(bundle['MANIFEST.json'])
                tile_dir = out / 'tiles'
                tile_dir.mkdir(exist_ok=True)
                for n, b in bundle.items():
                    (tile_dir / n).write_bytes(b)
                    files.append(dict(name=name + '!' + n, bytes=len(b), sha256=digest(b),
                                      read_status='PASS_FULL_PNG_DECODE' if n.endswith('.png') else 'PASS_FULL_BYTES'))
                for group in manifest['groups']:
                    g = group['group']
                    if digest(bundle[group['atlas_name']]) != group['atlas_sha256'] or digest(bundle[group['map_name']]) != group['map_sha256']:
                        raise ValueError('Pinned inner file SHA256 mismatch')
                    mapping = json.loads(bundle[group['map_name']])
                    image = Image.open(io.BytesIO(bundle[group['atlas_name']]))
                    image.load()
                    image = image.convert('RGBA')
                    if image.size != (3072, math.ceil(COUNTS[g] / 128) * 24) or len(mapping['frames']) != COUNTS[g]:
                        raise ValueError('Atlas size/count mismatch')
                    for i, f in enumerate(mapping['frames']):
                        if (f['i'], f['x'], f['y']) != (i, i % 128 * 24, i // 128 * 24):
                            raise ValueError('Frame coordinate mismatch')
                        if not (0 <= f['w'] <= 24 and 0 <= f['h'] <= 24 and 0 <= f['left'] < 24 and 0 <= f['top'] < 24
                                and f['left'] + f['w'] <= 24 and f['top'] + f['h'] <= 24):
                            raise ValueError(f'Invalid original frame bounds: {g}:{i}')
                        tile = image.crop((f['x'], f['y'], f['x'] + 24, f['y'] + 24))
                        alpha = tile.getchannel('A')
                        histogram = alpha.histogram()
                        opaque = 576 - histogram[0]
                        if opaque != f['opaque'] or histogram[0] + histogram[255] != 576:
                            raise ValueError('Alpha/stencil mismatch')
                        frames.append(dict(asset_id=f'{g}:{i}', group=g, index=i,
                                           rgba_sha256=digest(tile.tobytes()), opaque=opaque,
                                           source_kind='ORIGINAL_UNDATED_UPLOADED_EDITOR',
                                           automatic_status='PASS_PIXELS_COORDINATES_STENCIL',
                                           visual_review='NOT_REVIEWED', engine_registration='NOT_RUN',
                                           game_use=0, unused_reason='NOT_YET_PLACED'))
    result = dict(handoff_sha256=OUTER_SHA, bundle_sha256=BUNDLE_SHA, archive_members=len(files),
                  files=files, total_frames=len(frames), valid_frames=len(frames),
                  unique_rgba=len({f['rgba_sha256'] for f in frames}),
                  groups=COUNTS, frames=frames,
                  visual_review_count=0, engine_registered_count=0, game_used_unique_ids=0,
                  status='PASS_AUTOMATIC_ONLY_NOT_VISUAL_OR_GAME')
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('frames', 'files')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--report', required=True)
    a = p.parse_args()
    intake(a.source, a.out, a.report)
