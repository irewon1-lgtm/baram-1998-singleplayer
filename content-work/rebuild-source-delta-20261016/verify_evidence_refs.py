"""Independent reference checks for Work batches against fixed read-only P1.5."""
import argparse,csv,hashlib,json
from pathlib import Path

def canonical(r):
    return hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def verify(root, baseline, content):
    root,baseline,content=map(Path,(root,baseline,content))
    errors=[];checks=0
    def check(ok,msg):
        nonlocal checks
        checks+=1
        if not ok:errors.append(msg)
    m=json.loads((root/'MANIFEST.json').read_text())
    raw=(baseline/'INPUT_MANIFEST.json').read_bytes()
    check(hashlib.sha256(raw).hexdigest()==m['input_manifest_sha256'],'baseline manifest fingerprint')
    bindings={json.loads(l)['binding_id'] for l in (baseline/'field_bindings.jsonl').read_text().splitlines()}
    requirements={r['requirement_id'] for r in csv.DictReader((baseline/'requirements_delta.csv').open(encoding='utf-8-sig'))}
    cs=[json.loads(l) for l in (root/'FIELD_CANDIDATES.jsonl').read_text().splitlines() if l.strip()]
    needed={x for r in cs for x in r.get('existing_record_ids',r.get('content_ids',[]))}
    known={}
    catalog=json.loads((baseline/'selected_content/catalog.json').read_text())['normalized_catalogs']
    for f in catalog:
        p=content/Path(f['path']).name
        if p.suffix!='.jsonl':continue
        b=p.read_bytes()
        check(hashlib.sha256(b).hexdigest()==f['sha256'],'read-only normalized fingerprint '+p.name)
        for line in b.decode().splitlines():
            r=json.loads(line);i=r.get('record_id',r.get('id',r.get('content_id')))
            if i in needed:known[i]=r
    parsed={}
    for r in cs:
        i=r['candidate_id']
        check(bool(r.get('binding_ids')) and set(r['binding_ids'])<=bindings,'binding '+i)
        check(bool(r.get('requirement_ids')) and set(r['requirement_ids'])<=requirements,'requirement '+i)
        for ref in r.get('existing_record_ids',r.get('content_ids',[])):
            check(ref in known,'baseline record '+i+':'+ref)
        refs=[]
        loc=r.get('source_locator',{})
        if isinstance(loc,dict) and isinstance(loc.get('private_file'),dict):
            p=loc['private_file'];refs.append((p['relative_private_path'],p.get('sha256'),p.get('bytes'),loc.get('records',[loc['record_id']] if 'record_id' in loc else []),None))
        if isinstance(r.get('private_value'),dict):
            p=r['private_value'];refs.append((p['path'],None,None,[p['candidate_id']],p.get('record_canonical_sha256')))
        if r.get('private_record_locator'):
            path,record=r['private_record_locator'].split('#',1);refs.append((path,r.get('private_semantic_file_sha256'),None,[record],None))
        for ref in r.get('evidence_refs',[]):
            refs.append((ref['path'],ref.get('sha256'),ref.get('bytes'),ref.get('record_ids',[]),None))
        for path,sha,size,records,record_sha in refs:
            p=root/path;check(p.is_file() and not p.is_symlink(),'private file '+i+':'+path)
            if not p.is_file() or p.is_symlink():continue
            b=p.read_bytes()
            if sha:check(hashlib.sha256(b).hexdigest()==sha,'private SHA '+i+':'+path)
            if size is not None:check(len(b)==size,'private length '+i+':'+path)
            if records:
                if path not in parsed:
                    d=[json.loads(l) for l in b.decode().splitlines() if l.strip()] if p.suffix=='.jsonl' else json.loads(b)
                    rows=d.get('records',[]) if isinstance(d,dict) else d
                    parsed[path]={x.get('candidate_id',x.get('record_id',x.get('id'))):x for x in rows if isinstance(x,dict)}
                for rid in records:
                    check(rid in parsed[path],'private record '+i+':'+str(rid))
                    if record_sha and rid in parsed[path]:check(canonical(parsed[path][rid])==record_sha,'private record SHA '+i+':'+rid)
        check(bool(r.get('codex_tests')),'observation '+i)
    return {'schema':'baram.work.evidence_ref_validation/1','result':'FAIL' if errors else 'PASS','checks':checks,'candidates':len(cs),'baseline_ids_requested':len(needed),'baseline_ids_found':len(known),'errors':errors,'scope':'Fixed P1.5 manifest and actual binding/requirement/normalized IDs; declared private file/hash/length/record references','runtime':'NOT_RUN','Codex_G0_P2':'NOT_RUN'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--baseline',required=True);p.add_argument('--content',required=True);p.add_argument('--output');a=p.parse_args()
    r=verify(a.root,a.baseline,a.content);s=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
    if a.output:Path(a.output).write_text(s)
    print(s,end='');raise SystemExit(0 if r['result']=='PASS' else 1)
