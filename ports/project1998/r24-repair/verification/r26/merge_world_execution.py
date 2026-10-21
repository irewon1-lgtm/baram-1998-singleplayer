"""Join each effective entrance to executed final-handler evidence; never promote visual/condition coverage."""
import argparse,collections,csv,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--ledger',type=Path,required=True);p.add_argument('--execution',type=Path,required=True);a=p.parse_args()
root=a.ledger;maps=json.loads((root/'maps.json').read_text());warps=json.loads((root/'warps.json').read_text())
executed={}
for line in a.execution.read_text().splitlines():
 row=json.loads(line);key=(row['source_map'],row['x'],row['y']);assert key not in executed;executed[key]=row
assert len(executed)==len(warps)==10533
for row in warps:
 key=(row['map'],row['x'],row['y']);test=executed[key]
 assert (row['destination'],row['dx'],row['dy'])==(test['destination_map'],test['dx'],test['dy'])
 row['structural_status']=row.get('structural_status',row['status']);row['host_execution']=test
 row['roundtrip']=test['status'];row['status']='PARTIAL_HOST_ROUNDTRIP_VERIFIED'if test['status'].startswith('PASS_')else test['status']
 row['condition_execution']='ORIGINAL_GATES_ENFORCED_SYNTHETIC_PREREQUISITES; NEGATIVE_MATRIX_NOT_RUN'
 row['unresolved']='Visual entrance matching, every condition state and user-save dynamic-door state NOT_RUN.'
 if not test['status'].startswith('PASS_'):row['unresolved']+=' '+test['detail']+' Interior/return/outside sequence needs individual review.'
 if key[0]==330 and key[1]in(110,111)and key[2]==133:
  row['facade_provenance']='R26_LOCAL_RECONSTRUCTION_FROM_RETAINED_BUYA_SMITH_FACADE; original missing Kan image not recovered; warp coordinates unchanged'
by_map=collections.defaultdict(list)
for row in warps:by_map[row['map']].append(row)
for row in maps:
 tests=by_map[row['id']];passed=sum(w['roundtrip'].startswith('PASS_')for w in tests)
 row['host_warp_rows_exercised']=len(tests);row['host_complete_roundtrips']=passed;row['host_entrance_reviews_or_exclusions']=len(tests)-passed
 row['roundtrip']='SCOPED_HOST_ALL_OUTGOING_ROWS_COMPLETE'if tests and passed==len(tests)else'PARTIAL_OR_REVIEW_HOST'
 row['status']='PARTIAL_STRUCTURAL_RENDER_AND_HOST_EVIDENCE; VISUAL_CONDITIONS_NOT_ALL_VERIFIED'
 if row['id']==330:row['r26_facade']='38 authored cells locally reconstructed from retained same-city source art, not exact original Kan restoration'
def write(name,rows):
 (root/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
 keys=list(dict.fromkeys(k for row in rows for k in row))
 with(root/(name+'.csv')).open('w',encoding='utf-8-sig',newline='')as f:
  writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(list,dict))else v for k,v in row.items()}for row in rows)
write('maps',maps);write('warps',warps)
summary=json.loads((root/'SUMMARY.json').read_text());totals=collections.Counter(r['status']for r in executed.values())
summary.update(host_warp_rows_exercised=len(executed),host_complete_roundtrips=sum(v for k,v in totals.items()if k.startswith('PASS_')),
 host_reviews_or_exclusions=sum(v for k,v in totals.items()if not k.startswith('PASS_')),host_status_counts=dict(totals),
 maps_with_outgoing_host_rows=sum(bool(by_map[m['id']])for m in maps),maps_with_all_outgoing_host_roundtrips=sum(bool(by_map[m['id']])and all(w['roundtrip'].startswith('PASS_')for w in by_map[m['id']])for m in maps),
 all_warp_actual_roundtrip='ALL_ROWS_EXERCISED_WITH_PER_ENTRY_REVIEW; NOT_ALL_PASS',full_map_progression_pass=0,
 physical_android='NOT_RUN',conditions_negative_matrix='NOT_RUN',human_whole_map_review=0,
 execution_source=str(a.execution),facade_modified_maps=1,facade_authored_cells=38,
 scope='Original Session, synthetic prerequisites/accelerated clock and real SQLite. Each entrance is retained separately. Static and contact render are not human visual correctness. No whole map/game PASS implied.')
(root/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
page=root/'map-ledger.html';text=page.read_text();start=text.index('const maps=');end=text.index(';let visible=maps;',start)
text=text[:start]+'const maps='+json.dumps(maps,ensure_ascii=False).replace('</','<\\/')+',warps='+json.dumps(warps,ensure_ascii=False).replace('</','<\\/')+text[end:]
text=text.replace('실제 Godot 실행·전체 수동 검수·각 문 왕복 PASS가 아닙니다.','각 문 원래 처리기의 호스트 실행 결과를 포함합니다. 실기기·전체 수동 검수·조건별 PASS를 뜻하지 않습니다.')
page.write_text(text);print(json.dumps(summary,ensure_ascii=False,indent=2))
