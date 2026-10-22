"""Retain the complete historical ledger and supersede only ten newly executed rows."""
import csv,hashlib,io,json,zipfile
from collections import Counter
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R.parents[1];O=W/'deliverables';O.mkdir(exist_ok=True)
base=W/'ledger-input/Project1998-r28-world-ledger.zip'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='8af212052fa8a58b29db408478614b35ffabb943035da2f6b55a0f4d94d794dd'
def raw(p):return (R/p).read_bytes()
def data(p):return json.loads(raw(p))
def j(x):return json.dumps(x,ensure_ascii=False,indent=2).encode()
def csvbytes(rows):
 s=io.StringIO();keys=list(dict.fromkeys(k for row in rows for k in row));w=csv.DictWriter(s,fieldnames=keys);w.writeheader()
 for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(dict,list))else v for k,v in row.items()})
 return s.getvalue().encode('utf-8-sig')
new=[json.loads(l)for l in raw('evidence/r24/runtime/r29-map1014-final001/warp-execution.jsonl').decode().splitlines()]
assert len(new)==10 and all(x['status']=='PASS_SCOPED_HOST_COMPLETE_ROUNDTRIP_WITH_OUTSIDE_MOVE'for x in new)
lookup={(x['source_map'],x['x'],x['y']):x for x in new}
with zipfile.ZipFile(base)as z:
 maps=json.loads(z.read('world-ledger/maps.json'));warps=json.loads(z.read('world-ledger/warps.json'));oldsummary=json.loads(z.read('world-ledger/SUMMARY.json'));oldcount=Counter(x.get('roundtrip')for x in warps)
 for row in warps:
  k=(row['map'],row['x'],row['y']);row['execution_version']='HISTORICAL_R26_R28_RETAINED_NOT_NEW_APK_EXECUTION'
  if k in lookup:
   row['host_execution']=lookup[k];row['roundtrip']=lookup[k]['status'];row['execution_version']='R29_FINAL_SOURCE_SCOPED_HOST_20261022';row['unresolved']='Physical Android, user-save dynamic doors and full negative-condition matrix NOT_RUN.'
 for row in maps:
  row['r29_scope']='Inherited historical record; no new whole-map PASS'
  if row['id']==1014:
   row['r29_scope']='Two visible-fence passflag overrides reconstructed; all4 outgoing and6 incoming original road/interior/return paths re-executed. Actual user-save/device NOT_RUN.'
   row['r29_repairs']=[[0,16,0,3],[1,16,0,3]]
   for key in ['cells_reaching_an_exit','arrivals_without_static_exit']:row[key]=None
   row['r29_static_counts']='Historical map1014 collision counts superseded; no new full directional-cell census claimed.'
 summary={'schema':'P1998_R29_WORLD_LEDGER_1','registered_maps':len(maps),'effective_entrances':len(warps),'r29_changed_maps':1,'r29_changed_cells':2,'r29_reexecuted_entrances':len(new),'r29_complete_roundtrips':10,'r29_entrance_failures':0,'r29_entrance_reviews':0,'inherited_entrance_rows':len(warps)-len(new),'historical_status_counts':dict(oldcount),'current_mixed_version_status_counts':dict(Counter(x.get('roundtrip')for x in warps)),'all_world_new_execution':'NOT_RUN; historical per-entry evidence explicitly retained','whole_world_or_map_progression_pass':False,'negative_condition_matrix':'NOT_RUN','user_save_dynamic_doors':'NOT_RUN','physical_android':'NOT_RUN','baseline_archive_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'historical_summary':oldsummary}
 assert len(maps)==7948 and len(warps)==10533
 target=O/'Project1998-r29-world-ledger.zip'
 additions={'r29-current/SUMMARY.json':j(summary),'r29-current/maps.json':j(maps),'r29-current/maps.csv':csvbytes(maps),'r29-current/warps.json':j(warps),'r29-current/warps.csv':csvbytes(warps),'r29-current/map1014-warp-execution.jsonl':raw('evidence/r24/runtime/r29-map1014-final001/warp-execution.jsonl'),'r29-current/map1014-RESULT.json':raw('evidence/r24/runtime/r29-map1014-final001/RESULT.json'),'r29-current/recovery-checks.json':raw('evidence/r24/runtime/r29-recovery-green003/RESULT.json'),'r29-current/diagnosis.json':raw('evidence/r29/EMERGENCY-DIAGNOSIS.json'),'r29-current/preservation.json':raw('evidence/r29/PRESERVATION.json'),'r29-current/map1014-original-art.png':raw('evidence/r29/sonhi-valley-original.png')}
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as dest:
  for info in z.infolist():dest.writestr(info,z.read(info.filename))
  for n,b in additions.items():dest.writestr(n,b)
  dest.writestr('README-r29.txt','전체7948지도/10533출입구 원장입니다. r29-current를 먼저 읽으세요. 과거 원장은 원문 그대로 보존했습니다. 신규: 지도1014 보이는 울타리2칸 수정, 연결10개 일반길→입장→내부이동→귀환→바깥이동 검사 PASS. 나머지10523출입구는 과거 실행 근거이며 새 APK 실행 PASS가 아닙니다. 전체 미해결 검토/조건행렬/실기기 NOT_RUN은 유지합니다. totogo 실제 기기 복구는 APK 설치 후 조건 일치 시 수행되며 이 원장의 복구17PASS는 별도 시험 저장입니다.\n')
with zipfile.ZipFile(target)as z:assert z.testzip()is None and len(z.namelist())==len(set(z.namelist()))
(R/'evidence/r29/WORLD-LEDGER.json').write_bytes(j(summary));print(json.dumps({'path':str(target),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'new_roundtrips':10,'maps':len(maps),'entrances':len(warps)}))
