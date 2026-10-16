"""Read-only selected RTK grant-route evidence; never executes archived sources."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--package', type=Path, required=True)
p.add_argument('--failures', type=Path, required=True)
p.add_argument('--private-output', type=Path, required=True)
a = p.parse_args()
reference = a.package / 'inputs/reference_sources.zip'
assert hashlib.sha256(reference.read_bytes()).hexdigest() == '6e922fc3725c52e9bad3dd45924756c57e01781a36c9fd9b8eb35cd81291c508'
failures = json.loads(a.failures.read_text())['failures']
failed_ids = {r['record_id'] for r in failures if r['relation'] == 'skill_to_job'}
assert len(failed_ids) == 115
catalog = a.package / 'docs/rebuild/p1_5/selected_content/na_reference_rtk_sql.jsonl'
assert hashlib.sha256(catalog.read_bytes()).hexdigest() == 'e46a8a3a2c2250127af5e7bab145bcd29645957e7e41e68f6453109aedbb8489'
rows = [json.loads(line) for line in catalog.read_text().splitlines()]
spells = {r['original_value']['SplIdentifier']: r for r in rows if r['record_id'] in failed_ids}
assert len(spells) == 115 and all(r['original_value']['SplPthId'] == '99' for r in spells.values())
routes, members = [], {}
with zipfile.ZipFile(reference) as z:
    total = 0
    for i in z.infolist():
        n = i.filename
        if not n.startswith('RTK-Server/rtklua/') or not n.endswith('.lua'):
            continue
        assert i.file_size <= 1_000_000 and '..' not in Path(n).parts and not n.startswith('/')
        assert not ((i.external_attr >> 16) & 0o170000 == 0o120000)
        total += i.file_size
        assert total <= 100_000_000
        raw = z.read(i)
        for line_no, line in enumerate(raw.decode('utf8').splitlines(), 1):
            m = re.search(r'addSpell\s*\(\s*["\x27]([^"\x27]+)["\x27]', line)
            if m and m.group(1) in spells:
                key = m.group(1)
                routes.append({'record_id': spells[key]['record_id'], 'key': key,
                    'member': n, 'line': line_no, 'member_sha256': hashlib.sha256(raw).hexdigest(),
                    'interpretation': 'Explicit player:addSpell literal in static source; reachability and branch prerequisites need Codex test.',
                    'KR_selected_value': None, 'test_status': 'NOT_RUN'})
                members[n] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    for n in ['RTK-Server/rtk/src/map/sl.c', 'Project1998/Server/Content.Spells.cs']:
        raw = z.read(n)
        members[n] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
a.private_output.mkdir(parents=True, exist_ok=True)
out = {'schema': 'baram.work.na_grant_evidence/1', 'source_commit': 'e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6',
    'frozen_failure_edges': 154, 'unchanged_result': 'FAIL', 'path99_failed_edges': 115,
    'direct_grant_sites': len(routes), 'distinct_granted_spell_records': len({r['record_id'] for r in routes}),
    'routes': routes, 'members': members,
    'comment_conflict': {'spell': 'spot_traps', 'reference_comment': 'Project1998/Server/Content.Spells.cs:1550-1552 describes companion-only',
      'RTK_code': 'RTK-Server/rtklua/Accepted/NPCs/Common/dog_linguist.lua:94-115 explicitly grants to player class2/7 with level>=60 and quest/kill gates',
      'disposition': 'Different source claims; neither is Korean target-era truth. Preserve both, test receiving runtime separately.'},
    'trainer_filter': {'member': 'RTK-Server/rtk/src/map/sl.c', 'lines': [10852, 10874],
      'meaning': 'getUnknownSpells queries path0,class1,class2 rather than joining Paths. Path99 is outside ordinary 1..4 trainer selection; exact callers and exceptional class99 require review.'},
    'not_claimed': ['All115 path99 meanings resolved', 'No dangling source edges', 'Korean original skill availability', 'Reference/runtime execution']}
dst = a.private_output / 'grant_routes.json'
dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'output': str(dst), 'sites': len(routes), 'spells': len({r['record_id'] for r in routes}), 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()}))
