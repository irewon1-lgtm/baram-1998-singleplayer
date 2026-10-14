#!/usr/bin/env python3
"""Recover only missing signed-frame effect timelines; reuse all original PNGs."""
import argparse, re, shutil, sys, collections
from pathlib import Path
sys.dont_write_bytecode=True
from common import WORK,ROOT,IDs,load,lines,write,record,ref,shard,file_sha,sha
sys.path.insert(0,str(ROOT/'tools'))
from legacy_assets import dat_entries

def parse(text):
    blocks={}
    for m in re.finditer(r'^ID (\d+), (.*?)(?=^ID |\Z)',text,re.M|re.S):
        s=m[0];nf=int(re.search(r'NumFrontFrames (\d+)',s)[1]);nb=int(re.search(r'NumBackFrames (\d+)',s)[1])
        fs=[{'frame':int(f),'delay_ms':int(ms),'alpha_parameter':float(a),'light_parameter':int(l)} for f,ms,a,l in re.findall(r'Frame# (-?\d+), Delay (-?\d+), Alpha ([\d.]+), Light (-?\d+)',s)]
        if len(fs)!=nf+nb:raise ValueError('Original signed row count mismatch '+m[1])
        blocks[int(m[1])]={'front':fs[:nf],'back':fs[nf:],'repeat':{k:int(v) for k,v in re.findall(r'(RepeatFrontFrom|RepeatFrontTo|RepeatBackFrom|RepeatBackTo) (-?\d+)',s)}}
    return blocks

def build(batch,dat):
    source=dat_entries(dat.read_bytes())['effect.tbl'][2];blocks=parse(source.decode('ascii'));assets={}
    for p in (WORK/'packages/WK-ASSETS-001').glob('content-*.jsonl'):
        for r in lines(p):assets[r['id']]=r
    sheet=assets['wk.asset.kr491.sheet.effect'];ids=IDs();rs=[];rows=[]
    missing=[int(r['field']) for r in load(WORK/'catalog/asset-errors.json') if r.get('source_file')=='effect.tbl']
    for mid in missing:
        md=blocks[mid];fs=md['front']+md['back']
        if not fs:
            rows.append({'source_model':mid,'status':'BLOCKED','reason':'EMPTY_SOURCE_TIMELINE_NO_DRAWABLE_CONTENT','next':'Use an appropriate existing effect for consumers; retain empty source ID as source history, do not invent pixels'})
            continue
        if any(not -1<=f['frame']<sheet['data']['frame_count'] or f['delay_ms']<=0 for f in fs):raise ValueError('Malformed effect source '+str(mid))
        aid=ids.get('asset',f'kr491.effect.{mid:03d}')
        if aid in assets:raise ValueError('Already fixed effect must not be added again')
        d={'name':f'effect {mid}','asset_type':'effect_sequence','frame_count':len(fs),'acquisition':dict(sheet['data']['acquisition']),
           'metadata':dict(md,sheet_id=sheet['id'],render_order=['back','actor','front'],loop_capability_required=any(v>=0 for v in md['repeat'].values()),alpha='EPF_STENCIL'),
           'semantic_status':'RECOVERED_SIGNED_SOURCE_TIMELINE_EMPTY_FRAME_WAIT_INTERPRETATION_NOT_NATIVE_VERIFIED'}
        r=record(aid,'asset',d,['prov.effect.signed','rule.effect.blank'],refs=[ref('sheet',sheet['id']),ref('drawable_source_frames',sheet['id'],{'frames':sorted({f['frame'] for f in fs if f['frame']>=0})})],mode='DERIVED')
        r['field_provenance']={'metadata.front':'prov.effect.signed','metadata.back':'prov.effect.signed','metadata.repeat':'prov.effect.signed','semantic_status':'rule.effect.blank'};rs.append(r)
        rows.append({'source_model':mid,'status':'SOURCE_TIMELINE_RECOVERED','timeline_entries':len(fs),'drawable_entries':sum(f['frame']>=0 for f in fs),'wait_entries':sum(f['frame']==-1 for f in fs),'source_effect_tbl_sha256':sha(source),'role_link':'NOT_RUN','native_wait_interpretation':'NOT_RUN'})
    regression=[]
    for mid in [3,109]:
        old=assets[f'wk.asset.kr491.effect.{mid:03d}']['data']['metadata'];observed=blocks[mid]
        same=all(old[k]==observed[k] for k in ('front','back','repeat'))
        regression.append({'source_model':mid,'result':'PASS' if same else 'FAIL','scope':'parsed timeline equals prior fixed source definition, no PNG re-decoding'})
    if any(r['result']!='PASS' for r in regression):raise ValueError('Normal effect timeline regression')
    p=WORK/'packages'/batch
    if p.exists():raise ValueError('Use a new immutable batch')
    (p/'schema').mkdir(parents=True);shutil.copy2(WORK/'schemas/content-v1.json',p/'schema/content-v1.json')
    write(p/'provenance.json',[{'id':'prov.effect.signed','source_mode':'DERIVED','source_dat_sha256':file_sha(dat),'source_effect_tbl_sha256':sha(source),'rule':'Parse signed original Frame# indices; preserve exact row order, front/back split, delay, alpha/light and repeats'},
      {'id':'rule.effect.blank','source_mode':'INFERRED','basis':['source Frame# -1 rows have positive explicit delay and occupy declared front/back counts','old unsigned regex omitted these rows, causing count mismatches'],
       'rule':'Interpret -1 as a timed no-draw entry; runtime must advance time without reading negative atlas index. Source bytes preserved. Native interpretation and playback NOT_RUN.'}])
    shard(p,rs);ids.save();write(p/'recovery-summary.json',{'scope':'DATA_ONLY_SOURCE_TIMELINE','new_asset_definitions':len(rs),'new_private_bytes_required':0,'png_redecoded':0,'cause':'UNSIGNED_REGEX_OMITTED_FRAME_MINUS_ONE, not zero delays','attempts':rows,'normal_regression':regression,'timeline_entries':sum(r['data']['frame_count'] for r in rs),'wait_entries':sum(f['frame']==-1 for r in rs for f in r['data']['metadata']['front']+r['data']['metadata']['back']),'native_renderer_comparison':'NOT_RUN','game_import':'NOT_RUN','gameplay':'NOT_RUN'})
    print(batch,'effect timelines',len(rs),'normal comparisons',len(regression),'empty source remains1')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--dat',type=Path,required=True);a=p.parse_args();build(a.batch,a.dat)
