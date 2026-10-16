"""Read-only final-package audit; no source programs or SQL execution."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=Path('/workspace/scratch/3624c67f59e8')
BATCH=ROOT/'batch_staging/B002'
PACKAGE=Path('/workspace/scratch/68a0f3ea5a03/receiver/package')


def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def main():
    checks=0;errors=[]
    def check(ok,label):
        nonlocal checks
        checks+=1
        if not ok:errors.append(label)
    manifest=json.loads((BATCH/'MANIFEST.json').read_text())
    expected={r['path'] for r in manifest['files']}|{'MANIFEST.json','VALIDATION.json'}
    actual={r.relative_to(BATCH).as_posix() for r in BATCH.rglob('*') if r.is_file()}
    check(expected==actual,'exact expected file set')
    check(len(manifest['files'])==28 and len(actual)==30,'nonempty expected file counts')
    excluded=[];markers=[]
    patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{20,}',rb'sk-proj-[A-Za-z0-9_-]{20,}',rb'X-Amz-Signature=[A-Za-z0-9]+',rb'completion_token[\"\s:]+[A-Za-z0-9_-]{16,}']
    for name in actual:
        rel=PurePosixPath(name);p=BATCH/name
        check(not rel.is_absolute() and '..' not in rel.parts and not p.is_symlink(),'safe regular path '+name)
        b=p.read_bytes()
        if p.suffix.lower() in {'.exe','.dll','.sql','.bak','.ttf','.otf','.pfx','.jks','.keystore'} or any(x in name.lower().split('/') for x in ['.git','__pycache__','private-intake']):excluded.append(name)
        if any(re.search(pattern,b) for pattern in patterns):markers.append(name)
        if p.suffix=='.json':json.loads(b)
        elif p.suffix=='.jsonl':rows(p)
    for spec in manifest['files']:
        b=(BATCH/spec['path']).read_bytes();check(len(b)==spec['bytes'] and sha(b)==spec['sha256'],'payload size/hash '+spec['path'])
    check(not excluded,'excluded original/executable/font/key file types')
    check(not markers,'strong credential markers')
    candidates=rows(BATCH/'FIELD_CANDIDATES.jsonl')
    check(len(candidates)==154 and len({r['candidate_id'] for r in candidates})==154,'candidate unique set154')
    check({r['candidate_id'] for r in candidates}==set(manifest['candidate_ids']),'candidate manifest agreement')
    for r in candidates:
        check(r.get('selected_for_build') is False,'unapproved adoption '+r['candidate_id'])
        check(bool(r.get('codex_tests')),'unobserved test task missing '+r['candidate_id'])
    new_sources=[s for s in rows(BATCH/'SOURCES.jsonl') if s.get('acquisition_class')=='NEW_SOURCE_BYTES']
    check(len(new_sources)==13,'13 new-original byte sources, not15 derived payload files')
    for s in new_sources:
        b=(BATCH/s['private_payload_path']).read_bytes();check(sha(b)==s['sha256'] and len(b)==s['bytes'],'new-original actual bytes '+s['source_id'])
    # Match copied excerpts against the original P1.5 source bytes and exact lines.
    source_index={s['source_id']:s for s in json.loads((PACKAGE/'PRIVATE_SOURCE_INDEX.json').read_text())}
    for e in rows(BATCH/'archives_ui/payload/existing_source_excerpt.jsonl'):
        spec=source_index[e['source_id']];b=(PACKAGE/spec['path']).read_bytes()
        check(sha(b)==e['source_sha256'],'excerpt parent source SHA '+e['source_id'])
        lines=b.decode('cp949').splitlines()[e['line_start']-1:e['line_end']]
        check(lines==e['raw_html_lines'],'exact original excerpt source lines '+e['source_id']+':'+str(e['line_start']))
    texts={}
    for s in new_sources:
        path=BATCH/s['private_payload_path']
        if path.suffix=='.html':
            parser=Text();parser.feed(path.read_text());texts[s['source_id']]=' '.join(parser.parts)
    ui=[r for r in candidates if r['candidate_id'].startswith('SD-')]
    check(len(ui)==10,'10 archive/UI candidates')
    for r in ui:
        for e in r['source_evidence']:
            if e.get('text_anchor'):
                check(e['text_anchor'] in texts[e['source_id']],'primary transcript/caption anchor '+r['candidate_id'])
    # Check numeric source catalog claims without treating bibliography as book acquisition.
    for name,pages in [('SD-SRC-BOOK-NL23946242','431'),('SD-SRC-BOOK-NL25737613','447')]:
        isbn_text=re.sub(r'[-\s]','',texts[name])
        check('8985966286' in isbn_text or '9788985966283' in isbn_text,'catalog ISBN '+name)
        check(pages in texts[name],'catalog page count '+name)
    for r in ui:
        check(r['historical_profile_adoption']=='UNRESOLVED' and r['runtime_test_status']=='NOT_RUN','archive historical/runtime separation '+r['candidate_id'])
    staged=rows(BATCH/'gameplay_economy/field_candidates.private.jsonl')
    old={r['candidate_id']:r for r in rows(ROOT/'private_delta/gameplay_economy/field_candidates.private.jsonl')}
    changed={}
    for r in staged:
        prior=old[r['candidate_id']];keys={k for k in set(r)|set(prior) if r.get(k)!=prior.get(k)}
        if keys:changed[r['candidate_id']]=sorted(keys)
        check(keys <= {'requirement_ids'},'economy semantic data unchanged after earlier audit '+r['candidate_id'])
    z=ROOT/'delivery/BARAM_WORK_SOURCE_DELTA_B002_20261016.zip'
    with zipfile.ZipFile(z) as f:
        names={x.filename for x in f.infolist() if not x.is_dir()}
        check(len(names)==len(f.infolist()) and names==actual,'zip exact nonduplicate file set')
        check(f.testzip() is None,'zip CRC')
        for name in names:check(f.read(name)==(BATCH/name).read_bytes(),'zip exact actual bytes '+name)
    result={'schema':'baram.work_delta.b002_independent_ai_audit/1','result':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,'candidate_records':len(candidates),'payload_files':len(manifest['files']),'total_files':len(actual),'zip_sha256':sha(z.read_bytes()),'zip_bytes':z.stat().st_size,'new_original_byte_sources':len(new_sources),'archives_ui_payload_files':len(list((BATCH/'archives_ui/payload').glob('*'))),'archives_ui_candidates':len(ui),'economy_post_audit_changes':changed,'excluded_file_findings':excluded,'strong_secret_marker_files':markers,'visual_review':['Actually opened press_login2001.jpg and all4 newly acquired official GIFs. Press menu visibly 접속하기/이어하기/암호변경/배경이야기/만든사람들/종료.','Thumbnail dimensions do not establish original game resolution; old setup/article publication dates do not establish executable build.'],'scope':'Final staging/ZIP exact bytes, all listed file SHA/length, required candidate counts, new-source bytes, exact old-source excerpt lines, source anchors/bibliography, excluded filename/strong secret patterns; no malware/game/historical completeness certification','runtime':'NOT_RUN','Codex_G0_P2':'NOT_RUN','receipt':'UNACKNOWLEDGED'}
    (HERE/'B002_INDEPENDENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
