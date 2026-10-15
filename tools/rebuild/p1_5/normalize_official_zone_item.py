from pathlib import Path
from urllib.parse import urljoin,urlparse
from lxml import html
import re,json,hashlib,collections
import argparse
ap=argparse.ArgumentParser(description='Statically normalize official Korean guide rows; no game or network execution.')
ap.add_argument('--source-dir',type=Path,required=True)
ap.add_argument('--output-dir',type=Path,required=True)
ap.add_argument('--manifest-sha256',required=True)
args=ap.parse_args();base=args.source_dir.resolve();repo=args.output_dir.resolve();manifest_bytes=(base/'acquisition.json').read_bytes()
if hashlib.sha256(manifest_bytes).hexdigest()!=args.manifest_sha256:raise SystemExit('FAIL: acquisition manifest fingerprint mismatch')
repo.mkdir(parents=True,exist_ok=True);(repo/'selected_content').mkdir(exist_ok=True)
pages=json.loads(manifest_bytes);pages=[p for p in pages if p.get('status')==200 and any(x in p.get('original_url','') for x in ['/zone/','/item/'])]
def norm(t):return ' '.join(' '.join(t.itertext()).split())
def unknown(s):return not s or s in ['...','…','???','?','????','없음'] or bool(re.fullmatch(r'\?+',s))
def number(s):
 s=s.replace(',','').replace(' ','');m=re.fullmatch(r'([+-]?\d+)(?:전)?',s)
 if m:return int(m[1])
 m=re.fullmatch(r'(\d+)만전',s);return int(m[1])*10000 if m else None

def base_record(p,tr,kind,name):
 line=tr.sourceline;rid='KRO-'+kind.upper()+'-'+hashlib.sha256((p['source_id']+':'+str(line)+':'+name).encode()).hexdigest()[:14]
 return {'content_id':rid,'record_type':kind,'entity_name_ko':name,'original_value':{},'reconstructed_value':None,'selected_original_value':None,'selected_for_build':True,'source_ids':[p['source_id']],'source_family':'NEXON_OFFICIAL_GUIDE_SHARED','source_locator':{'original_url':p['original_url'],'archive_capture_at':p['archive_capture_at'],'final_response_url':p.get('final_response_url'),'html_line_start':line},'input_sha256':p['sha256'],'parser_version':'p15-official-zone-item-v1','game_region':'KR','client_build':'UNKNOWN; not inferred from capture date','content_era':'Official guide document captured '+p['archive_capture_at'][:8]+'; do not extrapolate backwards to1998','source_authored_or_modified_at':p.get('source_authored_or_modified_at'),'fact_status':'ORIGINAL_VERIFIED','fact_scope':'Only the explicitly documented field value in the contemporaneously archived official Korean guide; numeric accuracy and a specific executable build not independently tested.','use_status':'IDENTIFIED','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','selection_state':'SELECTED_DOCUMENTED_FIELDS_IN_CAPTURE_NAMESPACE','build_profile_id':'KR_GUIDE_'+p['archive_capture_at'][:4]+'_SNAPSHOT','selection_scope':'DOCUMENTED_FIELDS_WITHIN_CAPTURE_SNAPSHOT_ONLY','require_profile_dispatch':True,'global_default_selected':False,'selection_constraint':'Do not collapse differing2000/2001rows or infer unavailable parameters; final default-profile conflict resolution separate.','required_implementation':'Version-filtered normalized importer with stable entity-ID resolution and no missing-field defaults.'}
items=[];services=[];maps=[];page_audit=[]
for p in pages:
 b=(base/Path(p['local_private_path']).name).read_bytes();assert hashlib.sha256(b).hexdigest()==p['sha256'];raw=b.decode('cp949',errors='strict');tree=html.fromstring(raw);rows=tree.xpath('//tr[not(descendant::table)]');aud={'source_id':p['source_id'],'url':p['source_path_or_url'],'sha256':p['sha256'],'raw_bytes':len(b),'read_scope':'All direct non-nested table rows, section headings and linked image/archive elements inspected; numerical format checks per row','item_rows':0,'service_rows':0,'unsupported_rows':[]};header=None;section=None
 if '/item/' in p['original_url']:
  for tr in rows:
   cells=tr.xpath('./td|./th');c=[norm(x) for x in cells]
   if not c or not any(c):continue
   if c[0] in ['이름','무기이름'] and len(c) in [5,7]:header=c;continue
   if len(c)<=2 and not any(x.xpath('.//table') for x in cells):
    text=' '.join(x for x in c if x)
    if text:section=text
    continue
   if len(c) not in [5,7] or header is None or len(c)!=len(header):
    if any(c):aud['unsupported_rows'].append({'line':tr.sourceline,'cell_count':len(c),'reason':'row shape/header not mapped'})
    continue
   r=base_record(p,tr,'item',c[0]);images=[{'relative_src':im.get('src'),'original_url':urljoin(p['original_url'],im.get('src')),'alt':im.get('alt'),'html_line':im.sourceline} for im in tr.xpath('.//img[@src]')];v={'display_name_documented':c[0],'section_documented':section,'listed_price':number(c[2]),'listed_price_unit':'전' if '전' in c[2] else None,'price_semantics':'UNSPECIFIED_PRICE_COLUMN; not automatically NPC buy/sell','minimum_level':None,'durability':None,'armor_class':None,'damage_min':None,'damage_max':None,'required_strength':None,'job_restriction_documented':None,'gender_documented':None,'image_links':images,'effects':[],'vendor_role_hints':[],'obtaining_place':None,'raw_numeric_cells':dict(zip(header[2:-1],c[2:-1])),'source_note_sha256':hashlib.sha256(c[-1].encode()).hexdigest()}
   if section:
    mm=re.search(r'(전사|도적|주술사|도사)전용',section.replace(' ',''));v['job_restriction_documented']=mm[1] if mm else '전직업' if '전직업' in section else None
   if '남자' in c[0]:v['gender_documented']='남자'
   elif '여자' in c[0]:v['gender_documented']='여자'
   if len(c)==7:
    if '위력' in header:
     if '5m10' in raw and '사이' in raw:
      m=re.fullmatch(r'(\d+)m(\d+)',c[3].replace(' ',''))
      if m:v['damage_min'],v['damage_max']=int(m[1]),int(m[2])
     v['required_strength']=number(c[5]);v['minimum_level']=number(c[4]);v['armor_class']=None;v['item_kind']='weapon'
    else:
     ac=c[3].replace(' ','');m=re.fullmatch(r'(?:AC)?([+-]?\d+)',ac,re.I);v['armor_class']=int(m[1]) if m else None;v['durability']=number(c[4]);v['minimum_level']=number(c[5]);v['item_kind']='armour_or_accessory'
   else:v['item_kind']='consumable_or_quest_item';v['obtaining_place']=None if unknown(c[3]) else c[3]
   note=c[-1]
   if '전사전용' in note:v['job_restriction_documented']='전사'
   elif '도적전용' in note:v['job_restriction_documented']='도적'
   elif '주술사전용' in note:v['job_restriction_documented']='주술사'
   elif '도사전용' in note:v['job_restriction_documented']='도사'
   elif '전직업공통' in note:v['job_restriction_documented']='전직업'
   for m in re.finditer(r'(체력|마력|기력|힘|민첩|지력|재생력|명중률|명중율|파괴력|마법보호력)\s*([+-])\s*(\d+)(%?)',note):v['effects'].append({'stat_label_documented':m[1],'delta':int(m[3])*(1 if m[2]=='+' else -1),'unit':'percent' if m[4] else 'source_stat_unit_unspecified'})
   for vendor in ['대장간','갑옷점','포목상','주막의 주모','푸줏간','시약상점']:
    if vendor in note or len(c)==5 and vendor in c[3]:v['vendor_role_hints'].append(vendor)
   v['starts_with_item_documented']=True if '게임 시작시에 주어지는' in note else None
   v['use_key_documented']='e' if re.search(r'e\s*키',note,re.I) else None
   r.update(field_path='item.documented_numeric_and_appearance_fields',original_value=v,selected_original_value=v,consumer_feature='items/economy/equipment',requirement_ids=['RQ-069','RQ-074','RQ-075','RQ-121','RQ-146'],missing_information='Stable game itemID/iconEPFID, exact vendor-specific price meaning where column is only 가격, repair cost/eligibility, unknown question-mark values and capture-to-client-build match. Nonstandard AC underscore remains unparsed.')
   items.append(r);aud['item_rows']+=1
 if '/zone/' in p['original_url']:
  active_header=None
  for tr in rows:
   cells=tr.xpath('./td|./th');c=[norm(x) for x in cells]
   if len(c)==4 and c[0] in ['상인','길드대장']:active_header=c;continue
   if len(c)!=4 or not active_header:continue
   r=base_record(p,tr,'npc_service',c[0]);v={'npc_name_or_name_group_documented':c[0],'name_group_relation':'UNRESOLVED_ALIAS_OR_SEPARATE_NPC' if ' ' in c[0] else 'single_documented_name','location_label_documented':None if unknown(c[1]) else c[1],'services':[],'sale_tokens':[],'buy_only_tokens':[],'stock_alias_documented':None,'listed_stock_documented':None,'coordinate_point':None,'coordinate_semantics':None,'source_literal_columns':{active_header[i]:c[i] for i in range(2)}}
   svc=c[2]
   for label,pat in [('storage',r'물품보관'),('repair',r'물품수리'),('weapon_naming',r'이름\s*지어'),('marriage',r'혼례식'),('teach_skill',r'(기술|주술)\s*전수'),('forget_skill',r'(기술|주술)\s*지우기'),('personal_title',r'칭호하사'),('job_change_warrior',r'평민을\s*전사'),('job_change_rogue',r'평민을\s*도적'),('job_change_mage',r'평민을\s*주술사'),('job_change_poet',r'평민을\s*도사'),('go_stones_sale',r'흑돌과 백돌'),('janggi_piece_sale',r'장기\s*알'),('summon_monsters_paid',r'금액.*몹들을\s*불러')]:
    if re.search(pat,svc):v['services'].append(label)
   if svc=='없음':v['services']=[];v['service_none_explicit']=True
   else:v['service_none_explicit']=False
   if active_header[3]=='좌표':
    m=re.fullmatch(r'(\d+)\s*,\s*(\d+)',c[3]);v['coordinate_point']=[int(m[1]),int(m[2])] if m else None;v['coordinate_semantics']='Official guild table coordinate; entrance versus indoor NPC tile not established. No automatic placement.'
   else:
    stock=c[3];alias=re.search(r'(.+?)와\s*동일',stock)
    if alias:v['stock_alias_documented']=alias[1]
    elif stock=='없음':v['listed_stock_documented']=[]
    else:
     split=re.split(r'팔\s*수만\s*있는\s*물건\s*:',stock,maxsplit=1);front=split[0];sm=re.search(r'(?:제한적으로\s*)?사고\s*팔\s*수\s*있는\s*물건\s*:\s*(.*)',front)
     if sm:v['sale_tokens']=[x.strip(' .') for x in re.split('[,.]',sm[1]) if x.strip(' .')]
     else:v['listed_stock_documented']=[x.strip(' .') for x in stock.split(',') if x.strip(' .')]
     if len(split)==2:v['buy_only_tokens']=[x.strip(' .') for x in split[1].split(',') if x.strip(' .')]
     v['trade_restriction_documented']='Specific merchants only for 철단도/철도' if '특정 상인만' in stock else None
   r.update(field_path='npc.documented_location_services_and_stock',original_value=v,selected_original_value=v,consumer_feature='NPC/services/shops/job_change',requirement_ids=['RQ-036','RQ-068','RQ-069','RQ-072','RQ-080','RQ-121','RQ-146'],missing_information='Original NPClook/body/parts/palette/direction/interior tile, spoken dialogue, stable NPC/item IDs and numeric service prices. Stock categories remain categories; aliases require same-capture explicit linkage.')
   services.append(r);aud['service_rows']+=1
  # Link all game imagery and map attachments without claiming geometry or rendered NPC identity.
  for el in tree.xpath('//img[@src]|//a[@href]'):
   href=el.get('src') if el.tag=='img' else el.get('href');u=urljoin(p['original_url'],href);name=urlparse(u).path.rsplit('/',1)[-1]
   if el.tag=='a' and not name.endswith('.zip'):continue
   if el.tag=='img' and (re.search(r'^(blank|ani_|2title_|icon_|menu|back|exit|next)',name) or '/zone/' not in u):continue
   rr=base_record(p,el,'map_or_facility_image',el.get('alt') or name);v={'attachment_original_url':u,'relative_href':href,'image_label':el.get('alt'),'relation':'DIRECT_LINK_FROM_OFFICIAL_ZONE_PAGE','purpose':'map attachment' if name.endswith('.zip') or '/map' in p['original_url'] else 'facility/location screenshot or overview; exact subject pending visual review','acquired_asset_source_id':None,'geometry_cells_or_collision':None};rr.update(field_path='world.official_image_or_attachment_reference',original_value=v,selected_original_value=None,selected_for_build=False,selected_for_reference=True,consumer_feature='NPC appearance/world geometry comparison',requirement_ids=['RQ-027','RQ-036','RQ-121','RQ-134'],missing_information='Image byte/capture/format/visual subject and cell/landmark coordinates; source links do not establish map geometry.');maps.append(rr)
 page_audit.append(aud)
# Exact same-capture alias linkage only; source tells inventory equivalence, not face identity.
for r in services:
 alias=r['original_value']['stock_alias_documented']
 if alias:
  target=next((x for x in services if x['source_ids']==r['source_ids'] and x['entity_name_ko'].split()[0]==alias),None)
  if target:r['original_value']['stock_alias_content_id']=target['content_id'];r['selected_original_value']['stock_alias_content_id']=target['content_id']
for name,data in [('items',items),('services',services),('map_assets',maps)]:
 (repo/'selected_content'/('kr_official_'+name+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data))
report={'task_id':'BARAM_REBUILD_P1_5_001','scope':'All acquired official /zone/ and /item/ pages from shared122page acquisition; document rows and direct links, not original game execution','parser':'p15-official-zone-item-v1','source_pages':page_audit,'counts':{'pages_reviewed':len(pages),'item_rows':len(items),'service_rows':len(services),'map_facility_attachment_refs':len(maps),'unique_item_display_names':len({x['entity_name_ko'] for x in items}),'unique_npc_name_groups':len({x['entity_name_ko'] for x in services})},'source_family_policy':'All two site generations share NEXON_OFFICIAL_GUIDE_SHARED and are not independent corroboration. Each capture row kept separate; no averaging or date-to-executable inference.','selected_value_scope':'Explicit numeric/label/service fields in capture-specific namespace only. Unknown ?, AC underscore, category stock, ambiguity not filled with defaults.','raw_assets_note':'Attachment acquisition handled in separate incremental manifest; final enrichment still required.','runtime_test':'NOT_RUN','fact_limitations':['Contemporaneous official text is original documentation of a value, not actual client/server runtime measurement.','가격 is a listed price unless a specific vendor buy/sell meaning independently linked.','Guild 좌표 is not automatically an indoor NPC tile.','NPC name groups are not automatically aliases or individual location/face records.','Images are private source material, not published assets; direct linkage does not prove EPF/partIDs.']}
(repo/'research_official_zone_item.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['counts'],ensure_ascii=False))

manifest_sources=json.loads(manifest_bytes);page_ids={x['source_id'] for x in page_audit};report['sources']=[]
for x in manifest_sources:
 if x.get('source_id') in page_ids:
  a=dict(x);a.update(source_family='NEXON_OFFICIAL_GUIDE_SHARED',size_bytes=a['byte_length'],read_status='ACQUIRED_DECODED_LEAF_TABLE_ROWS_AND_ATTACHMENT_LINKS_REVIEWED',fact_status='ORIGINAL_VERIFIED',fact_scope='Specific documented fields only; no server runtime/client build extrapolation',use_status='IDENTIFIED',test_status='NOT_RUN',local_private_path=str(base/Path(a['local_private_path']).name));report['sources'].append(a)
report['outputs']=[]
for name in ['kr_official_items.jsonl','kr_official_services.jsonl','kr_official_map_assets.jsonl']:
 f=repo/'selected_content'/name;b=f.read_bytes();report['outputs'].append({'path':name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'records':len(b.splitlines())})
(repo/'research_official_zone_item.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
