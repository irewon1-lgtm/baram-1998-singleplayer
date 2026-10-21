"""Extend the verified complete r26 source archive with current r27 sources and actual evidence."""
import hashlib,json,os,shutil,zipfile
from pathlib import Path
r=Path(__file__).resolve().parents[2];out=r.parents[1]/'deliverables';prefix='source/'+r.name+'/'
build=json.loads((r/'android/evidence/build-r27-001/BUILD_RECEIPT.json').read_text())
inputs=json.loads((r/'android/evidence/build-r27-001/SOURCE_INPUTS.json').read_text())
baseline=out/'Project1998-r26-source-tests.zip';target=out/'Project1998-r27-source-tests.zip'
assert not target.exists(),'Preserve already qualified delivery archives'
excluded={'.git','.godot','obj','bin','__pycache__','state','profiles','project','test-only-project','data','restored','closed-ui-source'}
bad={'.keystore','.jks','.pfx','.p12','.pem','.key','.db','.sqlite','.sqlite3','.idsig','.dll','.pdb','.nupkg'}
def safe(name):
    p=Path(name)
    return p.suffix.lower() not in bad and p.name!='signing-password' and not p.name.endswith(('-wal','-shm')) and not any(x in excluded or x.startswith(('private-','content-')) for x in p.parts[:-1])
updates={}
for name,digest in inputs.items():
    relative=name.removeprefix(r.name+'/');path=r/relative
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    assert safe(relative),name
    updates['source/'+name]=path
for folder in ['verification/r27','r27-report','evidence/r27','evidence/r25/suite/r27-final001','evidence/r25/final-runtime','evidence/r25/items-ui/r27-final001','evidence/r25/crash/r27-final001','evidence/r24/console-r27-final001','android/evidence/build-r27-001']:
    base=r/folder
    for parent,dirs,names in os.walk(base):
        dirs[:]=[d for d in dirs if d not in excluded and not d.startswith(('content-','private-'))]
        for n in names:
            f=Path(parent)/n;rel=f.relative_to(r).as_posix()
            if folder=='evidence/r25/final-runtime' and not f.relative_to(base).parts[0].startswith('r27-final001-'):continue
            if safe(rel) and f.is_file() and not f.is_symlink() and (f.suffix in ['.json','.jsonl','.log','.txt','.md','.csv','.trx','.cs','.py','.html','.patch'] or folder.startswith(('verification/','r27-report/')) or (f.suffix=='.png' and '/ui/final002/' in rel)):
                updates[prefix+rel]=f
for folder in ['candidate/Tests','candidate/Server','Host','android']:
    # New product files and unit tests, excluding generated build outputs and archives.
    for f in (r/folder).rglob('*'):
        if f.is_file() and not f.is_symlink() and safe(f.relative_to(r).as_posix()) and f.suffix in ['.cs','.py','.csproj','.cfg','.godot']:
            updates[prefix+f.relative_to(r).as_posix()]=f
updates[prefix+'README-r27.txt']=r/'README-r27.txt'
manifest={};seen=set()
with zipfile.ZipFile(baseline) as source,zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as sink:
    for info in source.infolist():
        name=info.filename
        if not name.startswith(prefix) or info.is_dir():continue
        rel=name[len(prefix):]
        if not safe(rel):continue
        local=updates.pop(name,None) or (r/rel if (r/rel).is_file() and not (r/rel).is_symlink() else None)
        data=local.read_bytes() if local else source.read(name)
        sink.writestr(name,data);seen.add(name);manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    for name,path in sorted(updates.items()):
        if name in seen:continue
        data=path.read_bytes();sink.writestr(name,data);seen.add(name);manifest[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    sink.writestr('README-source-tests.txt','Project1998 r27 full source/tests. Active STATE: '+prefix+'verification/r27/STATE.json\nNew item acceptance 21 PASS, new safety cases 11 PASS, existing item UI 676 PASS; 66 inherited xUnit FAILs remain. Physical Android NOT_RUN. Private keys and save databases excluded. Read '+prefix+'README-r27.txt\n')
    sink.writestr('SOURCE-FILE-MANIFEST.json',json.dumps({'schema':'P1998_R27_COMPLETE_SOURCE_1','apk_sha256':build['sha256'],'files':manifest},ensure_ascii=False,indent=2))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    names=set(z.namelist())
    mismatches=[]
    for name,expected in inputs.items():
        entry='source/'+name
        if entry not in names or hashlib.sha256(z.read(entry)).hexdigest()!=expected:mismatches.append(name)
    assert not mismatches,mismatches
    assert len(z.namelist())==len(set(z.namelist()))
receipt={'status':'PASS_CRC_PRIVATE_FILE_EXCLUSION_AND_ALL_FROZEN_APK_SOURCE_INPUTS','entries':len(manifest),'apk_frozen_inputs_matching':len(inputs),'missing_or_mismatched_inputs':mismatches,
    'archive':target.name,'bytes':target.stat().st_size,'sha256':hashlib.file_digest(target.open('rb'),'sha256').hexdigest()}
(r/'evidence/r27/DELIVERY-ARCHIVE.json').write_text(json.dumps(receipt,indent=2));(out/'r27-DELIVERY-ARCHIVE.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
