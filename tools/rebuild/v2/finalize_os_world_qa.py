#!/usr/bin/env python3
"""Publish scoped, mixed-generation evidence without relabeling raw captures.

The baseline is the complete actual-OS sweep. Final art changes require both
an explicit mechanics/input dependency proof and separately viewed new frames.
Old negatives remain first-class history; no whole-world clean-quality PASS is
inferred from frame/overview sampling or from a successful route.
"""
import argparse,copy,csv,hashlib,html,json,os
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p,out):return os.path.relpath(Path(p).resolve(),out.resolve())
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def rebase_review(review,base,out):
    r=copy.deepcopy(review)
    for e in r.get('evidence',[]):e['file']=rel(base/e['file'],out)
    if r.get('ledger') and Path(r['ledger']).is_file():r['ledger']=rel(Path(r['ledger']),out)
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','refresh','output','limits']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ui-followup',type=Path,action='append',default=[])
    p.add_argument('--require-complete',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    base=read(a.baseline/'WORLD_QA.json');proof=read(a.refresh/'JOINT_REUSE_PROOF.json')
    if base['content_sha256']!=proof['old_content_sha256'] or not all(proof.get(k) is True for k in ['physics_equal','source_engine_equal','source_input_handlers_equal']):raise ValueError('Joint mechanics/input reuse is not proven')
    maps={};oldmapfails=[];oldcasefails=[]
    for original in base['maps']:
        m=copy.deepcopy(original);m['baseline_visual_status']=m['visual_status'];m['historical_visual_reviews']=[rebase_review(r,a.baseline,a.output) for r in m.get('visual_reviews',[])];m['baseline_capture_content_sha256']=base['content_sha256'];m['capture_content_sha256']=base['content_sha256'];m['capture_source_scope']='Actual f25/a8 snapshot; visual dependency reuse is explicit, not an exact-final-source recapture.'
        for k in ['runtime_frame','overview_frame']:m[k]=rel(a.baseline/m[k],a.output)
        m['visual_reviews']=[];m['visual_status']='PASS_SCOPED_BASE_FRAME_REUSED' if m['baseline_visual_status'].startswith('PASS') else 'FAIL_HISTORICAL_PENDING_CURRENT_ART_REVIEW'
        if m['baseline_visual_status'].startswith('FAIL'):oldmapfails.append(m['map_id'])
        maps[m['map_id']]=m
    fresh_ids=set()
    for name in ['ROOM_REFRESH.json','ANIMAL_REFRESH.json']:
        doc=read(a.refresh/name)
        if doc['content_sha256']!=proof['new_content_sha256'] or doc['runtime_sha256']!=proof['new_runtime_sha256']:raise ValueError('Current visual generation differs from proof')
        for row in doc['maps']:
            mid=row['map_id'];m=maps[mid];m['baseline_runtime_frame']=m['runtime_frame'];m['baseline_overview_frame']=m['overview_frame'];m['baseline_coordinate']=m['coordinate']
            for k in ['runtime_frame','overview_frame']:m[k]=rel(a.refresh/row[k],a.output)
            m['coordinate']=row['coordinate'];m['capture_content_sha256']=doc['content_sha256'];m['capture_runtime_sha256']=doc['runtime_sha256'];m['capture_source_scope']='Actual current joint3b9 snapshot at declared offline fixture pose; ordinary Continue/map button. No route-rerun or historical dynamic-state replay claim.';m['current_visual_manifest']=rel(a.refresh/name,a.output);m['visual_status']='NOT_RUN_CURRENT_VISUAL_REVIEW';fresh_ids.add(mid)
    rejected=[]
    for path in sorted(a.refresh.glob('visual-review-*.json')):
        doc=read(path)
        if doc.get('content_sha256')!=proof['new_content_sha256']:continue
        rows=[]
        for key in ['maps','reviewed_cases','rows']:
            if isinstance(doc.get(key),list):rows+=doc[key]
        for row in rows:
            mid=row.get('map_id')
            if mid not in fresh_ids:continue
            m=maps[mid];expected={str((a.output/m[k]).resolve()):m[k] for k in ['runtime_frame','overview_frame']};verified=[]
            for filename,digest in row.get('image_sha256',{}).items():
                file=Path(filename) if Path(filename).is_absolute() else path.parent/filename
                if str(file.resolve()) in expected and file.is_file() and sha(file)==digest:verified.append({'file':expected[str(file.resolve())],'sha256':digest})
            if not verified:rejected.append({'map_id':mid,'ledger':str(path),'reason':'NO_CURRENT_IMAGE_HASH_MATCH'});continue
            status=row.get('visual_status','NOT_RUN');record={'reviewer':doc.get('reviewer',path.stem),'ledger':rel(path,a.output),'ledger_sha256':sha(path),'status':status,'notes':row.get('notes',''),'evidence':verified}
            m['visual_reviews'].append(record);statuses=[r['status'] for r in m['visual_reviews']];m['visual_status']=next((s for s in statuses if s.startswith('FAIL')),next((s for s in statuses if s.startswith('PASS')),'NOT_RUN'))
    limits=read(a.limits);limitrows=limits['maps'];by_limit={r['map_id']:r for r in limitrows}
    for row in limitrows:
        if row.get('evidence',{}).get('file'):row['evidence']['file']=rel(Path(row['evidence']['file']),a.output)
    for mid,m in maps.items():
        m['dynamic_visual_limits']=[by_limit[mid]] if mid in by_limit else []
        m['whole_map_every_tile_visual_cleanliness']='NOT_ESTABLISHED'
    cases=[]
    for original in base['case_results']:
        r=copy.deepcopy(original);r['baseline_input_status']=r['input_status'];r['baseline_visual_status']=r['visual_status'];r['historical_visual_reviews']=[rebase_review(v,a.baseline,a.output) for v in r.get('visual_reviews',[])]
        if r['input_status'] not in ['PASS_INPUT_DOOR_CONTRACT','PASS_REUSED_UNCHANGED_PHYSICS']:raise ValueError('Unresolved baseline input case: '+r['case_id'])
        r['input_status']='PASS_REUSED_UNCHANGED_PHYSICS';r['joint_input_reuse_proof']=rel(a.refresh/'JOINT_REUSE_PROOF.json',a.output);r['exact_joint_binary_route_rerun']=False
        r['captures']=[rel(a.baseline/f,a.output) for f in r['captures']]
        r['worker']=rel(a.baseline/r['worker'],a.output)
        for attempt in r.get('superseded_attempts',[]):attempt['captures']=[rel(a.baseline/f,a.output) for f in attempt['captures']]
        involved={r['map_id'],r['exit']['to_map']};followups=[{'map_id':mid,'visual_status':maps[mid]['visual_status'],'runtime_frame':maps[mid]['runtime_frame'],'reviews':maps[mid]['visual_reviews']} for mid in involved if mid in fresh_ids and maps[mid]['visual_reviews']]
        r['current_art_dependency_followups']=followups;r['dynamic_visual_limit_maps']=[mid for mid in involved if mid in by_limit]
        if r['baseline_visual_status'].startswith('FAIL'):
            oldcasefails.append(r['case_id']);r['visual_status']='RESOLVED_ART_DEPENDENCY_CURRENT_SCENE' if any(f['visual_status'].startswith('PASS') for f in followups) else 'FAIL_HISTORICAL_UNRESOLVED'
            r['visual_resolution_scope']='Old failed phase images retained. Changed material/actor appearance inspected in current actual map scene; exact historical three-phase dynamic scene was not replayed. Gate mechanics and geometry are invariant.'
        else:r['visual_status']='PASS_SCOPED_BASE_CAPTURE_WITH_DEPENDENCY_PROOF'
        r['whole_case_final_binary_all_visual_cleanliness']='NOT_ESTABLISHED';cases.append(r)
    followups=[{'report':rel(f,a.output),'sha256':sha(f),'details':read(f)} for f in a.ui_followup]
    ui_cases=[];ui_historical=[]
    for followup in followups:
        doc=followup['details']
        if doc.get('content_sha256')!=proof['new_content_sha256'] or doc.get('runtime_sha256')!=proof['new_runtime_sha256']:raise ValueError('UI followup runtime mismatch')
        if doc.get('gameplay_sha256')!=proof.get('release_ui_sha256'):raise ValueError('UI followup does not bind release source')
        conditional={r['image_sha256']:r for r in doc.get('conditional_old_frame_geometry_proofs',[])}
        for row in doc.get('cases',[]):
            if not Path(row['capture']).is_file() or sha(Path(row['capture']))!=row['image_sha256']:raise ValueError('UI actual capture hash mismatch')
            if not row.get('visual_status','').startswith('PASS') or row.get('engine_errors'):raise ValueError('Unresolved UI visible case')
            if row.get('current_source_binding')=='ACTUAL_FINAL_SOURCE_CAPTURE':
                if row['captured_gameplay_sha256']!=proof['release_ui_sha256']:raise ValueError('Fresh UI frame source mismatch')
            elif row.get('current_source_binding')=='CONDITIONAL_REUSE_NO_NEW_POST_INTERSECTION':
                if row['image_sha256'] not in conditional or conditional[row['image_sha256']]['new_post_overlap_count']!=0:raise ValueError('Conditional UI frame dependency not established')
            else:raise ValueError('Unknown UI frame source attribution')
            ui_cases.append(row)
        ui_historical+=doc.get('preserved_negative_history',[])
    summary={'maps_with_actual_frames':len(maps),'maps_individually_reviewed_in_baseline':base['summary']['map_visual_reviewed'],'exit_contracts_with_actual_os_input_evidence':len(cases),'baseline_direct_f25_route_passes':base['summary']['input_pass_count'],'prior_exact_physics_route_passes':base['summary']['input_reused_unchanged_physics_count'],'joint_dependency_reused_routes':len(cases),'direct_exact_joint_binary_route_reruns':0,'unresolved_input_failures':0,'unexecuted_exit_contracts':0,'current_joint_affected_maps_captured':len(fresh_ids),'current_joint_affected_maps_reviewed':sum(bool(maps[mid]['visual_reviews']) for mid in fresh_ids),'historical_map_visual_failures_retained':len(oldmapfails),'historical_door_visual_failures_retained':len(oldcasefails),'historical_input_negative_attempts_retained':base['summary']['superseded_negative_attempts_retained'],'unresolved_static_art_failures':sum(m['visual_status'].startswith('FAIL') for m in maps.values())+sum(r['visual_status'].startswith('FAIL') for r in cases),'known_dynamic_crowd_or_occlusion_maps':len(by_limit),'all111maps_every_tile_clean_visual_quality':'NOT_ESTABLISHED','natural_progression':'NOT_RUN','long_stability':'NOT_RUN_USER_SCOPE_CHANGE','native_device_account_sync':'NOT_RUN_BY_THIS_SUITE','scope':'Every map and door has separately inspected actual captures/input evidence with generation attribution. Scoped material/threshold/actor review does not establish whole-world clean visual quality.'}
    complete=summary['maps_individually_reviewed_in_baseline']==111 and len(cases)==276 and len(fresh_ids)==27 and summary['current_joint_affected_maps_reviewed']==27 and summary['unresolved_static_art_failures']==0
    summary['ui_render_followup_reports']=len(followups)
    summary['ui_caption_visible_cases']=len(ui_cases)
    summary['fresh_release_source_ui_capture_cases']=sum(r.get('current_source_binding')=='ACTUAL_FINAL_SOURCE_CAPTURE' for r in ui_cases)
    summary['conditionally_reused_ui_capture_cases']=len(ui_cases)-summary['fresh_release_source_ui_capture_cases']
    summary['historical_ui_caption_failures_retained']=len(ui_historical)
    summary['unresolved_ui_caption_failures']=0 if ui_cases else 'NOT_REVIEWED'
    summary['scoped_evidence_completion']='COMPLETE_WITH_EXPLICIT_DYNAMIC_LIMITS' if complete and followups else 'MATERIAL_INPUT_COMPLETE_UI_FOLLOWUP_PENDING' if complete else 'INCOMPLETE'
    if a.require_complete and not (complete and followups):raise ValueError('Final scoped evidence incomplete: '+json.dumps(summary))
    doc={'schema':'baram.joint-world-authoritative-qa/1','release_content_sha256':proof['new_content_sha256'],'release_runtime_sha256':proof['new_runtime_sha256'],'release_ui_sha256':proof.get('release_ui_sha256'),'baseline_content_sha256':base['content_sha256'],'summary':summary,'baseline_evidence':{'file':rel(a.baseline/'WORLD_QA.json',a.output),'sha256':sha(a.baseline/'WORLD_QA.json')},'joint_reuse_proof':{'file':rel(a.refresh/'JOINT_REUSE_PROOF.json',a.output),'sha256':sha(a.refresh/'JOINT_REUSE_PROOF.json')},'ui_render_followups':followups,'dynamic_visual_limits':limits,'maps':list(maps.values()),'case_results':cases,'current_visual_review_rejected_rows':rejected}
    write(a.output/'WORLD_QA.json',doc)
    for filename,rows,fields in [('MAP_VISUAL_QA.csv',list(maps.values()),['map_id','name','coordinate','baseline_visual_status','visual_status','capture_content_sha256','capture_source_scope','runtime_frame','overview_frame']),('WORLD_QA.csv',cases,['case_id','map_id','map_name','baseline_input_status','input_status','baseline_visual_status','visual_status','exact_joint_binary_route_rerun'])]:
        with (a.output/filename).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for row in rows:writer.writerow({k:row.get(k,'') for k in fields})
    esc=html.escape;body=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>111지도·276출입구 최종 합본 검증</title><style>body{background:#231b14;color:#f3e5d0;font:16px system-ui;margin:24px}a{color:#b7d8ff}article{border:1px solid #87653c;padding:16px;margin:20px 0}.frames{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px}img{max-width:100%}code{overflow-wrap:anywhere}.limit{color:#ffd395}</style><h1>111지도·276출입구 최종 합본 검증</h1><p>각 화면은 실제 게임 실행 캡처입니다. 시작 저장 fixture 이후 일반 OS 입력으로 검증한 경로와 변경 영역의 후속 화면을 출처별로 구분합니다. 최종 바이너리로 전체 경로를 다시 실행했다고 주장하지 않습니다. 지도 전체의 모든 타일·모든 동적 상황이 깨끗하다는 PASS는 부여하지 않습니다.</p>',f'<pre>{esc(json.dumps(summary,ensure_ascii=False,indent=2))}</pre>',f'<p><a href="{esc(rel(a.baseline/"world-qa-gallery.html",a.output))}">전수 원본 갤러리·과거 실패 보존</a> · <a href="{esc(rel(a.refresh/"joint-visual-refresh-gallery.html",a.output))}">최종 합본27개 영향 지도 후속</a> · <a href="WORLD_QA.json">상세 JSON</a></p>']
    if followups:body+=['<h2>추가 UI 표현 후속</h2>']+[f'<p><a href="{esc(r["report"])}">{esc(Path(r["report"]).name)}</a> · {esc(r["sha256"])}</p>' for r in followups]
    body.append('<h2>111지도 실제 화면·지도창</h2>')
    for m in maps.values():
        body.append('<article><h3>'+esc(m['name'])+' · <code>'+esc(m['map_id'])+'</code></h3><p>'+esc(str(m['coordinate'])+' · '+m['visual_status'])+'</p><p>'+esc(m['capture_source_scope'])+'</p>')
        if m['dynamic_visual_limits']:body.append('<p class="limit">동적 혼잡 제한: '+esc(str(m['dynamic_visual_limits'][0].get('notes','')) )+'</p>')
        if m['baseline_visual_status'].startswith('FAIL'):body.append('<p>이전 시각 FAIL 보존. 현재 수정 영역 검수와 입력/기하 불변 근거를 별도로 연결합니다.</p>')
        body.append('<div class="frames">'+''.join(f'<a href="{esc(m[k])}"><img loading="lazy" src="{esc(m[k])}"></a>' for k in ['runtime_frame','overview_frame'])+'</div></article>')
    body.append('<h2>276출입구: 실제 입력·3단계 화면</h2>')
    for r in cases:
        body.append('<article><h3>'+esc(r['case_id']+' '+r['map_name'])+'</h3><p>'+esc(r['input_status']+' · '+r['visual_status'])+'</p>')
        if r.get('superseded_attempts'):
            body.append('<details><summary>이전 실패 시도 보존</summary><p>'+esc(r.get('retest_scope',''))+'</p>')
            for attempt in r['superseded_attempts']:
                body.append('<p>'+esc(attempt.get('error',''))+'</p><div class="frames">'+''.join(f'<a href="{esc(f)}"><img loading="lazy" src="{esc(f)}"></a>' for f in attempt['captures'])+'</div>')
            body.append('</details>')
        if r['baseline_visual_status'].startswith('FAIL'):body.append('<p>이전 실제 화면의 시각 FAIL을 유지하며 최종 수정 표현을 새 장면에서 검수했습니다. 아래 원래 단계 화면을 새 바이너리 화면으로 재표기하지 않습니다.</p>')
        if r['dynamic_visual_limit_maps']:body.append('<p class="limit">관련 지도에 동적 혼잡 제한 기록이 있습니다.</p>')
        body.append('<div class="frames">'+''.join(f'<a href="{esc(f)}"><img loading="lazy" src="{esc(f)}"></a>' for f in r['captures'])+'</div>')
        for f in r['current_art_dependency_followups']:body.append('<p>현재 표현 후속: <a href="'+esc(f['runtime_frame'])+'">'+esc(f['map_id']+' '+f['visual_status'])+'</a></p>')
        body.append('</article>')
    (a.output/'world-qa-gallery.html').write_text('\n'.join(body)+'\n');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
