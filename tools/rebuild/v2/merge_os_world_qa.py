#!/usr/bin/env python3
"""Combine independent actual-OS door workers without promoting visual status."""
import argparse,csv,html,json,os
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
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
    results=sorted(cases.values(),key=lambda r:r['case_id']);summary={'maps_with_actual_frames':len(maps),'exit_count':len(results),'input_pass_count':sum(r['input_status']=='PASS_INPUT_DOOR_CONTRACT' for r in results),'input_fail_count':sum(r['input_status']=='FAIL' for r in results),'input_not_run_count':sum(r['input_status']=='NOT_RUN' for r in results),'visual_status':'NOT_RUN','natural_progression':'NOT_RUN','long_stability':'NOT_RUN_USER_SCOPE_CHANGE'}
    out={'schema':'baram.world-exhaustive-os-merge/1','content_sha256':next(iter(contents)),'scope':'Offline fixtures before process start; subsequent actual GUI keys only. Functional results do not establish visual quality or natural progression.','summary':summary,'workers':sources,'maps':list(maps.values()),'case_results':results}
    (a.output/'WORLD_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    with (a.output/'WORLD_QA.csv').open('w',newline='') as f:
        fields=['case_id','map_id','map_name','exit_id','to_map','door_x','door_y','input_status','visual_status','error','captures'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:w.writerow({**{k:r.get(k,'') for k in ['case_id','map_id','map_name','input_status','visual_status','error']},'exit_id':r['exit']['id'],'to_map':r['exit']['to_map'],'door_x':r['exit']['x'],'door_y':r['exit']['y'],'captures':'|'.join(r['captures'])})
    esc=html.escape
    head='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>111지도·전체 출입구 실제 OS QA</title><style>body{background:#1f1b17;color:#eee8dc;font:16px system-ui;margin:24px}h1,h2{color:#efd29a}a{color:#baddff}article{border:1px solid #705a3b;padding:16px;margin:20px 0}img{max-width:100%;image-rendering:pixelated}.frames{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}code{overflow-wrap:anywhere}.fail{color:#ff9e99}summary{cursor:pointer}</style>'
    body=[head,'<h1>실제 실행 화면·OS 출입구 QA</h1>','<p>오프라인 시작 저장 fixture 이후 일반 OS 키로 접근→통과→도착→역방향→원위치. 자연 육성·실제 기기·계정·시각 품질 PASS를 뜻하지 않습니다. 모든 시각 판정은 별도 육안 검수 전 NOT_RUN입니다.</p>',f'<pre>{esc(json.dumps(summary,ensure_ascii=False,indent=2))}</pre>','<h2>111개 지도: 실제 게임 화면과 게임 지도창</h2>']
    for m in maps.values():
        body.append(f'<article><h3>{esc(m["name"])} · <code>{esc(m["map_id"])}</code></h3><p>좌표 {esc(str(m["coordinate"]))} · VISUAL_NOT_RUN</p><div class="frames">'+''.join(f'<a href="{esc(m[k])}"><img loading="lazy" src="{esc(m[k])}" alt="{esc(m["name"])} {k}"></a>' for k in ['runtime_frame','overview_frame'])+'</div></article>')
    body.append('<h2>전체 출입구: 실제 접근·도착·귀환 화면</h2>')
    for r in results:
        body.append(f'<article><h3>{esc(r["case_id"])} {esc(r["map_name"])}</h3><p class="{"fail" if r["input_status"]!="PASS_INPUT_DOOR_CONTRACT" else ""}">{esc(r["input_status"])} · VISUAL_NOT_RUN</p><p><code>{esc(r["exit"]["id"])} ({r["exit"]["x"]}, {r["exit"]["y"]}) → {esc(r["exit"]["to_map"])}</code></p>'+ (f'<p>{esc(r["error"])}</p>' if r.get('error') else '')+'<div class="frames">'+''.join(f'<a href="{esc(f)}"><img loading="lazy" src="{esc(f)}" alt="{esc(r["case_id"])} actual game frame"></a>' for f in r['captures'])+'</div></article>')
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
    for base in range(0,len(door_rows),6):
        sheet=Image.new('RGB',(1100,1170),'#211a13');draw=ImageDraw.Draw(sheet)
        for index,r in enumerate(door_rows[base:base+6]):
            x=(index%2)*550;y=(index//2)*390
            if r['captures']:
                frame=Image.open(a.output/r['captures'][0]).convert('RGB');frame.thumbnail((550,360),Image.Resampling.NEAREST);sheet.paste(frame,(x,y+30))
            draw.text((x+5,y+5),r['case_id']+' '+str((r['exit']['x'],r['exit']['y']))+' '+r['input_status'],fill='#fff0c0',font=font)
        sheet.save(directory/f'doors-{base:03d}-{min(base+5,len(door_rows)-1):03d}.jpg',quality=94,subsampling=0)
if __name__=='__main__':main()
