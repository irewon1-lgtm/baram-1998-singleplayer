#!/usr/bin/env python3
"""Pinned source manifest supplies hashes and URLs; no network or runtime execution."""
from pathlib import Path
import re,json,hashlib,collections,html
import argparse
cli=argparse.ArgumentParser(description='Static official Korean guide fact extraction; does not execute game/server code')
cli.add_argument('--input-dir',type=Path,required=True,help='Private pinned official HTML directory containing acquisition.json')
cli.add_argument('--out-dir',type=Path,required=True,help='P1.5 report directory')
a=cli.parse_args();p=a.input_dir;out=a.out_dir
(out/'selected_content').mkdir(parents=True,exist_ok=True)

manifest=json.loads((p/'acquisition.json').read_text());sources=[];rows=[];excluded_inactive=[]
def clean(s):return ' '.join(html.unescape(re.sub('<[^>]*>',' ',s)).split())
def leaf_rows(s):
 for m in re.finditer(r'<tr\b[^>]*>((?:(?!<tr\b|</table>).)*?)(?:</tr>|(?=<tr\b)|(?=</table>))',s,re.S|re.I):
  cols=re.findall(r'<t[dh]\b[^>]*>((?:(?!<t[dh]\b).)*?)(?:</t[dh]>|(?=<t[dh]\b)|$)',m[1],re.S|re.I)
  yield m,cols,[clean(c) for c in cols]
def emit(src,content,field,val,linea,lineb,selection=None,notes=None,requires=None):
 rid='KRO-'+hashlib.sha256((src['source_id']+content+field+str(linea)).encode()).hexdigest()[:12]
 row=dict(content_id=rid,record_type=field.split('.')[0],entity_name_ko=content,field_path=field,original_value=val,reconstructed_value=None,selected_original_value=selection,selected_for_build=selection is not None,selected_for_p2_technical_input=selection is not None,selected_for_reference=True,source_ids=[src['source_id']],source_family='NEXON_OFFICIAL_GUIDE',source_locator={'url':src['source_path_or_url'],'original_url':src['original_url'],'line_start':linea,'line_end':lineb},input_sha256=src['sha256'],parser_version='p15-official-core-v1',game_region='KR',client_build='UNKNOWN; officialwebsitecapture-era scoped',content_era=src['content_era'],archive_capture_at=src['archive_capture_at'],source_authored_or_modified_at=src['source_authored_or_modified_at'],fact_status='ORIGINAL_VERIFIED',fact_scope='Official published field as captured; not independently measured server mechanics',historical_match='CONTEMPORANEOUS_OFFICIAL_DOCUMENT',selection_state='SELECTED_ONLY_EXPLICIT_FIELDS' if selection is not None else 'UNRESOLVED_SUBFIELD_RETAINED',use_status='IDENTIFIED',new_runtime_binding='NOT_STARTED',test_status='NOT_RUN',consumer_feature=field.split('.')[0],required_implementation=requires or 'Consume selected_original_value only; keep unknown mechanics null; version-scoped data',missing_information='Runtime binding, stable native IDs, exact effect/audio/timing or full server implementation as applicable',notes=notes)
 rows.append(row)
for src in manifest:
 if src['status']!=200:continue
 url=src['original_url'];src['local_private_path']=str(p/Path(src['local_private_path']).name);source_bytes=Path(src['local_private_path']).read_bytes()
 if hashlib.sha256(source_bytes).hexdigest()!=src['sha256']:raise ValueError('Sourcehash mismatch:'+src['source_id'])
 s=source_bytes.decode('cp949')
 for cm in re.finditer(r'<!--.*?-->',s,re.S):
  if re.search(r'<tr|파이어볼',cm[0],re.I):excluded_inactive.append({'source_id':src['source_id'],'line_start':s[:cm.start()].count('\n')+1,'line_end':s[:cm.end()].count('\n')+1,'reason':'HTML_COMMENT_INACTIVE_NOT_DISPLAYED','fragment_sha256':hashlib.sha256(cm[0].encode('cp949')).hexdigest()})
 s=re.sub(r'<!--.*?-->',lambda m:re.sub(r'[^\n]',' ',m[0]),s,flags=re.S)
 if not any(x in url for x in ['/magic/','/dungeon/','/begin/','/start/']):continue
 src['read_status']='FULL_TEXT_SEMANTIC_REVIEW' if '/magic/' in url or '/dungeon/' in url else 'ACQUIRED_TEXT_NOT_ALL_FIELDS_NORMALIZED';src['source_family']='NEXON_OFFICIAL_GUIDE';sources.append(src)
 if '/magic/' in url:
  stem=Path(url).stem;job={'fighter':'전사','thidf':'도적','wizard':'주술사','dosa':'도사','common':'COMMON_FOUR_STARTER_JOBS','seung':'PROMOTED_JOBS'}.get(stem)
  tablerows=list(leaf_rows(s))
  for ri,(m,raw,c) in enumerate(tablerows):
   effectrefs=[];row_end_extra=0
   if len(c)==4 and not c[1] and ri+1<len(tablerows) and len(tablerows[ri+1][2])==1 and re.search(r'레벨\s*\d+',tablerows[ri+1][2][0]):
    effectrefs=re.findall(r'<img[^>]+src=[\"\']([^\"\']+)',raw[1],re.I);c=[c[0],tablerows[ri+1][2][0],c[2],c[3]];row_end_extra=tablerows[ri+1][0].end()-m.end()
   if len(c)==5 and not c[1] and ri+1<len(tablerows) and len(tablerows[ri+1][2])==1 and re.search(r'([가-힣]+)\s*99',tablerows[ri+1][2][0]):
    effectrefs=re.findall(r'<img[^>]+src=[\"\']([^\"\']+)',raw[1],re.I);c=[c[0],tablerows[ri+1][2][0],c[2],c[3]];row_end_extra=tablerows[ri+1][0].end()-m.end()
   if len(c)!=4 or not re.search(r'(?:레벨\s*\d+|(?:[가-힣]+)\s*99)',c[1]):continue
   name,lev,desc,cost=c;level=int(re.search(r'(\d+)',lev)[1]);li=s[:m.start()].count('\n')+1;le=li+s[m.start():m.end()+row_end_extra].count('\n');money=None
   if re.search(r'금전\s*:?\s*필요\s*없음',cost):money=0
   else:
    q=re.search(r'금전\s*:?\s*(\d+)\s*전',cost)
    if q:money=int(q[1])
   material=re.sub(r'금전\s*:?\s*(?:필요\s*없음|\d+\s*전)','',cost);material=re.sub(r'^\s*재료\s*:\s*','',material);ing=[];rem=material
   for q in re.finditer(r'([가-힣][가-힣\s]*?)\s*:?\s*(\d+)\s*개',material):
    ing.append({'item_name_literal':q[1].strip(),'quantity':int(q[2]),'item_id':None});rem=rem.replace(q[0],'')
   rem=re.sub(r'[\s,.:]','',rem).replace('필요','')
   sel={'job':(re.sub(r'\s*99','',lev).strip() if job=='PROMOTED_JOBS' else job),'learn_level':level}
   if money is not None:sel['learn_money']={'value':money,'unit':'전','source_says_no_money':money==0}
   if not rem and ing:sel['ingredients']=ing
   guardian=next((g for g in ['주작','현무','백호','청룡'] if g in desc),None)
   if guardian:sel['guardian']=guardian
   tags=[tag for kw,tag in [('회복','recovery'),('전후좌우','four_adjacent_directions'),('낮은 레벨','strictly_lower_level_target'),('주막','own_country_tavern'),('성황당','ghost_to_shrine'),('사대문','country_four_gates'),('마비','paralysis_related'),('중독','poison_related'),('투명','invisibility_related'),('소환','summon_related'),('체력','hp_related'),('기력','mp_related')] if kw in desc]
   val={**sel,'ingredients_parsed_candidate':ing,'materials_unresolved_tail':rem or None,'effect_tags_candidate':tags,'source_effect_description_sha256':hashlib.sha256(desc.encode()).hexdigest(),'effect_id':None,'sound_id':None,'mana_cost':None,'duration_seconds':None,'cast_delay_ms':None,'target_geometry':None,'success_probability':None,'unresolved_name_alias':name in ['공력증가','최격참주첨(풍뢰)'],'source_name_literal':name,'guide_effect_relative_images':effectrefs,'guide_effect_namespace':'OFFICIAL_GUIDE_2001_NOT_CLIENT_BINARY_ID'}
   emit(src,name,'skill.learning',val,li,le,sel,notes='No original sentence dump. Full source row read; only explicit job/level/money/fully parsed materials/guardian selected. Missing cost tail or source spelling typo retained; no arbitrary defaults. Each dated page remains a distinct candidate; later2001fields preferred only after explicit comparison.')
 if '/dungeon/' in url:
  heading={'north.html':'북방대초원','japan.html':'일본','seung.html':'승급사냥터','12_god.html':'12지신의유적'}.get(url.split('/')[-1],'UNKNOWN')
  heading_positions=[(hm.start(),hm[1].strip()) for hm in re.finditer(r'([가-힣][가-힣, \r\n]{0,40})\s*\(적정\s*레벨',s) if hm[1].strip()]
  for m,raw,c in leaf_rows(s):
   preceding=[x for x in heading_positions if x[0]<m.start()]
   if preceding:heading=preceding[-1][1]
   text=' '.join(c);d=re.search(r'([가-힣,\s]+)\s*\(적정\s*레벨',text)
   if d and d[1].strip():heading=d[1].strip()
   visual_cell_text=c[1] if len(c)==5 else None
   if len(c)==5:c=[c[0],c[2],c[3],c[4]]
   if len(c)!=4 or c[0] in ['주요 서식 생물','주요서식생물','주요 몬스터'] or not re.fullmatch(r'[\d,만억천.? ]*',c[2]):continue
   if not c[0] or c[0] in ['???','?']:continue
   name,desc,xp,item=c;li=s[:m.start()].count('\n')+1;le=li+m[0].count('\n');value=None
   q=re.fullmatch(r'(\d+)만',xp)
   if q:value=int(q[1])*10000
   elif xp.isdigit():value=int(xp)
   elif re.fullmatch(r'(\d+)만(\d+)천',xp):
    qq=re.fullmatch(r'(\d+)만(\d+)천',xp);value=int(qq[1])*10000+int(qq[2])*1000
   drop_probability=None;pd=re.search(r'(\d+)\s*%\s*의?\s*확률',item)
   if pd:drop_probability=int(pd[1])/100
   noitems=item.strip()=='없음';uncertain='?' in item
   itemraw=re.sub(r'<br\s*/?>',',',raw[-1],flags=re.I)
   parts=[] if noitems else [x.strip() for x in re.split(r',|또는',re.sub(r'\d+\s*%\s*의?\s*확률로\s*,?','',clean(itemraw))) if x.strip() and not '?' in x]
   itemnames=[];currency=[];currency_or_item=[]
   for part in parts:
    compact=part.replace(' ','')
    cm=re.fullmatch(r'(\d+|오만|십만|만|일만)전',compact)
    if cm:
     cash={'오만':50000,'십만':100000,'만':10000,'일만':10000}.get(cm[1]);cash=cash if cash is not None else int(cm[1]);currency.append({'amount':cash,'unit':'전','original_literal':part})
    elif compact=='금전':currency.append({'amount':None,'unit':'전','original_literal':part})
    elif compact in ['은전','은전뭉치']:currency_or_item.append(part)
    else:itemnames.append(part)
   nameparts=[clean(x) for x in re.split(r'<br\s*/?>',raw[0],flags=re.I) if clean(x)]
   grouped=len(nameparts)>=3
   sel={'monster_name_literal':name,'region':heading,'possible_item_names':itemnames,'possible_currency_drops':currency,'currency_or_item_unresolved':currency_or_item,'items_list_explicit_none':noitems}
   if grouped:sel['monster_name_group']=nameparts;sel['grouped_variant_mapping']='UNRESOLVED_NOT_SINGLE_ENTITY'
   if value is not None and name.replace(' ','') not in ['백호왕','쥐왕','최강다람쥐']:sel['experience']={'value':value,'unit':'XP'}
   if drop_probability is not None:sel['drop_probability']={'value':drop_probability,'unit':'fraction','scope':'named item only','probability_model':'UNKNOWN','quantity':None}
   # none in a published item column is not an omniscient proof of0% for all item conditions.
   if noitems:sel['none_scope']='officialtablecolumn only; not proven universal0percent'
   if '먼저 공격하지' in desc:sel['aggression']='RETALIATE_ONLY_DOCUMENTED'
   if '체력이 낮아지면 도망' in desc:sel['low_hp_flee']=True
   if '호전적' in desc:sel['aggression_description']='HOSTILE_DOCUMENTED'
   val={**sel,'drop_probability':sel.get('drop_probability'),'quantity':None,'probability_model':'UNKNOWN','no_drop_outcome':None,'spawn_count':None,'spawn_coordinates':None,'spawn_cap':None,'respawn_delay':None,'attack_interval':None,'source_experience_value':value,'experience_field_status':'HOLD_SOURCE_OUTLIER' if name.replace(' ','') in ['백호왕','쥐왕','최강다람쥐'] else ('DOCUMENTED' if value is not None else 'UNKNOWN'),'source_description_sha256':hashlib.sha256(desc.encode()).hexdigest(),'is_boss_documented':'Boss' in desc or 'BOSS' in desc,'source_items_unresolved':'?' in item,'monster_graphic_id':None,'source_item_parts':parts,'source_name_parts':nameparts,'source_visual_column_text':visual_cell_text,'entity_scope':'GROUPED_VARIANTS_NOT_AUTO_PAIRED' if grouped else 'SINGLE_NAMED_ROW','original_reward_alternative_connector':'또는' in item}
   emit(src,name,'monster.documented_reward_behavior',val,li,le,sel,notes='Published table facts, not observation sample. Proper variants/regions separate. Listed items do not imply100percent or independent/exclusive rolls; table없음 only preserved as publishedscope. Native monster/item IDs and full spawn/roll model remain unresolved.')
   if grouped or name=='범형제':
    rows[-1]['selected_for_build']=False;rows[-1]['selection_state']='HOLD_GROUPED_VARIANT_ROWS';rows[-1]['required_implementation']='Resolve10variant/10drop rowspan pairing; do notcreate a combinedmonster/item entity'

# Selection is explicit within an archival guide snapshot, never a global mixed-era default.
profile_groups=collections.defaultdict(list)
for row in rows:
 year=row['archive_capture_at'][:4]
 row['build_profile_id']='KR_GUIDE_'+year+'_SNAPSHOT'
 row['selection_scope']='PROFILE_SCOPED_PUBLISHED_FIELDS_ONLY'
 row['require_profile_dispatch']=True
 row['global_default_selected']=False
 row['target_profile_resolution']='UNRESOLVED'
 row['gameplay_binding_requires_profile_decision']=True
 row['profile_is_client_version']=False
 key=(row['record_type'],row['original_value'].get('job'),re.sub(r'\s+','',row['entity_name_ko']),row['source_locator']['original_url'].split('/')[-1])
 row['variant_group_id']='KRO-VAR-'+hashlib.sha256(repr(key).encode()).hexdigest()[:12]
 profile_groups[key].append(row)
conflicts=[]
for key,group in profile_groups.items():
 if len({r['build_profile_id'] for r in group})<2:continue
 fields=set().union(*(set(r['selected_original_value'] or {}) for r in group))
 for field in sorted(fields):
  vals={json.dumps((r['selected_original_value'] or {}).get(field),ensure_ascii=False,sort_keys=True) for r in group}
  if len(vals)>1:
   conflicts.append({'variant_group_id':group[0]['variant_group_id'],'entity_name_ko':group[0]['entity_name_ko'],'job':key[1],'field':field,'candidates':[{'content_id':r['content_id'],'source_ids':r['source_ids'],'build_profile_id':r['build_profile_id'],'value':(r['selected_original_value'] or {}).get(field)} for r in group],'resolution':'UNRESOLVED_NO_AVERAGE_OR_GLOBAL_DEFAULT'})
(out/'selected_content/kr_official_core.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
(out/'research_official_core.json').write_text(json.dumps({'task_id':'BARAM_REBUILD_P1_5_001','status':'PARTIAL','sources':sources,'records':len(rows),'counts_by_type':dict(collections.Counter(r['record_type'] for r in rows)),'private_acquisition_manifest':str(p/'acquisition.json'),'parser_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_manifest_sha256':hashlib.sha256((p/'acquisition.json').read_bytes()).hexdigest(),'excluded_inactive_source_spans':excluded_inactive,'epoch_conflicts':conflicts,'default_build_profile_id':None,'outputs':[{'path':'kr_official_core.jsonl','sha256':hashlib.sha256((out/'selected_content/kr_official_core.jsonl').read_bytes()).hexdigest(),'bytes':(out/'selected_content/kr_official_core.jsonl').stat().st_size,'records':len(rows)}],'warning':'Sourcecapture dates are not client build dates. Website data can be stale; compare2000and2001actualvalues, do notmerge by averaging.'},ensure_ascii=False,indent=2)+'\n');print(len(rows),dict(collections.Counter(r['record_type'] for r in rows)))
