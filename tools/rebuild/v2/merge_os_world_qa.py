#!/usr/bin/env python3
"""Combine independent actual-OS door workers without promoting visual status."""
import argparse,csv,hashlib,html,json,os
from pathlib import Path
def file_sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def apply_visual_ledgers(paths,maps,cases,content_sha,output):
    """Only actual human rows with matching generation and captured-image hashes.

    PASS_VISIBLE_FRAME_ONLY stays narrow. Conflicting FAIL dominates; every
    original reviewer statement remains attached for the integrator to assess.
    """
    rejected=[];applied=[]
    for path in paths:
        doc=json.loads(path.read_text())
        if doc.get('content_sha256')!=content_sha:
            rejected.append({'ledger':str(path),'reason':'CONTENT_FINGERPRINT_MISMATCH'});continue
        rows=[]
        for key in ['maps','reviewed_cases','cases','case_results','rows']:
            if isinstance(doc.get(key),list):rows+=doc[key]
        for review in rows:
            identifier=review.get('case_id',review.get('map_id'))
            target=cases.get(identifier) if review.get('case_id') else maps.get(identifier)
            if not target:
                rejected.append({'ledger':str(path),'id':identifier,'reason':'CAPTURE_TARGET_NOT_PRESENT'});continue
            expected=target.get('captures',[]) if review.get('case_id') else [target.get('runtime_frame'),target.get('overview_frame')]
            expected={str((output/p).resolve()):p for p in expected if p}
            hashes=review.get('image_sha256',{})
            if isinstance(hashes,str) and review.get('image'):hashes={review['image']:hashes}
            if not isinstance(hashes,dict):hashes={}
            for evidence in review.get('evidence',[]) if isinstance(review.get('evidence'),list) else []:
                if isinstance(evidence,dict) and evidence.get('file') and evidence.get('sha256'):hashes[evidence['file']]=evidence['sha256']
            verified=[]
            for filename,digest in hashes.items():
                candidate=Path(filename)
                if not candidate.is_absolute():candidate=path.parent/candidate
                absolute=str(candidate.resolve())
                if absolute in expected and candidate.is_file() and file_sha(candidate)==digest:verified.append({'file':expected[absolute],'sha256':digest})
            if not verified:
                rejected.append({'ledger':str(path),'id':identifier,'reason':'NO_MATCHING_CURRENT_CAPTURE_HASH','instruction':'Include image_sha256 {relative_actual_capture_path: sha256}, using this ledger directory as path base.'});continue
            status=str(review.get('visual_status',review.get('review_status','NOT_RUN')))
            notes=review.get('notes',review.get('observation',review.get('reason','')))
            record={'reviewer':doc.get('reviewer',path.stem),'ledger':str(path),'ledger_sha256':file_sha(path),'status':status,'notes':notes,'evidence':verified,'classification':review.get('classification',review.get('failure_code'))}
            target.setdefault('visual_reviews',[]).append(record);applied.append({'id':identifier,**record})
            statuses=[r['status'] for r in target['visual_reviews']]
            target['visual_status']=next((s for s in statuses if s.startswith('FAIL')),next((s for s in statuses if s.startswith('PASS')),'NOT_RUN'))
            target['visual_notes']=' | '.join(str(r['notes']) for r in target['visual_reviews'])
    return {'applied_rows':len(applied),'applied':applied,'rejected':rejected,'policy':'Human review only, generation and actual current capture hash required; scoped image PASS never means entire-map/native/natural PASS.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--visual-ledger',type=Path,action='append',default=[]);p.add_argument('--reuse-input',type=Path,action='append',default=[]);p.add_argument('--reuse-proof',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    maps={};cases={};sources=[];contents=set();expected={}
    for worker in a.worker:
        data=json.loads((worker/'WORLD_DOOR_QA.json').read_text());contents.add(data['content_sha256']);sources.append(str(worker.resolve()));plan=json.loads((worker/'PLAN.json').read_text())
        expected.update({r['case_id']:r for r in plan['cases']})
        for row in data['case_results']:
            row={**row,'worker':os.path.relpath(worker,a.output),'captures':[os.path.relpath(worker/f,a.output) for f in row['captures']]}
            if row['case_id'] in cases:raise ValueError('Duplicate case result: '+row['case_id'])
            cases[row['case_id']]=row
        for m in data['maps']:
            m={**m,**{k:os.path.relpath(worker/m[k],a.output) for k in ['runtime_frame','overview_frame']}}
            maps.setdefault(m['map_id'],m)
    if len(contents)!=1:raise ValueError('Cannot merge differing runtime generations')
    for id,row in expected.items():cases.setdefault(id,{**row,'input_status':'NOT_RUN','visual_status':'NOT_RUN','captures':[],'error':'Worker did not execute this case'})
    reused=[]
    if a.reuse_input:
        if not a.reuse_proof:raise ValueError('Explicit physics/source reuse proof required')
        proof=json.loads(a.reuse_proof.read_text())
        if proof.get('new_content_sha256')!=next(iter(contents)) or not all(proof.get(k) is True for k in ['physics_equal','source_engine_equal','source_input_handlers_equal']):raise ValueError('Reuse proof does not establish current physical/input parity')
        for directory in a.reuse_input:
            old=json.loads((directory/'WORLD_DOOR_QA.json').read_text())
            if old['content_sha256']!=proof['old_content_sha256']:raise ValueError('Old functional generation differs from reuse proof')
            for prior in old['case_results']:
                id=prior['case_id']
                if id not in proof['case_ids'] or prior['input_status']!='PASS_INPUT_DOOR_CONTRACT':raise ValueError('Unapproved/unpassed reused case: '+id)
                current=cases[id]
                if current['input_status']=='NOT_RUN':continue # Its fresh current visual capture has not arrived yet.
                if current['input_status']!='NOT_RUN_VISUAL_RECAPTURE':raise ValueError('Reuse needs fresh current visual recapture: '+id)
                for key in ['map_id','exit','return_exit','start','door_contract','reverse_door_contract']:
                    if prior[key]!=current[key]:raise ValueError('Physical case field changed: '+id+' '+key)
                current['input_status']='PASS_REUSED_UNCHANGED_PHYSICS'
                current['reused_input']={'source':str(directory),'old_content_sha256':old['content_sha256'],'old_runtime_sha256':old['runtime_sha256'],'source_result_sha256':file_sha(directory/'WORLD_DOOR_QA.json'),'proof':str(a.reuse_proof),'proof_sha256':file_sha(a.reuse_proof),'prior_result':prior,'scope':'Functional input evidence reused only; shown approach/overview are current captures. Not an exact current-binary rerun.'}
                reused.append(id)
    visual_ingest=apply_visual_ledgers(a.visual_ledger,maps,cases,next(iter(contents)),a.output)
    results=sorted(cases.values(),key=lambda r:r['case_id']);summary={'maps_with_actual_frames':len(maps),'exit_count':len(results),'input_pass_count':sum(r['input_status']=='PASS_INPUT_DOOR_CONTRACT' for r in results),'input_fail_count':sum(r['input_status']=='FAIL' and 'Operator cancelled' not in r.get('error','') for r in results),'input_cancelled_partial_count':sum('Operator cancelled' in r.get('error','') for r in results),'input_not_run_count':sum(r['input_status']=='NOT_RUN' for r in results),'visual_status':'NOT_RUN','natural_progression':'NOT_RUN','long_stability':'NOT_RUN_USER_SCOPE_CHANGE'}
    summary.update(map_visual_reviewed=sum(bool(m.get('visual_reviews')) for m in maps.values()),map_visible_frame_pass=sum(m['visual_status'].startswith('PASS') for m in maps.values()),map_visible_frame_fail=sum(m['visual_status'].startswith('FAIL') for m in maps.values()),door_visual_reviewed=sum(bool(r.get('visual_reviews')) for r in results),door_visible_frame_pass=sum(r['visual_status'].startswith('PASS') for r in results),door_visible_frame_fail=sum(r['visual_status'].startswith('FAIL') for r in results))
    summary['input_reused_unchanged_physics_count']=len(reused)
    summary['visual_status']='FAIL' if summary['map_visible_frame_fail'] or summary['door_visible_frame_fail'] else 'NOT_RUN'
    summary['visual_scope']='Manual screen-area review counts below; an overall B5 visual PASS is not inferred automatically.'
    out={'schema':'baram.world-exhaustive-os-merge/1','content_sha256':next(iter(contents)),'scope':'Offline fixtures before process start; subsequent actual GUI keys only. Functional results do not establish visual quality or natural progression.','summary':summary,'workers':sources,'maps':list(maps.values()),'case_results':results,'visual_ledger_ingest':visual_ingest}
    (a.output/'WORLD_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    with (a.output/'WORLD_QA.csv').open('w',newline='') as f:
        fields=['case_id','map_id','map_name','exit_id','to_map','door_x','door_y','input_status','visual_status','visual_notes','error','captures'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:w.writerow({**{k:r.get(k,'') for k in ['case_id','map_id','map_name','input_status','visual_status','visual_notes','error']},'exit_id':r['exit']['id'],'to_map':r['exit']['to_map'],'door_x':r['exit']['x'],'door_y':r['exit']['y'],'captures':'|'.join(r['captures'])})
    with (a.output/'MAP_VISUAL_QA.csv').open('w',newline='') as f:
        fields=['map_id','name','coordinate','visual_status','visual_notes','runtime_frame','overview_frame'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for m in maps.values():w.writerow({k:m.get(k,'') for k in fields})
    esc=html.escape
    head='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>111지도·전체 출입구 실제 OS QA</title><style>body{background:#1f1b17;color:#eee8dc;font:16px system-ui;margin:24px}h1,h2{color:#efd29a}a{color:#baddff}article{border:1px solid #705a3b;padding:16px;margin:20px 0}img{max-width:100%;image-rendering:pixelated}.frames{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}code{overflow-wrap:anywhere}.fail{color:#ff9e99}summary{cursor:pointer}</style>'
    body=[head,'<h1>실제 실행 화면·OS 출입구 QA</h1>','<p>오프라인 시작 저장 fixture 이후 일반 OS 키로 접근→통과→도착→역방향→원위치. 자연 육성·실제 기기·계정 PASS를 뜻하지 않습니다. 육안 검수 전 시각 판정은 NOT_RUN이며, 검수자의 실제 이미지 해시가 일치하는 기록만 반영합니다. PASS_VISIBLE_FRAME_ONLY는 해당 캡처 영역의 판정입니다.</p>',f'<pre>{esc(json.dumps(summary,ensure_ascii=False,indent=2))}</pre>','<h2>111개 지도: 실제 게임 화면과 게임 지도창</h2>']
    for m in maps.values():
        body.append(f'<article><h3>{esc(m["name"])} · <code>{esc(m["map_id"])}</code></h3><p>좌표 {esc(str(m["coordinate"]))} · {esc(m["visual_status"])}</p><p>{esc(m.get("visual_notes","아직 육안 검수 기록이 없습니다."))}</p><div class="frames">'+''.join(f'<a href="{esc(m[k])}"><img loading="lazy" src="{esc(m[k])}" alt="{esc(m["name"])} {k}"></a>' for k in ['runtime_frame','overview_frame'])+'</div></article>')
    body.append('<h2>전체 출입구: 실제 접근·도착·귀환 화면</h2>')
    for r in results:
        body.append(f'<article><h3>{esc(r["case_id"])} {esc(r["map_name"])}</h3><p class="{"fail" if r["input_status"]!="PASS_INPUT_DOOR_CONTRACT" else ""}">{esc(r["input_status"])} · {esc(r["visual_status"])}</p><p>{esc(r.get("visual_notes","아직 육안 검수 기록이 없습니다."))}</p><p><code>{esc(r["exit"]["id"])} ({r["exit"]["x"]}, {r["exit"]["y"]}) → {esc(r["exit"]["to_map"])}</code></p>'+ (f'<p>{esc(r["error"])}</p>' if r.get('error') else '')+'<div class="frames">'+''.join(f'<a href="{esc(f)}"><img loading="lazy" src="{esc(f)}" alt="{esc(r["case_id"])} actual game frame"></a>' for f in r['captures'])+'</div></article>')
    body.append('</html>');(a.output/'world-qa-gallery.html').write_text('\n'.join(body));print(json.dumps(summary,ensure_ascii=False))
    # Derivatives of actual framebuffer crops only. They aid exhaustive visual
    # review; creating a sheet does not change any map/door visual status.
    from PIL import Image,ImageDraw
    directory=a.output/'contact-sheets';directory.mkdir(exist_ok=True)
    font_path=next((p for p in [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),None)
    from PIL import ImageFont
    font=ImageFont.truetype(str(font_path),16) if font_path else ImageFont.load_default()
    rows=list(maps.values())
    for base in range(0,len(rows),6):
        sheet=Image.new('RGB',(1100,1170),'#211a13');draw=ImageDraw.Draw(sheet)
        for index,m in enumerate(rows[base:base+6]):
            x=(index%2)*550;y=(index//2)*390
            frame=Image.open(a.output/m['runtime_frame']).convert('RGB');frame.thumbnail((550,360),Image.Resampling.NEAREST);sheet.paste(frame,(x,y+30))
            draw.text((x+5,y+5),m['map_id']+' '+str(m['coordinate']),fill='#fff0c0',font=font)
        sheet.save(directory/f'maps-{base:03d}-{min(base+5,len(rows)-1):03d}.jpg',quality=94,subsampling=0)
    door_rows=results
    for stage,prefix in [('approach','doors'),('arrival','doors-arrival'),('returned','doors-returned')]:
        for base in range(0,len(door_rows),6):
            sheet=Image.new('RGB',(1100,1170),'#211a13');draw=ImageDraw.Draw(sheet)
            for index,r in enumerate(door_rows[base:base+6]):
                x=(index%2)*550;y=(index//2)*390
                capture=next((f for f in r['captures'] if '-'+stage+'-' in f or f.endswith('-'+stage+'.png')),None)
                if capture:
                    frame=Image.open(a.output/capture).convert('RGB');frame.thumbnail((550,360),Image.Resampling.NEAREST);sheet.paste(frame,(x,y+30))
                draw.text((x+5,y+5),r['case_id']+' '+stage+' '+r['input_status'],fill='#fff0c0',font=font)
            sheet.save(directory/f'{prefix}-{base:03d}-{min(base+5,len(door_rows)-1):03d}.jpg',quality=94,subsampling=0)
if __name__=='__main__':main()
