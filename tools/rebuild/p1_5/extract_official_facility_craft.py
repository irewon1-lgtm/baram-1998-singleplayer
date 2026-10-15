"""Extract explicit archived facility/crafting facts, retaining unknown costs/rates.
No network, reference client/server, game runtime or installer execution.
"""
from pathlib import Path
from lxml import html
import argparse,json,hashlib,re
ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--manifest-sha256',required=True);a=ap.parse_args();base=a.source_dir.resolve();out=a.output_dir.resolve();mb=(base/'acquisition.json').read_bytes()
if hashlib.sha256(mb).hexdigest()!=a.manifest_sha256:raise SystemExit('FAIL: official source manifest fingerprint mismatch')
pages=[p for p in json.loads(mb) if p.get('status')==200 and any(t in p.get('original_url','') for t in ['/zone/','/item/'])]
facility=[];craft=[];notes={}
def text(el):return ' '.join(' '.join(el.itertext()).split())
def rec(p,line,typ,name,v,selected=True):
 profile='KR_GUIDE_'+p['archive_capture_at'][:4]+'_SNAPSHOT'
 return {'content_id':'KRO-'+typ.upper()+'-'+hashlib.sha256((p['source_id']+str(line)+name).encode()).hexdigest()[:14],'record_type':typ,'entity_name_ko':name,'field_path':typ+'.official_documented_semantics','original_value':v,'selected_original_value':v if selected else None,'reconstructed_value':None,'selected_for_build':selected,'build_profile_id':profile,'selection_scope':'DOCUMENTED_FIELDS_WITHIN_CAPTURE_SNAPSHOT_ONLY','require_profile_dispatch':True,'global_default_selected':False,'source_ids':[p['source_id']],'source_family':'NEXON_OFFICIAL_GUIDE_SHARED','source_locator':{'original_url':p['original_url'],'archive_url':p['source_path_or_url'],'archive_capture_at':p['archive_capture_at'],'html_line_start':line},'input_sha256':p['sha256'],'parser_version':'p15-official-zone-item-v1+facility-craft','game_region':'KR','client_build':'UNKNOWN','content_era':'Archived official document captured'+p['archive_capture_at'][:8]+'; not an executable-version inference','fact_status':'ORIGINAL_VERIFIED' if selected else 'UNKNOWN','fact_scope':'Only explicit guide function/material/cost labels; not actual NPC spoken dialogue, measured success rate or complete recipe.','use_status':'IDENTIFIED','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','consumer_feature':typ,'required_implementation':'Profile-specific service/recipe importer; unknown parameters remain null and must not enable a fabricated complete recipe.','missing_information':'Exact NPC dialogue, item/NPC stable IDs, service fee/formula, success probability and failure consumption unless explicitly shown.'}
for p in pages:
 b=(base/Path(p['local_private_path']).name).read_bytes()
 if hashlib.sha256(b).hexdigest()!=p['sha256']:raise SystemExit('FAIL: official page byte mismatch')
 tree=html.fromstring(b.decode('cp949',errors='strict'))
 for tr in tree.xpath('//tr[not(descendant::table)]'):
  cells=[text(x) for x in tr.xpath('./td|./th')];joined=' '.join(x for x in cells if x);ln=tr.sourceline
  if '/item/' in p['original_url'] and len(cells) in [5,7] and cells[0] not in ['이름','무기이름']:
   name,note=cells[0],cells[-1];notes[(p['source_id'],ln)]=(note,cells)
   v=None;selected=True
   if name=='얼음칼' and '99' in note:v={'result_name':name,'operation':'NPC crafting','materials':[{'item_name':'얼음','quantity':99}],'npc_name':'한빙장','npc_location_description':'극지방 입구','quantity_result':None,'money_cost':None,'success_probability':None,'failure_consumption':None,'era_existence_evidence':'Explicit contemporary official2000/2001item description'}
   elif name=='방천가위' and '방천화극' in note:v={'result_name':name,'operation':'crafting','materials':[{'item_name':'방천화극','quantity':2}],'npc_name':None,'npc_location_description':cells[3] if len(cells)==5 else None,'secondary_use':'material for clothing repair','money_cost':None,'success_probability':None,'failure_consumption':None}
   elif name=='백화검' and '은나무' in note:v={'result_name':name,'operation':'ignite/crafting mention','materials':[{'item_name':'은나무 가지','quantity':None},{'item_name':'도깨비들의 부싯돌','quantity':None}],'npc_name':None,'money_cost':None,'success_probability':None,'failure_consumption':None,'alternative_acquisition_documented':{'action':'kill','monster_name':'범천','location':'호굴'},'path_rule':'Craft mention and kill acquisition are preserved as alternative documented claims, not one forced combined recipe.'}
   elif name=='과일화채' and '참수박' in note:v={'result_name':name,'operation':'combination','materials':[{'item_name':'깨끗한 얼음','quantity':None},{'item_name':'참수박','quantity':None}],'npc_name':None,'money_cost':None,'success_probability':None,'failure_consumption':None}
   elif name=='말린지네' and '죽은지네' in note:v={'result_name':name,'operation':'NPC exchange/crafting','materials':[{'item_name':'죽은지네','quantity':7}],'npc_name':None,'npc_location_description':cells[3],'money_cost':None,'listed_price_not_recipe_fee':800,'success_probability':None,'failure_consumption':None}
   elif name=='진호박단추' and '99' in note:v={'result_name':name,'operation':'crafting','materials':[{'item_name':'진호박','quantity':99}],'npc_name':None,'npc_location_description':cells[3],'money_cost':None,'success_probability':None,'failure_consumption':None,'availability':'time-limited; dates/conditions UNKNOWN'}
   elif name=='골무' and '다던데' in note:v={'result_name':name,'operation':'hearsay crafting claim only','materials':[{'item_name':'한왕','quantity':None},{'item_name':'초왕','quantity':None}],'money_cost':None,'success_probability':None,'failure_consumption':None,'source_uncertainty':'Guide explicitly uses hearsay phrasing; not selected as verified recipe'};selected=False
   elif name=='깨끗한얼음' and '씻' in note:v={'result_name':name,'operation':'washing mentioned in item description; executable player recipe not established','materials':[{'item_name':'얼음','quantity':None}],'money_cost':None,'success_probability':None,'failure_consumption':None};selected=False
   elif name=='녹호박' and '재료' in note:v={'material_item_name':'녹호박','material_role':'limited clothing material','result_name':None,'materials_quantity':None,'npc_name':None,'money_cost':None,'success_probability':None,'failure_consumption':None,'availability':'past/limited clothing context; exact event/rule UNKNOWN'}
   if v:craft.append(rec(p,ln,'crafting_fact',name,v,selected))
  if '/zone/' not in p['original_url'] or len(cells)==4 or not joined:continue
  v=None;name=None
  if joined.startswith('주막 ') and '노란비서' in joined:name='주막';v={'new_character_start_place_type':'inn','return_item_documented':'노란비서','return_spell_documented':'귀환','return_place_type':'inn','city_country_rule':None}
  elif joined.startswith('대장간 ') and '수리' in joined:name='대장간';v={'weapon_sales':True,'repair_service':True,'repair_before_item_break_recommended':True,'repair_fee':None,'repair_fee_formula':None,'durability_loss_formula':None,'repairable_item_restrictions':None,'modern_enhancement':None}
  elif joined.startswith('갑옷상점 '):name='갑옷상점';v={'gender_equipment_scope':'male clothing/armour/helmets','interaction_documented':'mouse-click merchant opens menu','upgrade_or_repair_fee':None}
  elif joined.startswith('포목상 '):name='포목상';v={'gender_equipment_scope':'female clothing/armour/helmets','interaction_documented':'mouse-click merchant opens menu','upgrade_or_repair_fee':None}
  elif joined.startswith('시약상점 '):name='시약상점';v={'merchant_group':'hidden vendors in Goguryeo/Buyeo','sells':'potions and some hard-to-find weapons','numeric_fee_or_stock_limit':None}
  elif joined.startswith('우체국 ') and '폐쇄' in joined:name='우체국';v={'open_at_document_capture':False}
  elif joined.startswith('복권상점 ') and '폐쇄' in joined:name='복권상점';v={'open_at_document_capture':False}
  elif joined.startswith('무한장 '):name='무한장';v={'pvp_allowed_here':True,'ordinary_area_pvp_allowed_documented':False,'death_experience_loss_here':False,'death_item_floor_drop_here':False,'team_marker':'clothing dye colour selected at entry','single_player_applicability':'scope decision required; original multiplayer service fact not automatic implementation instruction'}
  elif joined.startswith('혼례식장 '):name='혼례식장';v={'marriage_characters':'opposite-sex characters per document','reward_item':'사랑호출기','reward_function':'teleport to spouse','documented_range':'anywhere per guide; exact regional exceptions UNKNOWN','price':None,'single_player_applicability':'scope decision required'}
  elif joined.startswith('성황당 '):name='성황당';v={'service':'resurrection after death','fee':None,'health_on_resurrection':None,'item_restore_policy':None}
  elif joined.startswith('전투윷방 '):name='전투윷방';v={'player_command_ko':'던진다','paid':True,'fee':None,'outcome':'random monster summoning/combat','probability_table':None}
  elif joined.startswith('주술사길드 '):name='주술사길드';v={'leaders_documented':['해두','처연'],'job_entry':'평민→주술사','learn_menu':'마법배우기','learn_list_filter':'current level','required_level_or_fee':None}
  elif joined.startswith('도적길드 '):name='도적길드';v={'leaders_documented':['마로','마서'],'job_entry':'평민→도적','learning_action':'select skill name in list','learning_requires':'sufficient offerings/materials','required_level_or_material_quantities':None}
  elif joined.startswith('도사길드 '):name='도사길드';v={'leaders_documented':['진선','선후'],'job_entry':'평민→도사','forget_menu':'마법 지우기','required_fee':None}
  elif joined.startswith('전사길드 '):name='전사길드';v={'leaders_documented':['태백','예백'],'job_entry':'평민→전사','teaches_job_skills':True,'required_level_or_fee':None}
  if v:facility.append(rec(p,ln,'facility_rule',name,v))
# Add factual semantics from every item description without republishing flavour prose.
ip=out/'selected_content/kr_official_items.jsonl';items=[json.loads(l) for l in ip.read_text().splitlines()]
for r in items:
 note,cells=notes[(r['source_ids'][0],r['source_locator']['html_line_start'])];v=r['original_value'];tags=[]
 for token,tag in [('체력회복제','restore_hp'),('기력회복제','restore_source_label_기력'),('마력회복제','restore_mp'),('2차승급','second_promotion_material'),('3차승급','third_promotion_material'),('옷수선의 재료','clothing_repair_material')]:
  if token in note:tags.append(tag)
 v['documented_function_tags']=tags
 m=re.search(r'여성용은\s*,?\s*([^.,]+)',note)
 v['female_counterpart_name_documented']=m.group(1).strip() if m else None
 v['repairable_documented']=False if re.search(r'수리\s*(불가|불능|할\s*수\s*없)',note) else None
 v['craft_fact_record_ids']=[c['content_id'] for c in craft if c['entity_name_ko']==r['entity_name_ko'] and c['source_ids']==r['source_ids']]
 v['guide_explanation_not_npc_dialogue']=True
 r['selected_original_value']=v
ip.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in items))
for name,rs in [('facility_rules',facility),('crafting_facts',craft)]:
 (out/'selected_content'/('kr_official_'+name+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rs))
rp=out/'research_official_zone_item.json';r=json.loads(rp.read_text());r['counts'].update(facility_prose_rules=len(facility),crafting_documented_or_uncertain_facts=len(craft),crafting_selected_documented_facts=sum(x['selected_for_build'] for x in craft),crafting_hearsay_or_description_only_unselected=sum(not x['selected_for_build'] for x in craft));r['prose_extraction_scope']={'zone_item_pages_all_read':75,'numeric_repair_fee_or_formula_found':0,'success_probability_found_in_crafting_descriptions':0,'unavailable_rate_or_cost_encoding':'null, not0/50%/70%','item_note_semantics':'All771rows checked for key facts; parsed source-labelled stats/vendor/place/counterpart/function tags, craft facts split into separate typed records. Descriptive prose is not NPC dialogue.','craft_uncertainty':'골무hearsay and 깨끗한얼음washingdescription unselected; time-limited 진호박단추 availability retained, no automatic universally enabled recipe.','acquisition_scope':'Craft material quantities stated here are original document facts; complete recipes/failure-loss/cost still incomplete.'};r['parser_fingerprints'][Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();r['reproduction_commands'].append('python tools/rebuild/p1_5/extract_official_facility_craft.py --source-dir <private-official-dir> --output-dir <new-output-dir> --manifest-sha256 '+a.manifest_sha256);r['outputs']=[]
for name in ['items','services','map_assets','image_bindings','npc_appearance','full_maps','facility_rules','crafting_facts']:
 p=out/'selected_content'/('kr_official_'+name+'.jsonl');b=p.read_bytes();r['outputs'].append({'path':p.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'records':len(b.splitlines())})
rp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'facility_rules':len(facility),'crafting_facts':len(craft),'outputs':r['outputs']},ensure_ascii=False))
