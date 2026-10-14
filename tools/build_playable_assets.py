#!/usr/bin/env python3
"""Build replaceable private runtime resources from verified originals, not external code."""
import argparse
import hashlib
import json
import re
import shutil
import wave
import struct
from pathlib import Path
from PIL import Image
from legacy_assets import Epf, dat_entries, read_palettes, private_path

ROOT = Path(__file__).resolve().parents[1]
KR_SHA = 'f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def export(data, out):
    out = private_path(out)
    original = Path(data).read_bytes()
    if sha(original) != KR_SHA:
        raise ValueError('KR original DAT mismatch')
    entries = dat_entries(original)
    bindings=json.loads((ROOT/'game/data/runtime_bindings.json').read_text())
    sheets = {}
    ledger = []

    def sheet(name, epf_name, indices, color=0, palette_index=0, cell=(128, 128),pal_name=None,origin=(64,80),frame_palettes=None):
        epf = Epf(entries[epf_name + '.epf'][2])
        all_palettes = read_palettes(entries[(pal_name or epf_name) + '.pal'][2])
        image = Image.new('RGBA', (16 * cell[0], ((len(indices) + 15) // 16) * cell[1]))
        frames = []
        for j, i in enumerate(indices):
            f = epf.frame(i)
            selected_palette=frame_palettes[j] if frame_palettes is not None else palette_index
            palette=all_palettes[selected_palette]
            # Preserve original EPF canvas pivots in every animation layer.
            if f.left + origin[0] < 0 or f.top + origin[1] < 0 or f.left + f.width + origin[0] > cell[0] or f.top + f.height + origin[1] > cell[1]:
                raise ValueError(f'Frame exceeds declared canvas: {name}:{i}')
            raw = f.rgba(palette, color)
            if f.width and f.height:
                sprite = Image.frombytes('RGBA', (f.width, f.height), raw)
                image.paste(sprite, (j % 16 * cell[0] + origin[0] + f.left, j // 16 * cell[1] + origin[1] + f.top))
            frames.append(dict(frame=i, region=[j % 16 * cell[0], j // 16 * cell[1], *cell],
                               left=f.left, top=f.top, width=f.width, height=f.height,
                               rgba_sha256=sha(raw), opaque=sum(a != 0 for a in f.alpha),palette_index=selected_palette))
        target = out / 'sprites' / (name + '.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        spec = dict(path='sprites/' + target.name, frames=frames, canvas=list(cell), origin=list(origin),
                    sha256=sha(target.read_bytes()), epf=epf_name, palette_index=palette_index,
                    recolor_byte=color, source_kind='ORIGINAL_KR491',
                    motion_binding='INFERRED_FROM_TBL_AND_VISUAL_POSE', historical_match='UNVERIFIED')
        sheets[name] = spec
        ledger.append(dict(asset_id=name, **{k: v for k, v in spec.items() if k != 'frames'}, frames=len(frames)))

    for job, (body, head, tint) in enumerate(bindings['players']):
        sheet(f'body_{job}', 'body', list(range(body * 104, (body + 1) * 104)), tint)
        sheet(f'head_{job}', 'head', list(range(head * 100, (head + 1) * 100)))
    for key,(model,tint) in bindings['outfits'].items():
        sheet(key,'body',list(range(model*104,(model+1)*104)),tint)
    for key,(epf,model,tint) in bindings['weapons'].items():
        sheet(key,epf,list(range(model*20,(model+1)*20)),tint)
    sheet('ghost', 'ghost', list(range(Epf(entries['ghost.epf'][2]).count)))
    table = {int(v[0]): tuple(map(int, v[1:])) for v in re.findall(
        r'ID (\d+), Palette (\d+), Starting (\d+), Walk (\d+), Attack (\d+), Delay (\d+), Shadow (\d+)',
        entries['monster.tbl'][2].decode('ascii'))}
    for name, (model, tint) in bindings['monsters'].items():
        pal, start, walk, attack, delay, shadow = table[model]
        sheet(name, 'monster', list(range(start, start + 4 * (walk + attack))), tint, pal)
        sheets[name].update(model=model, walk=walk, attack=attack, delay_ms=delay,
                            semantic_binding='REFERENCE_OR_VISUAL_INFERENCE_REPLACEABLE')
    item_pal={int(i):int(p) for i,p in re.findall(r'ID (\d+), Palette (\d+)',entries['item.tbl'][2].decode('ascii'))}
    icon_indices=list(bindings['icons'].values())
    sheet('icons','item',icon_indices,frame_palettes=[item_pal[i] for i in icon_indices])
    # Original effect animation; assignment to heal/damage is a labeled replacement.
    sheet('effect_heal', 'effect', list(range(35, 43)))
    sheet('effect_damage', 'effect', list(range(85, 93)))
    sheets['effect_heal']['source_kind'] = 'ORIGINAL_KR491_REPLACEMENT_SKILL_BINDING'
    sheets['effect_damage']['source_kind'] = 'ORIGINAL_KR491_REPLACEMENT_SKILL_BINDING'
    # Resolve effect sequences and per-frame palettes from the actual paired tables.
    effect_text=entries['effect.tbl'][2].decode('ascii')
    frame_pal=entries['effect.frm'][2]
    effect_count=struct.unpack_from('<I',frame_pal)[0]
    if len(frame_pal)!=4+4*effect_count:raise ValueError('Effect FRM length mismatch')
    effect_palettes=[struct.unpack_from('<I',frame_pal,4+4*i)[0] for i in range(effect_count)]
    for role,effect_id in bindings['skill_effects'].items():
        match=re.search(r'^ID '+str(effect_id)+r', (.*?)(?=^ID |\Z)',effect_text,re.M|re.S)
        if not match:raise ValueError('Missing source effect record')
        pairs=[(int(i),int(ms)) for i,ms in re.findall(r'Frame# (\d+), Delay (\d+)',match.group(0))]
        fronts=int(re.search(r'NumFrontFrames (\d+)',match.group(0))[1]);pairs=pairs[:fronts]
        if not pairs:raise ValueError('Selected effect has no front sequence')
        indices=[i for i,ms in pairs]
        # Some effects use different palettes within one sequence. Export each
        # original frame with its own declared palette, keeping one actor sheet.
        pal_indices=[effect_palettes[i] for i in indices]
        name='fx_'+role
        sheet(name,'effect',indices,frame_palettes=pal_indices)
        sheets[name].update(source_effect_id=effect_id,delays_ms=[ms for i,ms in pairs],
                            source_kind='ORIGINAL_SEQUENCE_REPLACEMENT_SEMANTIC_ROLE',lifetime_ms=sum(ms for i,ms in pairs))
    sheet('ui_border','dlgframe',list(range(9)),cell=(16,16),pal_name='baram',origin=(0,0))
    sheet('ui_bars','bar',list(range(3)),cell=(100,11),pal_name='baram',origin=(0,0))
    orders = entries['drworder.tbl'][2].decode('ascii').strip().split(';')
    sheets['draw_order'] = [o for o in orders if len(o) == 4]
    sheets['icons']['names'] = list(bindings['icons'])
    sheets['equipment_bindings']=bindings['equipment']
    sheets['motion_bindings']=bindings['motion']
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
