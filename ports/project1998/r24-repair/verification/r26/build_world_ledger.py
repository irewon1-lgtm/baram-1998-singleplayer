"""Developer-only whole registry ledger and retained-atlas contact renderer. Never loaded by the game."""
import csv,functools,hashlib,html,json,pathlib,re,struct,sys
from PIL import Image,ImageDraw
import render_maps as art
ROOT=pathlib.Path(__file__).resolve().parents[2]
INPUT=pathlib.Path(sys.argv[1]).resolve();OUT=pathlib.Path(sys.argv[2]).resolve();OUT.mkdir(parents=True,exist_ok=True)
maps=json.loads((INPUT/'maps.json').read_text());warps=json.loads((INPUT/'warps.json').read_text());data=ROOT/'candidate/game-data'
def rows(name):return [r for r in csv.DictReader(l for l in(data/name).read_text(encoding='utf-8-sig').splitlines()if l.strip()and not l.lstrip().startswith('#'))if not next(iter(r.values()),'').startswith('#')]
meta={int(r['MapId']):r for r in rows('Maps.csv')if r['MapId'].isdigit()};raw=rows('Warps.csv');npcs=rows('NPCs.csv')
groups={};effective={}
for r in raw:
 k=tuple(int(r[x])for x in ['SourceMapId','SourceX','SourceY']);groups.setdefault(k,[]).append(r)
 if int(r['DestinationMapId'])in{m['id']for m in maps}:effective[k]=r
for w in warps:
 k=(w['map'],w['x'],w['y']);r=effective.get(k);w['raw_id']=r['WarpId']if r else None;w['raw_definitions']=len(groups.get(k,[]));w['original_or_reconstructed']='ORIGINAL_OR_PRIOR_COMPATIBILITY_SEE_RAW_COMMENT';w['unresolved']='NOT_RUN visual matching, original handler roundtrip, condition matrix and saved dynamic doors'if w['status']=='STATIC_ONLY'else'REVIEW static anomaly; requires individual original-condition and movement reproduction'
for k,r in effective.items():
 if k[0]not in{m['id']for m in maps}:warps.append({'map':k[0],'x':k[1],'y':k[2],'destination':int(r['DestinationMapId']),'dx':int(r['DestinationX']),'dy':int(r['DestinationY']),'raw_id':r['WarpId'],'status':'EXCLUDED_INVALID_SOURCE_MAP','reason':'Runtime table contains source without registered terrain. Explicit row retained, not silently excluded.','roundtrip':'NOT_RUN'})
images=OUT/'terrain-previews';images.mkdir(exist_ok=True);seen={};scale=.25
@functools.lru_cache(maxsize=50000)
def small(k):
 f=art.frame(k)
 if not f:return None
 pic,origin=f;return pic.resize((max(1,round(pic.width*scale)),max(1,round(pic.height*scale))),Image.Resampling.NEAREST),(round(origin[0]*scale),round(origin[1]*scale))
def draw(terrain,w,h):
 im=Image.new('RGBA',(w*6,h*6),(0,0,0,255));c=list(struct.iter_unpack('<HH',terrain))
 def put(k,x,y):
  f=small(k)
  if f:im.alpha_composite(f[0],(x+f[1][0],y+f[1][1]))
 for i,(g,o)in enumerate(c):
  k=art.C['grounds'].get(str(g))
  if k:put(k,i%w*6,i//w*6)
 for i,(g,o)in enumerate(c):
  for layer,k in enumerate(art.C['objects'].get(str(o),{}).get('frames',[])):
   if k:put(k,i%w*6,(i//w-layer)*6)
 return im.convert('RGB')
for n,m in enumerate(maps):
 mid=m['id'];m['metadata']=meta.get(mid,{});m['npc_cells']=[[int(n['NpcX']),int(n['NpcY'])]for n in npcs if n.get('NpcMapId')==str(mid)];m['terrain_render']='GENERATED_OFFLINE_RETAINED_ATLAS_QUARTER_SIZE_NOT_GODOT_NOT_HUMAN_REVIEW'
 key=m.get('terrain_sha256')
 if key and key not in seen:
  rawbytes=(INPUT/'terrain'/f'{key}.bin').read_bytes();im=draw(rawbytes,m['width'],m['height']);im.save(images/(key+'.png'),optimize=True)
  c=list(struct.iter_unpack('<HH',rawbytes));missingg=sorted({g for g,o in c if g and str(g)not in art.C['grounds']});missingo=sorted({o for g,o in c if o and str(o)not in art.C['objects']});seen[key]={'missing_ground_ids':missingg,'missing_object_ids':missingo}
 m['asset_reference_check']=seen.get(key,{});m['visual']='RENDERED_NOT_HUMAN_REVIEWED'
 if n%500==0:print('CONTACT_MAPS',n,'unique',len(seen),flush=True)
calls=[]
for p in sorted(data.glob('*.lua')):
 for line,text in enumerate(p.read_text().splitlines(),1):
  for match in re.finditer(r'(?::|\b)warp\s*\(([^)]*)\)',text,re.I):calls.append({'file':p.name,'line':line,'expression':match.group(1),'target_kind':'STATIC_LITERAL'if re.match(r'^\d+\s*,\s*\d+\s*,\s*\d+\s*$',match.group(1))else'DYNAMIC_REVIEW','condition_execution':'NOT_RUN','comment_only':text.lstrip().startswith('--')})
excluded=[{'id':mid,'name':r.get('MapName'),'reason':'Metadata row without registered playable terrain; retained separately, not counted as a playable map.'}for mid,r in meta.items()if mid not in{m['id']for m in maps}]
for name,items in [('maps',maps),('warps',warps),('script-movements',calls),('metadata-without-terrain',excluded)]:
 (OUT/(name+'.json')).write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')))
 keys=list(dict.fromkeys(k for r in items for k in r))
 with(OUT/(name+'.csv')).open('w',newline='',encoding='utf-8-sig')as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(dict,list))else v for k,v in r.items()}for r in items)
summary={'registered_maps':len(maps),'metadata_unique_ids':len(meta),'metadata_without_terrain':len(excluded),'raw_warp_rows':len(raw),'effective_warps_including_invalid_source':len(warps),'directional_static_maps':len(maps),'offline_contact_render_maps':len(maps),'unique_rendered_terrain':len(seen),'human_whole_map_review':0,'all_warp_actual_roundtrip':'NOT_RUN','static_warp_review':sum(w['status']=='REVIEW'for w in warps),'maps_with_exit_candidates':sum(m.get('arrivals_without_static_exit',0)>0 for m in maps),'script_call_sites':len(calls),'physical_android':'NOT_RUN','scope':'All registered IDs retained. Render/structural checks are not individual visual correctness or game progression PASS.'}
(OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
body='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 전체 지도 원장</title><style>body{background:#16191c;color:#eee;font:16px system-ui;margin:18px}input,select{padding:10px;font-size:16px}canvas{max-width:100%;image-rendering:pixelated;background:#000}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#8ec5ff}</style><h2>전체 지도·출입구 검사 원장</h2><p>정적 분석과 원본 아틀라스 축소 렌더. 실제 Godot 실행·전체 수동 검수·각 문 왕복 PASS가 아닙니다.</p><input id="q" placeholder="지도 번호 또는 이름"><select id="sel"></select><p id="counts"></p><canvas id="c"></canvas><pre id="info"></pre><script>const maps=MAPS,warps=WARPS;let visible=maps;const sel=document.querySelector('#sel'),q=document.querySelector('#q'),c=document.querySelector('#c'),ctx=c.getContext('2d');function filter(){visible=maps.filter(m=>(m.id+' '+m.name).toLowerCase().includes(q.value.toLowerCase()));sel.innerHTML=visible.map(m=>'<option value="'+m.id+'">'+m.id+' '+m.name+'</option>').join('');show()}function show(){const m=maps.find(m=>m.id==sel.value);if(!m)return;const ws=warps.filter(w=>w.map==m.id),im=new Image();im.onload=()=>{c.width=im.width;c.height=im.height;ctx.drawImage(im,0,0);for(const w of ws){ctx.strokeStyle='#ffdf00';ctx.strokeRect(w.x*6,w.y*6,6,6)}for(const p of m.npc_cells){ctx.fillStyle='#00bfff';ctx.fillRect(p[0]*6+2,p[1]*6+2,3,3)}};im.src='terrain-previews/'+m.terrain_sha256+'.png';document.querySelector('#counts').textContent=maps.length+' 지도 / '+warps.length+' 유효 출입구 행 (범위 밖 출발 지도 별도 표시 포함)';document.querySelector('#info').textContent=JSON.stringify({map:m,warps:ws},null,2)}q.oninput=filter;sel.onchange=show;filter();</script>'''
body=body.replace('MAPS',json.dumps(maps,ensure_ascii=False).replace('</','<\\/')).replace('WARPS',json.dumps(warps,ensure_ascii=False).replace('</','<\\/'));(OUT/'map-ledger.html').write_text(body)
print(json.dumps(summary),flush=True)
