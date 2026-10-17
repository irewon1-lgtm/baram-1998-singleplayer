#!/usr/bin/env python3
"""Isolated reconstructed cape layers from held KR491 Body20 garment pixels.

Writes a prototype only. Never modifies the runtime actor catalog or game code.
The original client has no verified item-to-cape part mapping; all bindings here
are explicitly reconstructed and require actual game-screen visual review.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw

DAT_SHA = 'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
READER_SHA = 'f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2'
RAMPS = {'gold': 88, 'blue': 64, 'green': 48, 'red': 40, 'purple': 104, 'gray': 128}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def category(name):
    for color, words in [('purple', ['보라', '자주']), ('gold', ['금', '황', '노랑', '노란', '베이지']),
                         ('blue', ['파란', '파랑', '하늘', '남색', '청']),
                         ('green', ['녹', '초록', '올리브', '연두', '비취']),
                         ('red', ['빨', '붉', '장미', '분홍', '적']),
                         ('gray', ['회색', '검', '흰', '백', '은색'])]:
        if any(word in name for word in words):
            return color, 'Explicit reconstructed category selected from the Korean item name'
    return 'gray', 'Unidentified numbered/name variant uses neutral gray reconstruction; no historical mapping claimed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['runtime', 'dat', 'reader', 'table-reader', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    runtime, output = args.runtime.resolve(), args.output.resolve()
    if runtime in output.parents or output == runtime:
        raise ValueError('Prototype must be outside the immutable runtime')
    raw, reader_bytes = args.dat.read_bytes(), args.reader.read_bytes()
    if sha(raw) != DAT_SHA or sha(reader_bytes) != READER_SHA:
        raise ValueError('Held source or pinned decoder differs')
    for module_name, path in [('cape_reader', args.reader), ('cape_tables', args.table_reader)]:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    reader, tables = sys.modules['cape_reader'], sys.modules['cape_tables']
    dat = reader.dat_entries(raw)
    parts = [row for _, _, row in tables.parse_counted(dat['body.tbl'][2])]
    part = next(row for row in parts if row['ID'] == 20)
    epf = reader.Epf(dat['body.epf'][2])
    palette = reader.read_palettes(dat['body.pal'][2])[part['Palette']]
    actors = json.loads((runtime / 'gameplay-assets/actors.json').read_text())
    game = json.loads((runtime / 'gameplay_content.json').read_text())
    source_look = actors['looks']['player_armor']
    output.mkdir(parents=True, exist_ok=True)
    (output / 'images').mkdir(exist_ok=True)
    looks, sources, rendered = {}, {}, {}
    for color, ramp in RAMPS.items():
        look = {'id': 'cape_' + color, 'animations': {}, 'render_layer': 'behind_body',
                'render_by_direction': {'0': 'after_player_below_head_region', '1': 'behind_body', '2': 'behind_body', '3': 'behind_body'},
                'source_tier': 'LEGACY_RECONSTRUCTED', 'binding_scope': 'Reconstructed mantle, not a verified native cape part'}
        for action, directions in source_look['animations'].items():
            look['animations'][action] = {}
            for direction, frames in directions.items():
                result_frames = []
                for original in frames:
                    relative = next(s['relative_frame'] for s in original['source_frames'] if s['epf'] == 'Body.epf')
                    frame = epf.frame(part['Starting'] + relative)
                    # Reconstruct a flared mantle rather than retaining native
                    # robe sleeves or trouser-like hem strips. Texture samples
                    # come only from Body20 garment indices48..55, never skin.
                    cloth = [(frame.left + x, frame.top + y, frame.indices[y * frame.width + x])
                             for y in range(frame.height) for x in range(frame.width)
                             if frame.alpha[y * frame.width + x] and 48 <= frame.indices[y * frame.width + x] <= 55
                             and abs(frame.left + x) <= 8]
                    if not cloth:
                        raise ValueError('No garment pixels in native source frame')
                    image = Image.new('RGBA', (32, 32))
                    offset = [-16, -30]
                    silhouette = set()
                    for gy in range(-26, -3):
                        progress = (gy + 26) / 22
                        if direction in ['1', '3']:
                            center = -6 if direction == '1' else 6
                            half = 2 + round(3 * progress)
                        else:
                            center, half = 0, 5 + round(5 * progress)
                        for gx in range(center - half, center + half + 1):
                            # Front opening preserves the underlying legs and
                            # makes the two visible edges read as cape tails.
                            if direction == '2' and gy > -15 and abs(gx) < 6:
                                continue
                            silhouette.add((gx, gy))
                    for gx, gy in silhouette:
                        boundary = any((gx + dx, gy + dy) not in silhouette for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])
                        if boundary:
                            rgb = palette.colors[16]
                        else:
                            sampled = min(cloth, key=lambda q: abs(q[0] - gx) + abs(q[1] - gy) * 2)
                            rgb = palette.colors[ramp + sampled[2] - 48]
                        image.putpixel((gx - offset[0], gy - offset[1]), (*rgb, 255))
                    bbox = image.getbbox()
                    if bbox is None:
                        raise ValueError('Empty cape frame: ' + str(relative))
                    image = image.crop(bbox)
                    offset = [offset[0] + bbox[0], offset[1] + bbox[1]]
                    relative_path = 'images/cape-' + sha(image.tobytes() + str(offset).encode())[:24] + '.png'
                    path = output / relative_path
                    image.save(path)
                    source = {'epf': 'Body.epf', 'frame': frame.index, 'relative_frame': relative,
                              'palette_member': 'Body.pal', 'palette': part['Palette'], 'source_body_part': 20,
                              'source_indices_and_alpha_sha256': sha(frame.indices + frame.alpha),
                              'source_original_rgba_sha256': sha(frame.rgba(palette)),
                              'reconstructed_palette_ramp': ramp, 'original_offset': [frame.left, frame.top]}
                    result_frames.append({'path': relative_path, 'offset': offset,
                        'duration_ms': original['duration_ms'], 'png_sha256': sha(path.read_bytes()),
                        'source_frames': [source]})
                    sources[str(frame.index)] = source
                look['animations'][action][direction] = result_frames
        looks[look['id']] = look
    bindings = {}
    for iid, item in game['items'].items():
        if item.get('slot') != 'cape':
            continue
        color, reason = category(item['name'])
        bindings[iid] = {'cape_look': 'cape_' + color, 'color_category': color,
            'render_layer': 'behind_body', 'source_tier': 'LEGACY_RECONSTRUCTED',
            'historical_item_mapping_verified': False, 'reason': reason}
    members = {name: {'sha256': sha(dat[name.lower()][2]), 'dat_offset': dat[name.lower()][1]}
               for name in ['Body.epf', 'Body.pal', 'Body.tbl']}
    result = {'schema': 'baram.cape-layer-prototype/1', 'status': 'PROTOTYPE_GAMEPLAY_NOT_RUN',
        'looks': looks, 'cape_item_graphics': bindings,
        'source': {'dat_sha256': DAT_SHA, 'reader_sha256': READER_SHA, 'members': members,
                   'source_frames': sources, 'tool_sha256': sha(Path(__file__).read_bytes())},
        'recipe': 'Reconstructed flared cloak silhouette at native foot coordinates y-26..-4; only Body20 garment48..55 pixels sampled for folds; Body.pal16 outline; existing Body.pal8color ramps; no skin, boots or sleeve shapes; front opening and rearward side profile',
        'limits': ['Reconstructed mantle silhouette and item categories, not verified native cape association',
                   'Behind-body composite can conceal the back center; requires actual direction/action screenshots',
                   'No inventory icon used as wearable imagery', 'Final actor index/runtime/game source untouched']}
    (output / 'cape-layer-looks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    # Preview the layer alone and under the real player armor sprites in all directions.
    sheet = Image.new('RGB', (6 * 192, 4 * 192), '#5d674c')
    draw = ImageDraw.Draw(sheet)
    for col, color in enumerate(RAMPS):
        for direction in range(4):
            frame = looks['cape_' + color]['animations']['standing'][str(direction)][0]
            cape = Image.open(output / frame['path']).convert('RGBA')
            base = source_look['animations']['standing'][str(direction)][0]
            player = Image.open(runtime / 'gameplay-assets' / base['path']).convert('RGBA')
            for side, composite in [(0, False), (1, True)]:
                canvas = Image.new('RGBA', (32, 56))
                origin = (16, 50)
                if not composite or direction != 0:
                    canvas.alpha_composite(cape, (origin[0] + frame['offset'][0], origin[1] + frame['offset'][1]))
                if composite:
                    canvas.alpha_composite(player, (origin[0] + base['offset'][0], origin[1] + base['offset'][1]))
                    if direction == 0:
                        canvas.alpha_composite(cape, (origin[0] + frame['offset'][0], origin[1] + frame['offset'][1]))
                canvas = canvas.resize((96, 168), Image.Resampling.NEAREST)
                sheet.paste(canvas, (col * 192 + side * 96, direction * 192), canvas)
            draw.text((col * 192 + 3, direction * 192 + 172), f'{color} dir{direction} layer / composite', fill='white')
    sheet.save(output / 'cape-prototype-contact.png')
    print(json.dumps({'output': str(output), 'looks': len(looks), 'cape_bindings': len(bindings),
                      'source_frames': len(sources), 'native_platform': 'NOT_RUN'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
