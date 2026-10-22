"""Extend full delivered r29 source/tests with final r30 APK inputs and executed evidence."""
import hashlib,json,os,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R.parents[1];OUT=W/'deliverables';PREFIX='source/'+R.name+'/'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
build=json.loads((R/'android/evidence/build-r30-001/BUILD_RECEIPT.json').read_text())
inputs=json.loads((R/'android/evidence/build-r30-001/SOURCE_INPUTS.json').read_text())
baseline=W/'deliverables/Project1998-r29-source-tests.zip';target=OUT/'Project1998-r30-source-tests.zip'
assert build['status']=='BUILD_PASS'
excluded={'.git','.godot','obj','bin','__pycache__','state','profiles','project','test-only-project','data','restored','closed-ui-source','detached-test-credentials'}
bad={'.keystore','.jks','.pfx','.p12','.pem','.key','.db','.sqlite','.sqlite3','.idsig','.dll','.pdb','.nupkg','.apk'}
def safe(name):
    p=Path(name)
    return p.suffix.lower() not in bad and p.name!='signing-password' and not p.name.endswith(('-wal','-shm')) and not any(x in excluded or x.startswith(('private-','content-')) for x in p.parts[:-1])
updates={}
updates[PREFIX+'candidate/Tests/packages.lock.json']=R/'candidate/Tests/packages.lock.json'
for name,digest in inputs.items():
    rel=name.removeprefix(R.name+'/');p=R/rel
    assert safe(rel) and p.is_file() and sha(p)==digest,name
    updates['source/'+name]=p
folders=['verification/r30','r30-report','evidence/r30','evidence/r27/ui/r30-preserved001','evidence/r29/ui/r30-preserved001','evidence/r25/suite/r30-final001','evidence/r25/fixtures/r30-final001','evidence/r25/items-ui/r30-final001','evidence/r25/crash/r30-final001','evidence/r24/console-r30-final001','android/evidence/build-r30-001']
folders += ['evidence/r25/visual/r30-emergency-final001','evidence/r25/suite/r30-final002','evidence/r25/fixtures/r30-final002','evidence/r25/items-ui/r30-final002','evidence/r25/crash/r30-final002','evidence/r24/console-r30-final002']
folders += [str(p.relative_to(R)) for p in (R/'evidence/r24/runtime').glob('r30-*') if p.is_dir()]
folders += [str(p.relative_to(R)) for p in (R/'evidence/r25/final-runtime').glob('r30-final00*-*') if p.is_dir()]
folders += [str(p.relative_to(R)) for p in (R/'evidence/r25/visual').glob('r30-final00*-*') if p.is_dir()]
for folder in folders:
    for parent,dirs,names in os.walk(R/folder):
        dirs[:]=[x for x in dirs if x not in excluded and not x.startswith(('private-','content-'))]
        for name in names:
            p=Path(parent)/name;rel=p.relative_to(R).as_posix()
            if p.is_symlink() or not safe(rel):continue
            if p.suffix in {'.json','.jsonl','.log','.txt','.md','.csv','.trx','.cs','.py','.html','.patch'} or folder.startswith(('verification/','r30-report')) or (p.suffix=='.png' and ('/ui/final002/' in rel or '/ui/final004/' in rel)):updates[PREFIX+rel]=p
for folder in ['candidate/Tests','candidate/Server','Host','android','verification']:
    for parent,dirs,names in os.walk(R/folder):
        dirs[:]=[x for x in dirs if x not in excluded and not x.startswith(('private-','content-'))]
        for name in names:
            p=Path(parent)/name;rel=p.relative_to(R).as_posix()
            if p.is_file() and not p.is_symlink() and safe(rel) and (p.suffix in {'.cs','.py','.csproj','.cfg','.godot'} or name.endswith('.cs.uid')):updates[PREFIX+rel]=p
updates[PREFIX+'README-r30.txt']=R/'README-r30.txt'
updates[PREFIX+'verification/r29/STATE.json']=R/'verification/r29/STATE.json'
manifest={};seen=set()
with zipfile.ZipFile(baseline) as src,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as dst:
    for info in src.infolist():
        name=info.filename
        if not name.startswith(PREFIX) or info.is_dir():continue
        rel=name[len(PREFIX):]
        if not safe(rel):continue
        p=updates.pop(name,None) or (R/rel if (R/rel).is_file() and not (R/rel).is_symlink() else None)
        data=p.read_bytes() if p else src.read(name)
        dst.writestr(name,data);seen.add(name);manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    for name,p in sorted(updates.items()):
        if name in seen:continue
        data=p.read_bytes();dst.writestr(name,data);seen.add(name);manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    dst.writestr('README-source-tests.txt','Project1998 r30 COMPLETE source and executed tests. Active STATE: '+PREFIX+'verification/r30/STATE.json\nOriginal delivered r29 source retained with r30 final changes. New mixed-catalog recovery/backup/refusal15 and actual Godot selection/recovery/tap/reopen8 PASS; original recovery17 and backup6 PASS. Full2093/2027PASS/66 unchanged FAIL;new0. Prior r29 UI and content evidence retained with original scope. Physical Android NOT_RUN. Keys/passwords/save databases excluded. Read README-r30.txt and r30-report.\n')
    dst.writestr('SOURCE-FILE-MANIFEST.json',json.dumps({'schema':'P1998_R30_COMPLETE_SOURCE_1','apk_sha256':build['sha256'],'files':manifest},ensure_ascii=False,indent=2))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    names=set(z.namelist());mismatch=[]
    for name,expected in inputs.items():
        entry='source/'+name
        if entry not in names or hashlib.sha256(z.read(entry)).hexdigest()!=expected:mismatch.append(name)
    assert not mismatch,mismatch
    assert len(z.namelist())==len(names)
    assert all(safe(n) for n in names)
    assert sum('/candidate/game-data/' in n for n in names)==8056
receipt={'status':'PASS_CRC_NO_DUPLICATES_PRIVATE_FILE_EXCLUSION_ALL_FROZEN_APK_INPUTS','archive':target.name,'entries':len(manifest),'apk_frozen_inputs_matching':len(inputs),'missing_or_mismatched_inputs':mismatch,'game_data_files':8056,'bytes':target.stat().st_size,'sha256':sha(target)}
(R/'evidence/r30/DELIVERY-ARCHIVE.json').write_text(json.dumps(receipt,indent=2)+'\n')
(OUT/'r30-DELIVERY-ARCHIVE.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
