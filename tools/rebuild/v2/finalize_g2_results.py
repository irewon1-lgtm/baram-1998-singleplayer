#!/usr/bin/env python3
"""Produce G2 result artifacts from actual evidence, retaining all open gates."""
import argparse,base64,csv,datetime,hashlib,html,json,shutil,zipfile
from collections import Counter
from pathlib import Path

SOURCE='0627c774927d92b68936ffd3323129fa268967dd'
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);a=p.parse_args();root=a.workspace.resolve();repo=root/'baram';ev=root/'evidence';out=root/'deliverables';rt=root/'private/g2-delivery';docs=repo/'docs/rebuild/v2'
 d=read(rt/'gameplay_content.json');usage=read(rt/'G2_WORLD_USAGE.json');semantic=read(rt/'G2_MONSTER_SEMANTICS.json');pack=read(ev/'G2_PACKAGED_ARTIFACTS.json');osrun=read(ev/'g2-delivery-ordinary30/OS_PLAYABILITY.json');analysis=read(ev/'g2-delivery-ordinary30/FINAL_ANALYSIS.json')
 assert pack['source_commit']==SOURCE and not osrun.get('error')
 freeze=read(ev/'G2_DELIVERY_FREEZE.json');assert freeze['source_commit']==SOURCE
 assert all(sha(repo/'rebuild/p2'/name)==digest for name,digest in freeze['source_snapshot'].items()),'App source changed after the freeze'
 stress=next(c for c in osrun['checks']if c['id']=='continuous_requested_stress_duration');assert stress['status']=='PASS'and stress['details']['stress_seconds']>=1800
 closure=read(ev/'g2-closure-delivery.json');actions=read(ev/'g2-actions-delivery.json');quests=read(ev/'g2-quests-final.json');natural=read(ev/'g2-natural-delivery.json');storage=read(ev/'g2-storage-delivery.json');roles=read(ev/'g2-roles-delivery.json');gui=read(ev/'g2-delivery-pack-ui-labels/GUI.json');cold=read(ev/'g2-delivery-cold/OS_PLAYABILITY.json');parity=read(ev/'g2-delivery-parity-expanded.json')
 assert all(r.get('failures',0)==0 for r in(closure,actions,quests,natural,storage,roles,gui,parity))
 counts={k:len(d[k])for k in('maps','items','monsters','skills','npcs','quests','recipes')};assert counts=={'maps':111,'items':1105,'monsters':644,'skills':262,'npcs':84,'quests':160,'recipes':73}and semantic['meaningful_signatures']==513
 assert quests['quests_completed']==160 and quests['recipes_crafted']==73
 assert closure['counts']=={'items_executed':1105,'maps_reached_by_exits':111,'monsters_fought':644,'npcs_accessed':84}
 source_object_inputs=sum(p['source_objects']for s in usage['source_chunks']for p in s['placements'])
 placed_source_objects=sum(1 for m in d['maps'].values()for o in read(rt/m['geometry_file']).get('objects',[])if o.get('placement_fact_status')=='SOURCE_RELATIVE_COORDINATES_PRESERVED')
 write(ev/'G2_SOURCE_OBJECT_AUDIT.json',{'source_object_records_in_adopted_chunks':source_object_inputs,'placed_with_source_relative_coordinates':placed_source_objects,'outside_64cell_anchor_records_skipped':source_object_inputs-placed_source_objects,'policy':'Native import retains anchors within the decoded64x64 chunk. Out-of-chunk anchors are excluded, not counted as placed; boundary art remains a tuning limit.'})
 source_cell_summary=f'지형/충돌158,401셀 보존 · 개구부/접합422셀 변경 · 원본 물체{placed_source_objects:,}개 배치 · 경계 밖 앵커{source_object_inputs-placed_source_objects}개 미배치'
 specs=[('구조·충돌·성장 그래프','g2-static-delivery.json','EXECUTED'),('모든 ID 명령','g2-closure-delivery.json','EXECUTED'),('기술·게임 행동','g2-actions-delivery.json','EXECUTED'),('추가 전투 역할 AI·저장','g2-roles-delivery.json','EXECUTED'),('저장·이전·중단·길찾기','g2-storage-delivery.json','EXECUTED'),('새 캐릭터 4직업 초반 성장','g2-natural-delivery.json','EXECUTED'),('의뢰160·제작73','g2-quests-final.json','REUSED_EXACT_DEFINITIONS_G2_REUSE_IMPACT'),('최종 PCK 화면','g2-delivery-pack-ui-labels/GUI.json','EXECUTED'),('APK/PCK 자료 일치','g2-delivery-parity-expanded.json','EXECUTED'),('최종 PCK 새 프로세스 이어하기','g2-delivery-cold/OS_PLAYABILITY.json','EXECUTED'),('연속1800초 일반 입력','g2-delivery-ordinary30/OS_PLAYABILITY.json','EXECUTED')]
 tests=[]
 for title,path,use in specs:
  file=ev/path;r=read(file);checks=r.get('checks',[]);tests.append({'name':title,'path':path,'sha256':sha(file),'status':r['status'],'checks':len(checks)if isinstance(checks,list)else checks,'failures':r.get('failures'),'use':use,'scope':r.get('scope')})
 cold_metrics={n:read(ev/'g2-delivery-cold'/n/'FINAL_ANALYSIS.json')for n in('first-process','restart-process')}
 performance={'long':{k:analysis.get(k)for k in('status','engine_wall_frame_interval','engine_input_to_frame_post_draw','save_duration','target_assessment','OS_received_to_frame_post_draw')},'cold':{n:{k:r.get(k)for k in('engine_wall_frame_interval','save_duration','target_assessment')}for n,r in cold_metrics.items()},'full_world_fixture':storage['timings'],'overall':'FAIL_NUMERIC_TARGETS_NOT_WAIVED','scope':'Untrimmed Linux software-rendered engine frame, receipt-to-post-draw and save measurements. Not native/physical display/input latency. Independent clocks stay separate.'}
 remaining={'Windows_native':'NOT_RUN','Android_native_install_update_save_retention':'NOT_RUN','Galaxy':'NOT_RUN','OS_Korean_IME':'NOT_RUN','physical_audio_and_display_latency':'NOT_RUN','authenticated_account_roundtrip':'BLOCKED_NO_APPROVED_GAME_AUTHENTICATED_ENDPOINT','fine_balance_and_map_join_art':'TUNING_PENDING','performance':'FAIL_COLD_AND_FULL_WORLD_SAVE_TARGETS'}
 summary={'schema':'baram.g2.results/1','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_id':'BARAM_REBUILD_V2_RESOURCE_FIRST_20261016','overall':'PARTIAL_PERFORMANCE_NATIVE_ACCOUNT_GATES_REMAIN','app_source_commit':SOURCE,'incoming_head':'2317f6bf299b508962a850eeeefd92baa18f45c3','previous_app_source':'639750f04d10ee4ac3c1a7113232b8c30109f078','branch':'work/rebuild-p3-remediation-20261016','generation':'G2','counts':counts,'meaningful_monsters':513,'spawn_definitions':2026,'gather_nodes':256,'world':{k:usage[k]for k in('baseline_area_A0','g2_area_A1','ratio','unique_chunks_placed','source_chunks_total')},'tests':tests,'performance':performance,'remaining':remaining,'pack':pack,'reuse_impact':'G2_REUSE_IMPACT.json','source_count_correction':'Earlier521 included names. Strict401 was extended by112 actual tactical profiles to513;131 aliases are excluded.'}
 write(ev/'G2_RESULTS.json',summary)
 # Per-ID command evidence is separate from visual/native acceptance.
 passed={str(c['id'])for c in actions['checks']if c.get('result',c.get('status'))=='PASS'}
 with(ev/'G2_EXECUTION.csv').open('w',newline='',encoding='utf-8-sig')as f:
  writer=csv.writer(f);writer.writerow(['type','id','name','generation','command_execution','visual_review','balance','native'])
  for kind in counts:
   for iid,v in d[kind].items():
    ok=(iid in closure['item_routes']if kind=='items'else iid in closure['monster_routes']if kind=='monsters'else 'g1_actual_apply:'+iid in passed if kind=='skills'else True)
    writer.writerow([kind,iid,v.get('name',iid),v.get('generation','G1'),'PASS_FIXTURE'if ok else'NOT_CONFIRMED','NOT_ALL_IDS_VISUALLY_REVIEWED','TUNING_PENDING','NOT_RUN'])
 with(ev/'G2_SOURCE_USAGE.csv').open('w',newline='',encoding='utf-8-sig')as f:
  writer=csv.writer(f);writer.writerow(['source_ref','sha256','disposition','placements','preserved_cells','aperture_or_patch_cells'])
  for s in usage['source_chunks']:writer.writerow([s['source_ref'],s['source_chunk_sha256'],s['disposition'],len(s['placements']),sum(v['preserved_floor_collision_cells']for v in s['placements']),sum(v['reconstructed_overlap_or_aperture_cells']for v in s['placements'])])
 history=docs/'history';history.mkdir(exist_ok=True)
 for name in('DELIVERY.json','VERIFICATION.json','RESULTS.md'):
  target=history/('R14_'+name)
  if not target.exists():shutil.copy2(docs/name,target)
 write(docs/'VERIFICATION.json',{**summary,'schema':'baram.v2.playability-verification/4','historical_previous':'history/R14_VERIFICATION.json'})
 write(docs/'DELIVERY.json',{'schema':'baram.v2.delivery/4','status':summary['overall'],'app_source_commit':SOURCE,'app_candidate':'G2-r15','runtime_variant':'G2-delivery','branch':summary['branch'],'artifacts':pack['artifacts'],'source_content_fingerprint':pack['source_content_fingerprint'],'candidate_pack_provenance':'evidence/G2/G2_PACK_PROVENANCE.json','persistent_save_status':'PENDING_ORDERED_BATCH','actual_native_update':'NOT_RUN','remaining':remaining,'historical_previous':'history/R14_DELIVERY.json'})
 state_path=repo/'docs/rebuild/STATE.json';state=read(state_path)
 if 'G1_execution_before_G2'not in state['historical']:
  state['historical']['G1_execution_before_G2']={k:state.get(k)for k in('execution_20261017','playability_20261017','retained_actual_status')}
 state.update(status='G2_LARGE_WORLD_CANDIDATES_BUILT_PARTIAL_ACCEPTANCE',implementation_status=summary['overall'],handoff_commit=SOURCE,app_behavior_commit=SOURCE,current_phase='B5',current_phase_execution='G2_LARGE_WORLD_CONTENT_HOST_VERIFIED_B6_FILES_READY_NATIVE_ACCOUNT_PERFORMANCE_REMAIN')
 state['observed_counts']['active']={**counts,'monster_stable_ids':644,'monster_exact_semantics':513};state['observed_counts']['G2_registered']=counts;state['observed_counts']['G2_command_executed']={**closure['counts'],'skills':262,'quests':160,'recipes':73};state['retained_actual_status']={**remaining,'performance':performance};state['source_of_current_evidence']['scope']='G2_HOST_SCOPE_SOURCE_0627C774_PRIVATE_INSTALL_CANDIDATES_NOT_FULL_ACCEPTANCE'
 state['execution_20261017']={'generation':'G2','source_commit':SOURCE,'evidence':'docs/rebuild/v2/VERIFICATION.json'};state['playability_20261017']={'generation':'G2','ordinary_seconds':stress['details']['stress_seconds'],'overall':summary['overall']};state['gates']['content']='G2 required IDs have actual command paths; strict monster count513 excludes names/looks/aliases; whole-game natural balance remains tuning.'
 for phase in state['phases']:
  if phase['id']=='B5':phase['status']=summary['overall']
  if phase['id']=='B6':phase['status']='G2_APK_WINDOWS_CANDIDATES_READY_NATIVE_UPDATE_AND_FULL_ACCEPTANCE_PENDING'
 state['next_action']={'owner':'Work','phase':'B5','action':'Resume from exact G2 cold save existing_read phase: first process480.966ms/restart88.921ms. Preserve checksum, archive, revision and rollback checks while reducing repeat decode/migration; rerun only affected cold/save and source-dependent checks. Native/account gates remain separate.','resume_from':'app0627c774 / G2 delivery runtime / evidence/g2-delivery-cold first-process and restart-process','do_not_repeat':'No reset, new plan/engine, full source inventory/decoder restart, unchanged native CI retry, or recount by names. Reuse current 111map/1105item/644ID(513meaningful)/262skill/84NPC/160quest/73recipe implementation.'}
 state['publication']['verification']='App0627c774 and exact export file hashes are pinned separately from later documentation/test-tool commits; no main/production mutation.';write(state_path,state)
 master=repo/'docs/rebuild/MASTER_PLAN.md';text=master.read_text().replace('이번 고정 작업에서 게임 수정·APK/EXE 실행은 하지 않았다.','초기 B0 고정 이후 G1 및 G2 구현·호스트 실행·설치 후보 제작이 이어졌다. 현재 실행 상태는 STATE를 따른다.').replace('BARAM_V2_B5_SOURCE_WORLD_BULK_20261017','BARAM_V2_B5_B6_SOURCE_WORLD_BULK_20261017');master.write_text(text)
 # Keep existing defect IDs; append the G2 evidence without erasing G1 history.
 defects=repo/'docs/rebuild/p3-remediation/DEFECTS.csv'
 with defects.open(encoding='utf-8-sig',newline='')as f:reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
 for row in rows:
  if row['id']in('P3-FIX-09','P3-FIX-10','P3-FIX-17','P3-FIX-22','P3-FIX-06','P3-FIX-20'):
   row['b5_status']=summary['overall'];row['b5_evidence']='docs/rebuild/v2/VERIFICATION.json';row['b5_remaining']='G2 host execution and candidate files recorded; cold/frame targets fail; native Windows/Android update, Galaxy/IME/audio and authenticated account roundtrip remain.'
   if row['id']=='P3-FIX-09' and ' G2:127 native layouts' not in row['notes']:row['notes']+=' G2:127 native layouts retain158401 floor/collision cells with422 explicit aperture/patch cells;2cities280²/16fields128²/12four-floor families;world joins reconstructed.'
   if row['id']=='P3-FIX-22' and ' G2:1105items/644monsterIDs' not in row['notes']:row['notes']+=' G2:1105items/644monsterIDs(513strict gameplay signatures)/262skills/84NPC/160quests/73recipes. Actual commands; prerequisites labelled fixtures.'
 with defects.open('w',encoding='utf-8-sig',newline='')as f:writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
 md=f'''# 바람의나라 G2 대형 월드 · r15 설치 후보\n\n현재 판정: **{summary['overall']}**. B5→B6 순서와 기존 계획 ID를 유지한다. 정식 B6 완료로 판정하지 않는다.\n\n앱 소스 `{SOURCE}`, 원본 인계 HEAD2317에서 이어 갔다. 현재 엔진을 유지했고 새 프로젝트·Unity·유료 제작 도구를 사용하지 않았다.\n\n지도111개: 국내성·부여성280×280,16개 야외권역128×128,12던전계열 각4층 이상. 실제 연결 통행 면적은40,798→635,313셀(15.572배). 원본 공간 배치127개와 건물·방향 충돌을 함께 이식했다.158,401셀을 보존하고422개 접합/개구부 수정 셀을 기록했다. 지명·연결·출구는 재구성이다.\n\n아이템1,105·기술262·NPC84·의뢰160·제작73, 몬스터644ID 중 이름·외형·위치·중복을 제외한 기능 정의513종. 이전521 집계는 이름을 포함한 잘못된 수량 기준으로 대체했다. 추가112개는7개 전투 역할을16권역의 성장·전리품·제작 재료 흐름에 연결한 정의다. 독립 AI 알고리즘112개를 뜻하지 않는다. 모두 AI 공격·상태·파일 저장/재시작을 실행했다.\n\n명령6,872·행동2,299·저장/이전894·추가역할401·구조1,670·최종PCK 화면71 검사에서 실패0.4직업 새 캐릭터는 직접 보상 지급 없이5,955개 명령으로 성장·전직·거래·학습·귀환·저장을 완료했다. 가속 시간 검사이며 자연1~99·사람의 재미 검증은 아니다. 의뢰160/제작73은 정의 일치 검토 후 앞선 실제 명령 결과를 재사용하며 새 실행으로 합산하지 않는다.\n\n최종 일반 입력은{stress['details']['stress_seconds']:.2f}초. Linux llvmpipe/XTEST의 실제 창·저장·재시작이며 native Windows/Android 증거가 아니다. APK/PCK의8,990개 자료/컴파일 스크립트가 일치한다. 실제 설치 파일 PCK의 두 새 프로세스 이어하기72검사는 관찰 범위에서 통과했다.\n\n성능은 미달이다. 냉시작 frame p95 약36~39ms, 최초/재시작 저장528/153ms. 최초 저장 existing_read480.966ms가 우선 보수 지점이다. 전체2,026개 몬스터 파일은578,229bytes로 보존되지만 첫 저장164.224ms였다. 긴 프레임·100ms 초과 저장을 제거하지 않았다. 현재 수치는 VERIFICATION/원시 분석 JSON을 따른다.\n\nAndroid는 동일 패키지·서명키,versionCode7. Windows ZIP은 동일 EXE와 설치 안내를 담는다. 실제 native 실행·업데이트·기기 저장 이전, Galaxy/IME/물리음향, 인증 계정 왕복은 미실행/차단이다. 세부 밸런스·지도 접합 미술 조정도 남아 있다.\n\n자료·실행·설치 파일·실제 저장 결과는 HTML/증거ZIP/DELIVERY에 묶었다. 현재 앱을 과거 SHA로 reset하지 않는다. 다음 작업은 위 냉시작 저장 지연부터 좁게 이어 간다.\n\n이전 r14 기록: `history/R14_RESULTS.md`, `history/R14_VERIFICATION.json`, `history/R14_DELIVERY.json`.\n'''
 (docs/'RESULTS.md').write_text(md)
 def img(path,caption):
  return '<figure><img loading="lazy" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>'
 def table(headers,rows):return '<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>'for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>'for c in row)+'</tr>'for row in rows)+'</tbody></table></div>'
 count_rows=[('지도',76,111,'111개 출구 명령'),('아이템',593,1105,'1,105개 획득·사용/소비'),('몬스터 ID',346,644,'644개 전투 / 엄격한 기능513종'),('기술',190,262,'262개 시전·적용'),('NPC',24,84,'84명 접근·서비스'),('의뢰',52,160,'160개 완료 · 정의 일치 후 재사용'),('제작',9,73,'73개 제작 · 정의 일치 후 재사용')]
 screens=ev/'g2-delivery-pack-ui-labels';figures=''.join(img(screens/name,label)for name,label in[('world-00.png','최종 Windows 내장 PCK: 국내성 원본 배치 주변. 위치 시험 조건.'),('world-03.png','최종 PCK: 부여성 권역. 위치 시험 조건.'),('world-04.png','최종 PCK: 야외권역의 원본 지형·물체·NPC. 위치 시험 조건.'),('world-20.png','최종 PCK: 연결된 던전층. 위치 시험 조건.'),('map-00.png','최종 PCK 전체 도시 지도·현재 위치·서비스·출구.'),('map-32.png','작은 주막에서도 지도와 현재 위치가 표시됨.')])
 historical_figure=img(ev/'history-r14-screen-3.png','이전 r14에서 실제 일반 입력으로 종료한 장면. 보존된 결과 HTML의 원본 PNG를 재사용했고 이전 시험을 다시 실행하지 않았습니다.')
 natural_figure=img(ev/'g2-delivery-ordinary30/06-final-play.png','동일 최종 자료의 일반 OS 입력 플레이. 위치·보상 지급 없이 이어서 진행한 캐릭터.')
 body=f'''<p class="eyebrow">BARAM · G2 / 같은 Godot 프로젝트 / r15 설치 후보</p><h1>큰 세계와 다량 콘텐츠를<br>현재 게임에 연결했습니다.</h1><p class="lead">지도111개 · 아이템1,105개 · 전투·보상 정의513종 · 기술262개<br>NPC84명 · 의뢰160개 · 제작73개</p><p class="notice">현재 판정: 기능·자료 확장 및 설치 후보 전달. 성능 수치와 실제 플랫폼·계정 검증은 미완료입니다.</p><section><h2>월드 규모</h2>{table(['구분','실제 구현'],[('국내성·부여성','각280×280셀'),('야외권역16개','각128×128셀'),('던전계열12개','각4층 이상 · 층당64×64이상'),('정상 입구 연결 통행 면적','40,798 → 635,313셀 · 15.572배'),('원본 지도 배치 채택','250개 중127개. 작은 방104개 보존·미배치, 빈 청크19개 제외.'),('원본 보존·접합',source_cell_summary)])}<p>원본 건물·지형·방향 충돌의 상대 배치를 함께 가져왔습니다. 도시 사이 관계, 새 지명·길·출구·NPC 위치는 재구성입니다. 원본과 같은 역사 지도라고 주장하지 않습니다.</p></section><section><h2>등록과 실제 실행을 구분했습니다</h2>{table(['종류','G1','G2','실제 실행 범위'],count_rows)}<p>몬스터644ID 중131개 중복 의미는 목표 수량에서 제외했습니다. 이름·외형·지역·좌표를 제외한 전투·드롭 규칙으로513종입니다. 앞선 이름 포함521종 집계를 바로잡았습니다. 추가112개 정의는7개 전투 역할을16권역의 성장·전리품·제작 재료 흐름에 연결한 것입니다. 독립 AI 알고리즘112개를 뜻하지 않습니다.</p><p>전수 명령은 레벨·돈·재료·위치·RNG 조건을 밝힌 검사입니다. 아이템 지급 메뉴를 정상 게임에 넣지 않았습니다. 별도로 새4직업의 초반은 직접 보상 지급 없이 실제 명령으로 성장했습니다. 자연1~99·모든 콘텐츠 재미/밸런스 합격으로 해석하지 않습니다.</p></section><section><h2>최종 파일에서 본 화면</h2><p>아래 화면은 설치 파일의 실제 내장 PCK를 Linux Godot으로 연 것입니다. 화면 위치 조건은 시험용이며 실제 native Windows/Android 화면은 아닙니다.</p><div class="gallery">{figures}</div><h3>일반 플레이 기록: 이전 r14 → 현재 G2</h3><p>서로 다른 위치의 실제 종료 장면입니다. 같은 좌표의 미술 비교로 사용하지 않습니다.</p><div class="gallery">{historical_figure}{natural_figure}</div></section><section><h2>실행 증거</h2>{table(['검사','상태','규모','사용'],[(x['name'],x['status'],x['checks'],x['use'])for x in tests])}<p>미실행 검사는 PASS로 바꾸지 않았으며 검사 횟수를 합쳐 완성률로 표현하지 않았습니다. 최종 APK와 Windows 내장 PCK의8,990개 원본 자료·컴파일 스크립트가 일치합니다.</p></section><section><h2>성능과 남은 조건</h2>{table(['항목','실제 결과'],[('연속 일반 입력',f"{stress['details']['stress_seconds']:.2f}초 · Linux llvmpipe/XTEST"),('연속 구간 프레임',json.dumps(performance['long']['engine_wall_frame_interval'],ensure_ascii=False)),('연속 구간 저장',json.dumps(performance['long']['save_duration'],ensure_ascii=False)),('냉시작 최초/재시작 저장 최댓값','528.417ms /153.056ms ·100ms 기준 미달'),('전체 방문 상태 저장','2,026개 몬스터 보존 ·578,229bytes ·최초 저장164.224ms'),('실제 Windows·Android/Galaxy/IME/물리음향','NOT_RUN'),('같은 계정 인증 왕복','승인된 게임 인증 endpoint 미확인으로 BLOCKED'),('세부 밸런스·접합 미술','조정 필요')])}<p>긴 프레임과 저장 지연을 모두 보존했습니다. 엔진이 입력을 받은 뒤 post_draw까지의 측정은 실제 화면 표시나 물리 입력 지연을 증명하지 않습니다. 독립 프로세스의 시계를 합치지 않았습니다. 첫 구간의 빌드·검사 동시 실행도 제거하지 않았습니다.</p><p>다음 보수 지점은 냉시작 저장의 existing_read(최초480.966ms/재시작88.921ms)입니다. 원본 보존·체크섬·리비전·복구 조건을 유지하며 해당 경로부터 이어 갑니다.</p></section><section><h2>설치·업데이트·저장</h2><p>Android: 기존 보수본을 삭제하지 않고 같은 패키지·서명의 버전코드7 APK로 업데이트합니다. Windows: ZIP 전체를 새 폴더에 풀고 baram-p3-playable.exe를 실행합니다. 사용자 저장 경로는 기존 보수본과 같습니다.</p><p>저장 이전 전 원본·백업을 .pre-migration-SHA 파일로 보존합니다. 명시된 좌표 변환을 한 번 적용하고 아이템·기술·의뢰·돈·몬스터 생사/타이머를 유지합니다. 실제 기기 설치·업데이트·저장 유지 여부는 별도 미실행 항목입니다.</p>{table(['파일','bytes','SHA-256'],[(i['filename'],i['bytes'],i['sha256'])for i in pack['artifacts']])}</section><footer><p>계획 BARAM_REBUILD_V2_RESOURCE_FIRST_20261016 · B5→B6 유지<br>앱 소스 {SOURCE}<br>브랜치 work/rebuild-p3-remediation-20261016 · 원본 인계2317f6bf에서 계속</p><p>원본 자료·서명키 재취득이나 동일 실패 CI 반복 없이 증분 구현했습니다. 미완료 조건을 정식 납품 완료로 표시하지 않습니다.</p></footer>'''
 page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>바람의나라 G2 r15 실행 결과</title><style>body{margin:0;background:#131b1c;color:#e7e4d9;font:16px/1.7 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:44px 24px}h1{font-size:clamp(32px,5vw,61px);line-height:1.25;color:#f0d29a}h2{font-size:27px;color:#f0d29a}section{border-top:1px solid #45514c;margin-top:46px;padding-top:22px}.eyebrow{letter-spacing:.08em;color:#9bb3a5}.lead{font-size:21px}.notice{padding:17px;background:#483a25;border-left:4px solid #d3ac6d}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px;border-bottom:1px solid #45514c;overflow-wrap:anywhere}th{background:#263531}.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}figure{margin:18px 0}img{display:block;width:100%;height:auto;border:1px solid #5a6a5e}figcaption{font-size:13px;color:#bdcabc;padding:8px 0}footer{margin-top:50px;color:#b2bcb3;font-size:13px}pre{white-space:pre-wrap}@media(max-width:700px){.gallery{grid-template-columns:1fr}main{padding:24px 14px}}</style><main>'+body+'</main></html>'
 (out/'baram-G2-r15-results.html').write_text(page)
 # Repository evidence is concise text/JSON; source rasters and player saves stay private.
 target=docs/'evidence/G2';target.mkdir(parents=True,exist_ok=True)
 for name in('G2_RESULTS.json','G2_SOURCE_OBJECT_AUDIT.json','G2_DELIVERY_FREEZE.json','G2_PACK_PROVENANCE.json','G2_REUSE_IMPACT.json','G2_PACKAGED_ARTIFACTS.json','G2_EXECUTION.csv','G2_SOURCE_USAGE.csv'):
  shutil.copy2(ev/name,target/name)
 for name in('G2_WORLD_USAGE.json','G2_MAP_MIGRATION.json','G2_MONSTER_SEMANTICS.json','G2_COLLISION_PACKING.json'):
  shutil.copy2(rt/name,target/name)
 # Evidence archive includes previous failures, raw traces and short videos;
 # the final full video is a separate artifact, avoiding duplication.
 archive=out/'baram-G2-r15-evidence.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for f in sorted(ev.rglob('*')):
   if not f.is_file()or f.name=='STOP_OPERATOR':continue
   relative=f.relative_to(ev)
   if relative.parts[0]=='g2-delivery-ordinary30'and f.suffix.lower()in('.mp4','.mkv'):continue
   z.write(f,'evidence/'+relative.as_posix())
  for f in sorted(rt.glob('G2_*.json')):z.write(f,'runtime-metadata/'+f.name)
  for name in('Windows','Android'):
   build=root/('builds/g2-delivery-'+name)
   for f in build.iterdir():
    if f.is_file()and f.suffix in('.json','.log'):z.write(f,'exports/'+name+'/'+f.name)
  z.writestr('INSTALL_KO.md',(docs/'G2_INSTALL_KO.md').read_text());z.writestr('RESULTS.md',md)
 video=ev/'g2-delivery-ordinary30/ordinary-unedited.mp4';shutil.copy2(video,out/'baram-G2-r15-ordinary30-unedited.mp4')
 artifacts=[{'filename':f.name,'local_path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)}for f in sorted(out.glob('baram-G2-r15-*'))]
 delivery=read(docs/'DELIVERY.json');delivery['artifacts']=artifacts;write(docs/'DELIVERY.json',delivery);write(ev/'G2_FINAL_ARTIFACTS.json',{'artifacts':artifacts,'persistent_save_status':'PENDING_ORDERED_BATCH'})
 print(json.dumps({'overall':summary['overall'],'artifacts':[{'file':i['filename'],'bytes':i['bytes'],'sha256':i['sha256']}for i in artifacts]},ensure_ascii=False))
if __name__=='__main__':main()
