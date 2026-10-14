#!/usr/bin/env python3
"""Build replaceable private runtime resources from verified originals, not external code."""
import argparse
import hashlib
import json
import re
import shutil
import wave
from pathlib import Path
from PIL import Image
from legacy_assets import Epf, dat_entries, read_palettes, private_path

ROOT = Path(__file__).resolve().parents[1]
KR_SHA = 'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'
MODELS = {'rabbit': (125, 11), 'squirrel': (25, 9), 'rat': (90, 9), 'bat': (58, 0),
          'snake': (26, 9), 'boar': (19, 9), 'spider': (97, 9), 'skeleton': (30, 0),
          'innkeeper': (51, 0), 'merchant': (67, 0), 'teacher': (68, 0), 'priest': (41, 0)}
ICON_FRAMES = {'목도': 2, '목검': 2, '도토리': 214, '토끼고기': 217,
               '철검': 17, '철단도': 12, '산삼': 229, '붉은시약': 165, '푸른시약': 166}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def export(data, out):
    out = private_path(out)
    original = Path(data).read_bytes()
    if sha(original) != KR_SHA:
        raise ValueError('KR original DAT mismatch')
    entries = dat_entries(original)
    sheets = {}
    ledger = []

    def sheet(name, epf_name, indices, color=0, palette_index=0, cell=(128, 128)):
        epf = Epf(entries[epf_name + '.epf'][2])
        palette = read_palettes(entries[epf_name + '.pal'][2])[palette_index]
        image = Image.new('RGBA', (16 * cell[0], ((len(indices) + 15) // 16) * cell[1]))
        frames = []
        for j, i in enumerate(indices):
            f = epf.frame(i)
            # Preserve original EPF canvas pivots in every animation layer.
            origin = (64, 80)
            if f.left + origin[0] < 0 or f.top + origin[1] < 0 or f.left + f.width + origin[0] > cell[0] or f.top + f.height + origin[1] > cell[1]:
                raise ValueError(f'Frame exceeds declared canvas: {name}:{i}')
            raw = f.rgba(palette, color)
            if f.width and f.height:
                sprite = Image.frombytes('RGBA', (f.width, f.height), raw)
                image.paste(sprite, (j % 16 * cell[0] + origin[0] + f.left, j // 16 * cell[1] + origin[1] + f.top))
            frames.append(dict(frame=i, region=[j % 16 * cell[0], j // 16 * cell[1], *cell],
                               left=f.left, top=f.top, width=f.width, height=f.height,
                               rgba_sha256=sha(raw), opaque=sum(a != 0 for a in f.alpha)))
        target = out / 'sprites' / (name + '.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        spec = dict(path='sprites/' + target.name, frames=frames, canvas=list(cell), origin=[64, 80],
                    sha256=sha(target.read_bytes()), epf=epf_name, palette_index=palette_index,
                    recolor_byte=color, source_kind='ORIGINAL_KR491',
                    motion_binding='INFERRED_FROM_TBL_AND_VISUAL_POSE', historical_match='UNVERIFIED')
        sheets[name] = spec
        ledger.append(dict(asset_id=name, **{k: v for k, v in spec.items() if k != 'frames'}, frames=len(frames)))

    for job, (body, head, tint) in enumerate([(2, 0, 2), (19, 33, 0), (6, 52, 2), (18, 63, 1)]):
        sheet(f'body_{job}', 'body', list(range(body * 104, (body + 1) * 104)), tint)
        sheet(f'head_{job}', 'head', list(range(head * 100, (head + 1) * 100)))
    sheet('wood_weapon', 'sword', list(range(20, 40)))
    sheet('iron_weapon', 'sword', list(range(40, 60)))
    sheet('ghost', 'ghost', list(range(Epf(entries['ghost.epf'][2]).count)))
    table = {int(v[0]): tuple(map(int, v[1:])) for v in re.findall(
        r'ID (\d+), Palette (\d+), Starting (\d+), Walk (\d+), Attack (\d+), Delay (\d+), Shadow (\d+)',
        entries['monster.tbl'][2].decode('ascii'))}
    for name, (model, tint) in MODELS.items():
        pal, start, walk, attack, delay, shadow = table[model]
        sheet(name, 'monster', list(range(start, start + 4 * (walk + attack))), tint, pal)
        sheets[name].update(model=model, walk=walk, attack=attack, delay_ms=delay,
                            semantic_binding='REFERENCE_OR_VISUAL_INFERENCE_REPLACEABLE')
    sheet('icons', 'item', list(ICON_FRAMES.values()))
    # Original effect animation; assignment to heal/damage is a labeled replacement.
    sheet('effect_heal', 'effect', list(range(35, 43)))
    sheet('effect_damage', 'effect', list(range(85, 93)))
    sheets['effect_heal']['source_kind'] = 'ORIGINAL_KR491_REPLACEMENT_SKILL_BINDING'
    sheets['effect_damage']['source_kind'] = 'ORIGINAL_KR491_REPLACEMENT_SKILL_BINDING'
    orders = entries['drworder.tbl'][2].decode('ascii').strip().split(';')
    sheets['draw_order'] = [o for o in orders if len(o) == 4]
    sheets['icons']['names'] = list(ICON_FRAMES)
    sound_path = Path(data).with_suffix('.snd')
    sounds = dat_entries(sound_path.read_bytes())
    audio = []
    for key, (_, _, raw) in sounds.items():
        if not key.endswith('.wav'):
            continue
        dest = out / 'sounds' / key
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(raw)
        with wave.open(str(dest)) as w:
            audio.append(dict(path='sounds/' + key, frames=w.getnframes(), rate=w.getframerate(),
                              channels=w.getnchannels(), bits=8*w.getsampwidth(), sha256=sha(raw)))
    sheets['sounds'] = audio
    # Event-to-number identity is unverified; keep this assignment replaceable.
    sheets['sound_bindings'] = {k: audio[i]['path'] for k, i in [('attack', 0), ('hit', 1), ('skill', 2), ('level', 3)]}
    sheets['sound_binding_provenance'] = 'ORIGINAL_WAV_REPLACEMENT_BINDING_IDENTITY_UNVERIFIED'
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    (out / 'fonts').mkdir(exist_ok=True)
    shutil.copy2(font, out / 'fonts' / font.name)
    (out / 'actors.json').write_text(json.dumps(sheets, ensure_ascii=False, separators=(',', ':')))
    report = dict(status='PASS_STATIC_EXPORT_NOT_GAMEPLAY', original_dat_sha256=KR_SHA,
                  actor_sheets=ledger, registered_candidate_frames=sum(a['frames'] for a in ledger),
                  sounds=audio, generated_image_count=0,
                  font='Noto Sans CJK SIL OFL; include system copyright file in personal package')
    return report


def numeric(out):
    source = ROOT / 'research/restoration-integrated-20261013'
    groups = {}
    for line in (source / 'NUMERIC_MASTER.jsonl').read_text().splitlines():
        v = json.loads(line)
        g = groups.setdefault(v['content_id'], dict(id=v['content_id'], name=v['content_name'],
            category=v['category'], job=v['class_scope'], level=v['level'], values={}, provenance={}))
        g['values'][v['field']] = v['value']
        g['provenance'][v['field']] = dict(field_id=v['field_id'], classification=v['classification'])
    drops = [json.loads(s) for s in (source / 'DROP_RULES.jsonl').read_text().splitlines()]
    out.mkdir(parents=True, exist_ok=True)
    (out / 'numeric.json').write_text(json.dumps(dict(contents=list(groups.values()), drops=drops,
        source_sha256=sha((source / 'NUMERIC_MASTER.jsonl').read_bytes()), source_unchanged=True),
        ensure_ascii=False, separators=(',', ':')))
    shutil.copy2(source / 'BALANCE_TESTS.json', out / 'balance_tests.json')
    return dict(contents=len(groups), field_count=19477, source_unchanged=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dat', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--report', required=True)
    a = p.parse_args()
    report = export(a.dat, a.out)
    report['numeric'] = numeric(ROOT / 'game/data')
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('actor_sheets','sounds')}))
