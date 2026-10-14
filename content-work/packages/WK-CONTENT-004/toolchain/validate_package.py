#!/usr/bin/env python3
"""Two-pass schema, guards, references, numeric, graph and private-byte validation.

JSON Schema is delivered for external tools; this small validator checks the
same required envelope plus the content semantics without new dependencies.
"""
import argparse
import collections
import copy
import datetime
import io
import json
import math
import re
import sys
import wave
import zipfile
from pathlib import Path
from PIL import Image
sys.dont_write_bytecode=True
from common import ROOT, WORK, BASE, canonical, file_sha, lines, load, sha, write

def validate(package, dependency_dirs=(), bundle=None, write_report=True, verify_manifest=False, dependency_bundles=()):
    package=Path(package);schema=load(package/'schema/content-v1.json')
    own=[]
    for p in sorted(package.glob('content-*.jsonl')):
        for n,r in enumerate(lines(p),1):own.append((p,n,r))
    dependency_records=[]
    for d in dependency_dirs:
        for p in sorted(Path(d).glob('content-*.jsonl')):dependency_records.extend(lines(p))
    all_records=dependency_records+[r for _,_,r in own]
    base=load(ROOT/'game/data/numeric.json')['contents'];external={r['id']:r for r in base}
    external.update({m['id']:m for m in load(ROOT/'game/data/world.json')['maps']})
    byid={};effective={};errors=[];checks=collections.Counter();prov=set()
    for d in [package,*map(Path,dependency_dirs)]:
        p=d/'provenance.json'
        if p.exists():prov.update(v['id'] for v in load(p))
    def fail(r,field,value,expected,path='',line=None):
        errors.append({'batch_id':package.name,'content_id':r.get('id'),'file':path,'line':line,'field':field,'value':value,
          'expected':expected,'provenance_refs':r.get('provenance_refs',[]),'reproduce':f'python3 content-work/tools/validate_package.py content-work/packages/{package.name}'})
    def integer(v):return type(v) is int
    # Incremental batches guard the effective data after pinned dependencies.
    # A KR numeric proposal owns runtime_definition; a new Work add owns data.
    external=copy.deepcopy(external)
    def apply_changes(node,r,check=False):
        for c in r.get('changes',[]):
            current=node;exists=True
            for part in c['path'].split('.'):
                if not isinstance(current,dict) or part not in current:exists=False;current=None;break
                current=current[part]
            guard=c.get('before',{})
            if check and (guard.get('exists')!=exists or exists and guard.get('value')!=current):
                fail(r,'changes.'+c['path'],guard,'guard matches effective pinned dependencies');continue
            parent=node;parts=c['path'].split('.')
            for part in parts[:-1]:
                if part not in parent or not isinstance(parent[part],dict):
                    fail(r,'changes.'+c['path'],part,'existing parent object');break
                parent=parent[part]
            else:parent[parts[-1]]=copy.deepcopy(c['after'])
    for r in dependency_records:
        if r['operation']=='add':external[r['id']]=copy.deepcopy(r['data'])
        elif r.get('target_id') in external:apply_changes(external[r['target_id']],r,True)
        else:fail(r,'target_id',r.get('target_id'),'dependency target exists')
    def valid_ratio(v,r,field):
        checks['ratios']+=1
        if not isinstance(v,dict) or not integer(v.get('numerator')) or not integer(v.get('denominator')) or not 0<=v['numerator']<=v['denominator'] or v['denominator']<=0:
            fail(r,field,v,'integer numerator 0..positive denominator');return False
        return True
    def numeric_walk(v,r,path='data'):
        if isinstance(v,dict):
            if 'numerator' in v and 'denominator' in v:valid_ratio(v,r,path)
            for k,x in v.items():
                if isinstance(x,(int,float)) and not isinstance(x,bool):
                    checks['numeric_values']+=1
                    if not math.isfinite(x):fail(r,path+'.'+k,x,'finite number')
                    negative_ok=k in ('armor_class','bonus_armor_class','armor_class_delta','x_offset','y_offset') or 'Repeat' in k or path.endswith('.original_rect')
                    if x<0 and not negative_ok and k not in ('left','top','light_parameter','level_delta'):
                        fail(r,path+'.'+k,x,'nonnegative, or explicitly signed stat')
                numeric_walk(x,r,path+'.'+k)
        elif isinstance(v,list):
            for i,x in enumerate(v):numeric_walk(x,r,path+f'[{i}]')
    for r in all_records:
        rid=r.get('id')
        if rid in byid:fail(r,'id',rid,'unique ID across package/dependencies')
        byid[rid]=r
        eid=r.get('target_id',rid)
        effective[eid]=r
    own_effective=[r.get('target_id',r['id']) for _,_,r in own]
    if len(own_effective)!=len(set(own_effective)):fail({},'target_id',None,'one consolidated proposal per target in one batch')
    available=set(effective)|set(byid)|set(external)
    for p,n,r in own:
        checks['records']+=1
        missing=set(schema['required'])-set(r)
        if missing:fail(r,'envelope',sorted(missing),'all required fields',str(p),n);continue
        if not re.fullmatch(schema['properties']['id']['pattern'],r['id']):fail(r,'id',r['id'],'persistent wk namespace',str(p),n)
        if r['kind'] not in schema['properties']['kind']['enum']:fail(r,'kind',r['kind'],'declared kind');continue
        if r['operation'] not in ('add','propose_patch'):fail(r,'operation',r['operation'],'add or propose_patch')
        if r['source_mode'] not in ('ORIGINAL','AVERAGED','INFERRED','DERIVED'):fail(r,'source_mode',r['source_mode'],'source mode enum')
        missing=set(schema['kind_required_data'][r['kind']])-set(r['data'])
        if missing:fail(r,'data',sorted(missing),'kind-specific required fields')
        if not r['provenance_refs'] or any(x not in prov for x in r['provenance_refs']):fail(r,'provenance_refs',r['provenance_refs'],'resolvable source/rule IDs')
        if r['operation']=='propose_patch':
            checks['conditional_patches']+=1
            target=external.get(r.get('target_id'))
            if target is None or r.get('base_game_commit')!=BASE:fail(r,'target_id/base',r.get('target_id'),'target in effective pinned base/dependencies');continue
            if not r.get('changes'):fail(r,'changes',[],'explicit guarded fields')
            for c in r.get('changes',[]):
                node=target;exists=True
                for part in c['path'].split('.'):
                    if not isinstance(node,dict) or part not in node:exists=False;node=None;break
                    node=node[part]
                guard=c.get('before',{})
                if guard.get('exists')!=exists or exists and guard.get('value')!=node:fail(r,'changes.'+c['path'],guard,'guard matches effective pinned dependencies')
                if c.get('provenance_ref') not in prov:fail(r,'changes.provenance_ref',c.get('provenance_ref'),'known rule')
        for x in r['references']:
            checks['references']+=1
            if not isinstance(x,dict) or x.get('id') not in available:fail(r,'references',x,'existing internal/dependency/external ID');continue
            selector=x.get('selector',{})
            if 'frame' in selector:
                a=byid.get(x['id']) or effective.get(x['id']);f=selector['frame']
                if not a or a['kind']!='asset' or not integer(f) or not 0<=f<a['data']['frame_count']:fail(r,'references.selector',x,'valid frame in sheet')
            if 'frames' in selector:
                a=byid.get(x['id']) or effective.get(x['id']);fs=selector['frames'];checks['explicit_frame_selections']+=len(fs)
                if not a or a['kind']!='asset' or not isinstance(fs,list) or len(fs)!=len(set(fs)) or any(not integer(f) or not 0<=f<a['data']['frame_count'] for f in fs):
                    fail(r,'references.selector.frames',x,'unique bounded model-local frame selection')
        numeric_walk(r['data'],r)
        d=r['data'];kind=r['kind']
        if kind=='asset':
            if not integer(d.get('frame_count')) or d['frame_count']<1:fail(r,'frame_count',d.get('frame_count'),'positive count')
            for name,a in d.get('metadata',{}).get('animations',{}).items():
                if a['offset']+a['directions']*a['frames_per_direction']>d['frame_count']:fail(r,'metadata.animations.'+name,a,'animation within original model')
        if kind=='item':
            if not integer(d.get('stack_limit')) or d['stack_limit']<1:fail(r,'stack_limit',d.get('stack_limit'),'positive integer')
            if d.get('slot')!='none' and d.get('stack_limit')!=1:fail(r,'stack_limit',d.get('stack_limit'),'equipment does not stack')
            if d.get('prices',{}).get('sell',0)>d.get('prices',{}).get('buy',0) and d.get('flags',{}).get('buyable'):fail(r,'prices',d['prices'],'no accidental arbitrage')
        if kind=='drop_group':
            mode=d['mode'];rolls=d['rolls']
            if mode not in ('independent','single_select','weighted','guaranteed'):fail(r,'mode',mode,'declared selection semantics')
            if mode in ('independent','single_select'):
                for roll in rolls:
                    if 'probability' not in roll:fail(r,'rolls.probability',roll,'explicit ratio');continue
                    valid_ratio(roll['probability'],r,'rolls.probability')
                if mode=='single_select' and rolls:
                    denoms={x['probability']['denominator'] for x in rolls}
                    if len(denoms)!=1 or sum(x['probability']['numerator'] for x in rolls)!=next(iter(denoms)):fail(r,'rolls',rolls,'exclusive sum including no-drop = denominator')
            if mode=='weighted' and (not rolls or any(x.get('weight',-1)<0 for x in rolls) or sum(x.get('weight',0) for x in rolls)<=0):fail(r,'weights',rolls,'nonnegative weights and positive total')
        if kind=='enhancement':
            for stage in d['stages']:
                outcomes=stage['outcomes'];nums=[o['probability']['numerator'] for o in outcomes];den={o['probability']['denominator'] for o in outcomes}
                keys=[o['result'] for o in outcomes]
                if len(set(keys))!=len(keys) or len(den)!=1 or sum(nums)!=next(iter(den)):fail(r,'stages.outcomes',outcomes,'exclusive named outcomes sum = denominator')
        if kind=='growth':
            if d['terminal']!=(d['level']==99):fail(r,'terminal',d['terminal'],'only level 99 terminal')
            if d['terminal'] and d['exp_to_next']!=0 or not d['terminal'] and d['exp_to_next']<=0:fail(r,'exp_to_next',d['exp_to_next'],'positive until terminal')
        if kind=='quest':
            if not d['objectives'] or not d['rewards']:fail(r,'objectives/rewards',d,'nonempty objectives and rewards')
            if d['repeat']['mode']=='once' and d['repeat'].get('cooldown_ms',0)!=0:fail(r,'repeat',d['repeat'],'once uses no cooldown')
    # Embedded data must also be referenced explicitly; catch forgotten refs.
    suffixes=('_id','_ids')
    def embedded(v,r,path='data'):
        if isinstance(v,dict):
            for k,x in v.items():
                if k.endswith(suffixes) and k not in ('bundle_id','source_id','rule_id','source_model_id','original_map_id','completion_key','placement_id'):
                    xs=x if k.endswith('_ids') and isinstance(x,list) else [x]
                    for ident in xs:
                        if ident is not None and isinstance(ident,str) and ident not in available:fail(r,path+'.'+k,ident,'resolvable embedded reference')
                embedded(x,r,path+'.'+k)
        elif isinstance(v,list):
            for i,x in enumerate(v):embedded(x,r,path+f'[{i}]')
    for _,_,r in own:embedded(r['data'],r)
    # Required prerequisite edges only; map cycles and repeat quests are legal.
    quests={r.get('target_id',r['id']):r for r in all_records if r['kind']=='quest'}
    active=set();done=set()
    def dfs(qid):
        if qid in active:fail(quests[qid],'prerequisites',qid,'acyclic required quest graph');return
        if qid in done:return
        active.add(qid)
        for q in quests[qid]['data']['prerequisites']:
            if q in quests:dfs(q)
        active.remove(qid);done.add(qid)
    for q in quests:dfs(q)
    for _,_,r in own:
        if r['kind']=='class':
            growth=[effective[x]['data'] for x in r['data']['growth_ids'] if x in effective]
            expected=set(range(r['data'].get('growth_start_level',1),r['data'].get('growth_end_level',99)+1));levels={x['level'] for x in growth}
            if levels!=expected:fail(r,'growth_ids',sorted(levels),'complete declared start..99 growth levels')
            last=-1
            for g in sorted(growth,key=lambda g:g['level']):
                if g['cumulative_exp']<last:fail(r,'cumulative_exp',g,'monotonic cumulative experience')
                last=g['cumulative_exp']
    checks['quest_graph_nodes']=len(quests)
    if bundle:
        acquire=load(package/'acquisition.json');p=Path(bundle)
        if p.stat().st_size!=acquire['size_bytes'] or file_sha(p)!=acquire['sha256']:fail({},'bundle',str(p),'matching acquisition size/SHA')
        with zipfile.ZipFile(p) as z:
            bundle_readers={acquire['bundle_id']:z}
            for dep_path in dependency_bundles:
                dep_path=Path(dep_path)
                matches=[load(Path(d)/'acquisition.json') for d in dependency_dirs if (Path(d)/'acquisition.json').exists() and load(Path(d)/'acquisition.json')['file_name']==dep_path.name]
                if not matches:fail({},'dependency_bundle',dep_path.name,'declared dependency acquisition');continue
                ac=matches[0]
                if dep_path.stat().st_size!=ac['size_bytes'] or file_sha(dep_path)!=ac['sha256']:
                    fail({},'dependency_bundle',dep_path.name,'matching pinned dependency bytes');continue
                bundle_readers[ac['bundle_id']]=zipfile.ZipFile(dep_path)
            def layout_bytes(d):
                ac=d['layout_acquisition'];reader=bundle_readers.get(ac['bundle_id'])
                if reader is None:raise ValueError('Missing pinned layout bundle '+ac['bundle_id'])
                raw=reader.read(ac['member'])
                if sha(raw)!=ac['sha256']:raise ValueError('Layout hash changed '+ac['member'])
                return raw
            names=z.namelist()
            if len(set(names))!=len(names) or len({n.casefold() for n in names})!=len(names):fail({},'bundle.names',len(names),'unique case-exact paths')
            manifest=load_json_bytes(z.read('PRIVATE_MANIFEST.json'))
            for f in manifest['files']:
                data=z.read(f['path']);checks['private_files']+=1
                if len(data)!=f['size_bytes'] or sha(data)!=f['sha256']:fail({},'private_file',f['path'],'matching bytes/hash')
                if f['path'].endswith('.png'):
                    try:
                        with Image.open(io.BytesIO(data)) as im:im.verify()
                    except (OSError,SyntaxError,ValueError) as e:fail({},'private_png',f['path'],'readable PNG with intact checksums: '+str(e))
                    checks['png_files']+=1
            checked_metadata=set()
            for _,_,r in own:
                if r['kind']!='asset':continue
                a=r['data']['acquisition'];data=z.read(a['member'])
                if sha(data)!=a['sha256']:fail(r,'acquisition',a,'member hash')
                if a['member'].endswith('.json') and a['member'] not in checked_metadata:
                    checked_metadata.add(a['member'])
                    m=load_json_bytes(data)
                    if 'frames' in m and 'pages' in m:
                        pages={x['path']:x for x in m['pages']}
                        for f in m['frames']:
                            x,y,w,h=f['region'];page=pages[f['path']]
                            if x<0 or y<0 or x+w>page['width'] or y+h>page['height']:fail(r,'frame.region',f,'frame within atlas')
                            checks['frame_rectangles']+=1
            placement_ids=set()
            for _,_,r in own:
                if r['kind']!='map':continue
                d=r['data'];ac=d['layout_acquisition'];raw=layout_bytes(d)
                if sha(raw)!=ac['sha256']:fail(r,'layout_acquisition',ac,'matching layout hash')
                layout=load_json_bytes(raw);w,h=d['width'],d['height']
                if (w,h)!=(layout['width'],layout['height']):fail(r,'dimensions',[w,h],'layout dimensions')
                masks=layout['collision_masks']
                if len(masks)!=w*h or len(layout['layers']['ground'])!=w*h or len(layout['layers']['objects'])!=w*h:fail(r,'layers',len(masks),'exact cell count')
                def walkable(xy):return isinstance(xy,list) and len(xy)==2 and all(integer(v) for v in xy) and 0<=xy[0]<w and 0<=xy[1]<h and masks[xy[1]*w+xy[0]]!=15
                if not walkable(d['entry']):fail(r,'entry',d['entry'],'walkable source entry');continue
                component={tuple(d['entry'])};todo=collections.deque(component)
                while todo:
                    x,y=todo.popleft()
                    for pos in [(x,y-1),(x-1,y),(x,y+1),(x+1,y)]:
                        if pos not in component and walkable(list(pos)):component.add(pos);todo.append(pos)
                checks['source_maps']+=1;checks['source_map_cells']+=w*h
                for group in ['portals','spawns','npc_placements']:
                    for pl in d[group]:
                        at=[pl['x'],pl['y']];checks['placements']+=1
                        if tuple(at) not in component:fail(r,group+'.position',at,'walkable reachable from entry under solid-mask interpretation')
                        pid=pl['placement_id']
                        if pid in placement_ids:fail(r,'placement_id',pid,'globally unique placement definition')
                        placement_ids.add(pid)
                        if group=='spawns' and (pl['max_live']<1 or any(tuple(p) not in component for p in pl['spawn_cells'])):fail(r,'spawn_cells',pl,'positive count and walkable spawn points')
                        if group=='portals':
                            dest=effective.get(pl['destination_map_id'])
                            if not dest or dest['kind']!='map':fail(r,'portal.destination',pl,'known map');continue
                            target=dest['data'];tx,ty=pl['destination_xy']
                            if not 0<=tx<target['width'] or not 0<=ty<target['height']:fail(r,'portal.destination_xy',pl,'within target map')
                            target_layout=load_json_bytes(layout_bytes(target))
                            if target_layout['collision_masks'][ty*target['width']+tx]==15:fail(r,'portal.destination_collision',pl,'walkable target')
                if d.get('variant_active') is not False and not d['portals']:fail(r,'portals',[],'at least one reachable return route')
            for reader in bundle_readers.values():
                if reader is not z:reader.close()
    if verify_manifest:
        m=load(package/'manifest.json')
        for f in m['files']:
            p=package/f['path'];checks['manifest_files']+=1
            if not p.is_file() or p.stat().st_size!=f['size_bytes'] or file_sha(p)!=f['sha256']:fail({},'manifest.file',f['path'],'size/hash')
        for dep in m['dependencies']:
            found=[Path(d) for d in dependency_dirs if Path(d).name==dep['batch_id']]
            if not found or file_sha(found[0]/'manifest.json')!=dep['manifest_sha256']:fail({},'dependency',dep,'pinned manifest')
    report={'batch_id':package.name,'base_game_commit':BASE,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'command':' '.join(sys.argv),'scope':'WORK_DATA_CHECKS_ONLY','result':'FAIL' if errors else 'PASS',
      'checks':dict(checks),'errors':errors,'input_content_sha256':{p.name:file_sha(p) for p in sorted(package.glob('content-*.jsonl'))},
      'private_bytes_check':'PASS' if bundle and not errors else 'NOT_RUN' if not bundle else 'FAIL',
      'game_import':'NOT_RUN','gameplay':'NOT_RUN','physical_audio_listening':'NOT_RUN'}
    if write_report:write(package/'validation.json',report)
    return report

def load_json_bytes(data):return json.loads(data.decode('utf-8'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('--dependency',action='append',default=[]);p.add_argument('--bundle')
    p.add_argument('--verify-manifest',action='store_true');p.add_argument('--report-only',action='store_true');p.add_argument('--dependency-bundle',action='append',default=[])
    a=p.parse_args();r=validate(a.package,a.dependency,a.bundle,not a.report_only,a.verify_manifest,a.dependency_bundle)
    print(json.dumps({'batch_id':r['batch_id'],'result':r['result'],'checks':r['checks'],'errors':r['errors'][:12]},ensure_ascii=False))
    raise SystemExit(r['result']!='PASS')
