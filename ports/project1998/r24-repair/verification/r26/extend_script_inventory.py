"""Keep table warps separate from conditional scripted doors and conservatively indexed source calls."""
import collections,csv,hashlib,json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];out=Path(sys.argv[1]);data=R/'candidate/game-data'
maps=json.loads((out/'maps.json').read_text());by_id={m['id']:m for m in maps}
def rows(name):return list(csv.DictReader(l for l in(data/name).read_text(encoding='utf-8-sig').splitlines()if l.strip()and not l.lstrip().startswith('#')))
def write(name,items):
 (out/(name+'.json')).write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')))
 keys=list(dict.fromkeys(k for item in items for k in item))
 with(out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False)if isinstance(v,(list,dict))else v for k,v in item.items()}for item in items)
calls=[];files={}
for folder,pattern in [(R/'candidate/Server','*.cs'),(data,'*.lua')]:
 for path in sorted(folder.rglob(pattern)):
  if any(p in ('bin','obj')for p in path.relative_to(folder).parts):continue
  text=path.read_text();name=path.relative_to(R).as_posix();files[name]=hashlib.sha256(text.encode()).hexdigest()
  for line,source in enumerate(text.splitlines(),1):
   for match in re.finditer(r'\b(EnterMap|Warp|WarpHall|TeleportToBind|Teleport|warp)\s*\(',source):
    calls.append({'file':name,'line':line,'method':match.group(1),'source':source.strip(),
     'kind':'COMMENT_REFERENCE'if source.lstrip().startswith(('//','--','/*','*'))else'SOURCE_CALL_OR_DEFINITION_REVIEW',
     'target_resolution':'LITERAL_OR_SYMBOLIC_EXPRESSION_RETAINED; dynamic target domain NOT_RUN',
     'execution':'NOT_RUN_AS_INDIVIDUAL_SCRIPT_CALL_SITE','physical_android':'NOT_RUN'})
   if re.search(r'\b_char\.Map\s*=',source):calls.append({'file':name,'line':line,'method':'CHARACTER_MAP_ASSIGNMENT','source':source.strip(),'kind':'LEAF_ASSIGNMENT_REVIEW','execution':'NOT_RUN_AS_INDIVIDUAL_SCRIPT_CALL_SITE'})
scripted=[]
def add(source_map,x,y,dest,dx,dy,kind,origin,condition,extra=None):
 row={'source_map':int(source_map),'x':int(x),'y':int(y),'destination_map':int(dest),'dx':int(dx),'dy':int(dy),
  'kind':kind,'origin':origin,'conditions':condition,'execution':'NOT_RUN_IN_TABLE_WARP_SWEEP','overall':'REVIEW_SCRIPTED_CONDITION_AND_ROUNDTRIP'}
 if extra:row.update(extra)
 source=by_id.get(row['source_map']);target=by_id.get(row['destination_map'])
 row['source_in_bounds']=bool(source and 0<=row['x']<source['width']and 0<=row['y']<source['height'])
 row['destination_in_bounds']=bool(target and 0<=row['dx']<target['width']and 0<=row['dy']<target['height'])
 scripted.append(row)
for cave in rows('MythicCaves.csv'):
 for tile in cave['EntranceTiles'].split(';'):
  x,y=map(int,tile.split(':'))
  for tier,offset in [(1,0),(2,3000),(3,4000)]:
   base=int(cave['DestMap']);target=base+offset if base+offset in by_id else base
   add(cave['EntranceMap'],x,y,target,cave['DestX'],cave['DestY'],'MYTHIC_TIER','MythicCaves.csv',
    'Deepest qualified tier; level AND (MaxHp OR MaxMp threshold); original class/quest/runtime rules retained',
    {'tier':tier,'requirements':{k:v for k,v in cave.items()if k.startswith('T')},'animal':cave['Animal'],'sources':cave.get('Sources')})
bands=rows('EventCaveTiers.csv')
for cave in rows('EventCaves.csv'):
 for tile in cave['EntranceTiles'].split(';'):
  x,y=map(int,tile.split(':'))
  for tier,target in enumerate(cave['TierMaps'].split('|'),1):
   add(cave['EntranceMap'],x,y,target,cave['DestX'],cave['DestY'],'EVENT_TIER','EventCaves.csv +EventCaveTiers.csv',
    'Original level/mark ladder, pages and near/far menu; all band boundaries NOT_RUN',{'tier':tier,'bands':bands,'raw_configuration':cave})
for door in rows('ArenaDoors.csv'):
 for tile in door['Tiles'].split(';'):
  x,y=map(int,tile.split(':'));left=door['DestX'].split('-')
  for dx in range(int(left[0]),int(left[-1])+1):
   add(door['Map'],x,y,door['DestMap'],dx,door['DestY'],'ARENA','ArenaDoors.csv',
    'Original min/max level, mark and OR vital caps; no waiver',{'raw_configuration':door})
for hall in rows('PathHalls.csv'):
 for x in (1,2):
  if int(hall['GuildMap']):add(hall['HallMap'],x,23,hall['GuildMap'],x+6,3,'CLASS_GUILD','PathHalls.csv',
   'Original base-class member gate',{'base_class':hall['BaseClass']})
 for alignment,key in enumerate(['SanctumUnaligned','SanctumKwisin','SanctumMingken','SanctumOhaeng']):
  target=int(hall[key]);dy=by_id[target]['height']-2 if target in by_id else 18
  for x in (8,9):add(hall['HallMap'],x,1,target,x-3,dy,'ALIGNMENT_SANCTUM','PathHalls.csv',
   'Original Character.Alignment0..3; invalid alignment falls back0',{'alignment':alignment})
add(1002,19,91,1228,21,16,'FOREVER_TREE_DIALOG','Session.Navigation.cs:TryForeverTreeEntrance',
 'Warning dialog must complete and source map remain unchanged. Other progression gates are not waived.')
config=[]
for name in ['WorldMapDests.csv','WorldMapTriggers.csv','GatewayGates.csv','WarpQuestLocks.csv']:
 if(data/name).exists():
  for index,row in enumerate(rows(name),1):config.append({'file':name,'data_row':index,'configuration':row,'execution':'NOT_RUN_AS_ALL_SCRIPTED_CONDITIONS_AND_DOMAINS'})
write('script-movements',calls);write('scripted-entrances',scripted);write('script-movement-configurations',config)
grouped=collections.defaultdict(list)
for row in scripted:grouped[row['source_map']].append(row)
spawn={3472:(11,8),4164:(24,32),4472:(10,8)}
for row in maps:
 row['scripted_entrance_cases']=grouped[row['id']]
 row['scripted_case_count']=len(grouped[row['id']])
 if row['id']in spawn:row['r26_spawn_room_safety']={'retained_invalid_origin':spawn[row['id']],'change':'Runtime bounded original free-tile fallback. No CSV/map resize. Exact legacy invalid live-position recovery separately verified for4164.','free_tile_test':'PASS_SCOPED_HOST','physical_android':'NOT_RUN'}
write('maps',maps)
summary=json.loads((out/'SUMMARY.json').read_text());summary.update(script_call_sites=len(calls),script_source_files_scanned=len(files),
 scripted_entrance_destination_cases=len(scripted),scripted_unique_source_tiles=len({(s['source_map'],s['x'],s['y'])for s in scripted}),
 scripted_condition_roundtrips='NOT_RUN_AS_FULL_MATRIX; TABLE_WARP10533_SWEEP_IS_SEPARATE',
 configured_movement_rows=len(config),specific_maps_affected_by_repairs=4,spawn_origin_protection_maps=3,
 table_warp_coordinate_rows_changed=0,table_warp_facade_source_rows_repaired=2,
 maps_with_remaining_table_warp_reviews=sum(m['host_entrance_reviews_or_exclusions']>0 for m in maps))
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));(out/'SCRIPT-SOURCE-SCAN.json').write_text(json.dumps({'files':files,'scope':'Conservative source call/definition/comment index. Dynamic expressions and code-only quest/gateway domains remain review; no execution PASS inferred.'},indent=2))
page=out/'map-ledger.html';text=page.read_text();start=text.index('const maps=');end=text.index(';let visible=maps;',start)
warps=json.loads((out/'warps.json').read_text());text=text[:start]+'const maps='+json.dumps(maps,ensure_ascii=False).replace('</','<\\/')+',warps='+json.dumps(warps,ensure_ascii=False).replace('</','<\\/')+text[end:]
text=text.replace('유효 출입구 행 (범위 밖 출발 지도 별도 표시 포함)','테이블 워프 행 (스크립트 문은 각 지도 정보의 별도 목록)')
text=text.replace('for(const p of m.npc_cells)',"for(const s of m.scripted_entrance_cases){ctx.strokeStyle='#ff8090';ctx.strokeRect(s.x*6,s.y*6,6,6)}for(const p of m.npc_cells)")
page.write_text(text);print(json.dumps(summary,ensure_ascii=False,indent=2))
