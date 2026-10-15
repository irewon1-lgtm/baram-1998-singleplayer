from pathlib import Path
import json,hashlib,re,collections
import argparse
ap=argparse.ArgumentParser(description='Statically bind official image bytes and prepare evidence metadata; no game or network execution.')
ap.add_argument('--source-dir',type=Path,required=True)
ap.add_argument('--output-dir',type=Path,required=True)
ap.add_argument('--assets-manifest-sha256',required=True)
args=ap.parse_args();base=args.source_dir.resolve();assetbase=base/'zone-item-assets';repo=args.output_dir.resolve();reportp=repo/'research_official_zone_item.json';report=json.loads(reportp.read_text());asset_bytes=(assetbase/'FROZEN_assets_acquisition.json').read_bytes()
if hashlib.sha256(asset_bytes).hexdigest()!=args.assets_manifest_sha256:raise SystemExit('FAIL: asset manifest fingerprint mismatch')
assets=json.loads(asset_bytes);assets=sorted(assets,key=lambda a:a['source_id']);good=[a for a in assets if a.get('status')==200];lookup={(a['requested_archive_capture_at'],a['original_url']):a for a in assets};goodsid={a['source_id']:a for a in good}
for a in good:
 a['local_private_path']=str(assetbase/Path(a['local_private_path']).name);b=Path(a['local_private_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==a['sha256'];assert len(b)==a['byte_length']
auditp=assetbase/'FROZEN_assets_acquisition.json'
# Only factual item-to-image links: source table row plus acquired exact request URL asset.
items=[json.loads(l) for l in (repo/'selected_content/kr_official_items.jsonl').read_text().splitlines()];bindings=[];item_link_c=collections.Counter()
for r in items:
 for image in r['original_value']['image_links']:
  a=lookup.get((r['source_locator']['archive_capture_at'],image['original_url']))
  if a is None:item_link_c['NOT_ATTEMPTED']+=1;continue
  if a.get('status')!=200:item_link_c['ACCESS_OR_FORMAT_BLOCKED']+=1;continue
  if not a.get('capture_within_target'):item_link_c['POST_CUTOFF_REFERENCE_ONLY']+=1;continue
  item_link_c['ACQUIRED_WITHIN_TARGET']+=1
  bindings.append({'content_id':'KRO-ICON-'+hashlib.sha256((r['content_id']+a['source_id']).encode()).hexdigest()[:14],'record_type':'item_icon','entity_name_ko':r['entity_name_ko'],'field_path':'item.official_document_image_binding','original_value':{'item_record_id':r['content_id'],'image_source_id':a['source_id'],'image_sha256':a['sha256'],'width':a['width'],'height':a['height'],'frames':a.get('n_frames',1),'table_capture_at':r['source_locator']['archive_capture_at'],'image_actual_capture_at':a['actual_archive_capture_at'],'epf_or_original_sprite_id':None},'selected_original_value':{'item_record_id':r['content_id'],'image_source_id':a['source_id'],'image_sha256':a['sha256']},'reconstructed_value':None,'selected_for_build':True,'selected_for_p2_technical_input':True,'source_ids':r['source_ids']+[a['source_id']],'source_family':'NEXON_OFFICIAL_GUIDE_SHARED','source_locator':{'table':r['source_locator'],'image_html_line':image['html_line'],'image_archive_url':a['final_response_url']},'input_sha256':r['input_sha256'],'parser_version':'p15-official-zone-item-v1','game_region':'KR','client_build':'UNKNOWN','content_era':'Official HTML and image captures separately recorded; both within2000–2001','fact_status':'ORIGINAL_VERIFIED','fact_scope':'Direct named item table-cell→image URL and actual archived image bytes; not an EPF-ID or executable-version proof.','use_status':'IDENTIFIED','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','consumer_feature':'actual item icon selection/reference','required_implementation':'Resolve private image source by persistent manifest; preserve item stable-ID/capture namespace; no replacement icon if absent.','missing_information':'EPF/frame/palette ID and full item repertoire matching; whole-source visual table checking not independent game execution.'})
(repo/'selected_content/kr_official_image_bindings.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in bindings))
# Known named NPCs visually distinguished from lower-screen player/other actors.
subjects=[('태백','검성 태백','P15-ARCASSET-b686ee32bb35',[204,143,232,193],'회색·백색 계열 투구와 갑옷을 입은 중앙 인물'),('해두','현자 해두','P15-ARCASSET-cea7f4fc49ab',[207,149,230,193],'흰 모자와 회색·백색 옷을 입은 중앙 인물'),('마로','태성 마로','P15-ARCASSET-8f44f514dd59',[207,152,230,193],'검은 머리와 어두운 옷·노란 장식의 중앙 인물'),('진선','진선 진선','P15-ARCASSET-15baa2f13413',[204,152,230,194],'밝은 머리와 회색 옷·지팡이 형태가 보이는 중앙 인물')]
sv=[json.loads(l) for l in (repo/'selected_content/kr_official_services.jsonl').read_text().splitlines()];npc=[]
for name,title,sid,bbox,desc in subjects:
 a=goodsid[sid];assert a['capture_within_target'];sr=next(x for x in sv if x['entity_name_ko']==name and x['source_locator']['archive_capture_at'].startswith('2001'))
 npc.append({'content_id':'KRO-NPCLOOK-'+name,'record_type':'npc_appearance_reference','entity_name_ko':name,'field_path':'npc.named_original_screenshot_appearance','original_value':{'visible_title_documented':title,'named_npc_source_service_record_id':sr['content_id'],'location_label_documented':sr['original_value']['location_label_documented'],'screenshot_source_id':sid,'screenshot_sha256':a['sha256'],'screenshot_dimensions':[a['width'],a['height']],'npc_pixel_bbox_xyxy_exclusive':bbox,'bbox_scope':'Manually visually located central named NPC in original full screenshot; lower-screen player/other actors excluded. Not a sprite cutout or tile coordinate.','visible_appearance_description_ko':desc,'screen_facing':'toward screen bottom; numeric direction index UNKNOWN','original_look_id':None,'body_head_clothing_weapon_ids':None,'palette_id':None,'frame_or_motion_id':None},'selected_original_value':{'screenshot_source_id':sid,'screenshot_sha256':a['sha256'],'npc_pixel_bbox_xyxy_exclusive':bbox},'reconstructed_value':None,'selected_for_build':False,'selected_for_reference':True,'selected_for_p2_technical_input':True,'source_ids':[sid]+sr['source_ids'],'source_family':'NEXON_OFFICIAL_GUIDE_SHARED','source_locator':{'screenshot_archive_url':a['final_response_url'],'image_actual_capture_at':a['actual_archive_capture_at'],'service_table':sr['source_locator'],'pixel_bbox':bbox},'input_sha256':a['sha256'],'parser_version':'p15-official-zone-item-v1+manual-visual-review','game_region':'KR','client_build':'UNKNOWN','content_era':'Actual screenshot archive captures2001; source exact build not established','fact_status':'ORIGINAL_VERIFIED','fact_scope':'Named screen image/appearance reference only. Sprite/part IDs, all directions, motion and all NPC restoration remain unresolved.','use_status':'IDENTIFIED','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','consumer_feature':'NPC identity/appearance P2 reference comparison','required_implementation':'Compare original body/head/mons frames against this named screenshot; never apply one job master face to other same-role NPCs.','missing_information':'Original entity/look/parts/palette/frame IDs, exact anchor/layers, other directions/motion. Guild table coordinate remains facility point, not this screenshot NPC tile.'})
(repo/'selected_content/kr_official_npc_appearance.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in npc))
# Enrich every official zone link with explicit asset result, never equating a thumbnail to a full map.
mp=repo/'selected_content/kr_official_map_assets.jsonl';maps=[json.loads(l) for l in mp.read_text().splitlines()]
for r in maps:
 v=r['original_value'];a=lookup.get((r['source_locator']['archive_capture_at'],v['attachment_original_url']))
 if a:
  v['asset_access_status']=a['status'];v['acquired_asset_source_id']=a['source_id'] if a.get('status')==200 else None;v['actual_archive_capture_at']=a.get('actual_archive_capture_at');v['capture_within_target']=a.get('capture_within_target');v['byte_sha256']=a.get('sha256') if a.get('status')==200 else None
  if a.get('status')==200:
   r['source_ids']=list(dict.fromkeys(r['source_ids']+[a['source_id']]));v['dimensions']=[a.get('width'),a.get('height')];r['selected_for_p2_technical_input']=True
   if '/s_ko_' in a['original_url'] or '/s_bu_' in a['original_url']:v['purpose']='90x90 city-map thumbnail tile in documented3x3 HTML grid; useful only for broad landmark comparison, not full PCX/cell geometry';v['grid_label']=re.search(r's_(ko|bu)_(\d)(\d)',a['original_url']).groups();v['geometry_cells_or_collision']=None
   elif a['source_id'] in [s[2] for s in subjects]:v['visual_review']='Named central guild NPC confirmed; see kr_official_npc_appearance.jsonl'
   elif '/map' in r['source_locator']['original_url'] and a.get('width')==290:v['visual_review']='Graph of linked castles, not a city terrain map; some graph parts captured2002 kept reference only.'
  else:
   diagnostic=' Direct attachment blocked or malformed; failure is this path only, not source nonexistence.'
   if diagnostic not in r['missing_information']:r['missing_information']+=diagnostic
 else:v['asset_access_status']='NOT_ATTEMPTED'
mp.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in maps))
# Frozen source catalogue of acquired bytes. Blocked attempts remain separate and not presented as acquired input.
source_pages=[s for s in report['sources'] if s.get('source_type')=='ARCHIVED_OFFICIAL_GUIDE'];asset_sources=[]
for a in good:
 d=dict(a);d.update(source_type='ARCHIVED_OFFICIAL_ATTACHMENT',source_family='NEXON_OFFICIAL_GUIDE_SHARED',size_bytes=a['byte_length'],fact_status='ORIGINAL_VERIFIED' if a.get('capture_within_target') else 'UNKNOWN',fact_scope='Actual archived image bytes/format; semantic subject only separately reviewed; actual capture date differs from parent requested date.',use_status='DECODED',test_status='NOT_RUN',read_status='ACQUIRED_IMAGE_HEADER_AND_PIXEL_DECODED; manual named NPC subset4 and map thumbnails inspected')
 asset_sources.append(d)
report['sources']=source_pages+asset_sources;report['asset_acquisition']={'requests_expected':828,'receipts_checked':len(assets),'acquired_decoded':len(good),'capture2001':sum(a.get('actual_archive_capture_at','').startswith('2001') for a in good),'capture2002_reference_only':sum(a.get('actual_archive_capture_at','').startswith('2002') for a in good),'attempts_without_decoded_asset':len(assets)-len(good),'access_blocked':sum(a.get('status')!=200 and not a.get('byte_length') for a in assets),'format_failed':sum(a.get('status')!=200 and bool(a.get('byte_length')) for a in assets),'blocked_reason_counts':dict(collections.Counter(a.get('error','UNKNOWN') for a in assets if a.get('status')!=200)),'map_pcx_zip_acquired':sum(a.get('kind')=='ZIP_MAP_ATTACHMENT' for a in good),'map_zip_attempts':18,'city_map_thumbnails_acquired':sum('/s_ko_' in a['original_url'] or '/s_bu_' in a['original_url'] for a in good),'frozen_private_manifest':str(auditp),'frozen_private_manifest_sha256':hashlib.sha256(auditp.read_bytes()).hexdigest(),'failure_scope':'585proxy-tunnel403 is transport access failure; origin404/formats separately retained. No missing-source conclusion or bypass attempted.'};report['blocked_asset_attempts']=[a for a in assets if a.get('status')!=200];report['counts'].update(item_image_links=dict(item_link_c),item_icon_bindings=len(bindings),named_npc_appearances_visually_identified=len(npc),known_npc_name_groups_from_service_tables=22,full_original_npc_population='UNKNOWN');report['visual_review']={'named_guild_npcs':subjects,'facility_contact_sheet_private':str(assetbase/'facility-guild-contact.png'),'map_thumbnail_contact_sheet_private':str(assetbase/'ko-map-tiles-contact.png'),'scope':'4specific named NPC screenshots,9Koguryo thumbnails and castle graph3images manually viewed; remaining successful203images pixel decoded/metadata checked, not all semantically reviewed.','parts_lookup_status':'Requested static comparison from kr_assets; unresolved until evidence returned.'};report['raw_assets_note']='203source images retained privately with actual capture dates; only metadata and normalized facts go into public source.18PCX links blocked;18thumbnail images do not establish complete city cells/terrain/collision.';report['outputs']=[]
for f in [repo/'selected_content'/('kr_official_'+n+'.jsonl') for n in ['items','services','map_assets','image_bindings','npc_appearance']]:
 b=f.read_bytes();report['outputs'].append({'path':f.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'records':len(b.splitlines())})
report['freeze_status']='FROZEN_FOR_INTEGRATION_20261016';reportp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
# Scope/shape checks, not historical/runtime proof.
ids=set();rowcount=0
for o in report['outputs']:
 f=repo/'selected_content'/o['path'];b=f.read_bytes();assert hashlib.sha256(b).hexdigest()==o['sha256'];rs=[json.loads(l) for l in b.decode().splitlines()];assert len(rs)==o['records']
 for r in rs:
  assert r['content_id'] not in ids;ids.add(r['content_id']);rowcount+=1;assert r['test_status']=='NOT_RUN';assert r['new_runtime_binding']=='NOT_STARTED'
  for sid in r['source_ids']:assert any(s['source_id']==sid for s in report['sources']),sid
assert len(assets)==828;assert len(good)==203;assert len(npc)==4
print(json.dumps({'outputs':report['outputs'],'rows':rowcount,'sources':len(report['sources']),'assets':report['asset_acquisition'],'icon_binding_counts':dict(item_link_c)},ensure_ascii=False)[:6500])

# Additional real full-map attachments discovered through an alternate CDX prefix.
# These differ from the18failed fragment URLs. A CRC mismatch stays FAIL and is
# never converted to a usable PCX merely because the ZIP bytes were acquired.
from PIL import Image
from io import BytesIO
import zipfile
alt_path=assetbase/'alternate_map_acquisition.json'
alt_bytes=alt_path.read_bytes()
alt_expected=(assetbase/'alternate_map_acquisition.sha256').read_text().strip()
if hashlib.sha256(alt_bytes).hexdigest()!=alt_expected:raise SystemExit('FAIL: alternate map manifest fingerprint mismatch')
alts=json.loads(alt_bytes);fullmaps=[];alt_catalog=[]
for a in alts:
 a=dict(a);a['local_private_path']=str(assetbase/Path(a['local_private_path']).name)
 if a.get('sha256'):
  b=Path(a['local_private_path']).read_bytes()
  if len(b)!=a['size_bytes'] or hashlib.sha256(b).hexdigest()!=a['sha256']:raise SystemExit('FAIL: alternate map ZIP size/hash mismatch')
 if a.get('status')!=200:
  a.update(status='FAIL_ARCHIVE_MEMBER_CRC' if 'CRC' in a.get('error','') else a.get('status'),access_status='ACQUIRED' if a.get('sha256') else 'BLOCKED',format_validation='FAIL' if 'CRC' in a.get('error','') else 'NOT_RUN',fact_status='UNKNOWN',use_status='ACQUIRED' if a.get('sha256') else 'DISCOVERED',test_status='NOT_RUN',selected_for_build=False,exclusion_reason='Acquired ZIP member CRC mismatch; original bytes preserved privately, PCX not adopted.')
  alt_catalog.append(a);continue
 z=zipfile.ZipFile(BytesIO(b));zi=z.infolist()
 if len(zi)>100 or sum(x.file_size for x in zi)>100000000:raise SystemExit('FAIL: map archive extraction limits')
 for m in a['members']:
  bb=z.read(m['archive_member'])
  if len(bb)!=m['size_bytes'] or hashlib.sha256(bb).hexdigest()!=m['sha256']:raise SystemExit('FAIL: map PCX size/hash mismatch')
  im=Image.open(BytesIO(bb));im.load()
  if [im.width,im.height]!=[m['width'],m['height']]:raise SystemExit('FAIL: map image dimensions mismatch')
  original_name=m['archive_member'].encode('cp437').decode('cp949',errors='strict')
  fullmaps.append({'content_id':'KRO-FULLMAP-'+a['source_id'].split('-')[-1],'record_type':'official_full_map_image','entity_name_ko':original_name,'field_path':'world.official_target_period_map_image_reference','original_value':{'archive_member_raw_cp437':m['archive_member'],'archive_member_decoded_cp949':original_name,'archive_member_sha256':m['sha256'],'archive_member_size_bytes':m['size_bytes'],'format':im.format,'width':im.width,'height':im.height,'mode':im.mode,'city_label_documented':'고구려','image_scope':'Full official pictorial city/landscape map with facility symbols; manually viewed1451 and978pixel versions.','client_map_id':None,'tile_grid_dimensions':None,'origin_or_scale_in_game_cells':None,'collision_or_exits':None},'selected_original_value':{'source_id':a['source_id'],'archive_member_decoded_cp949':original_name,'archive_member_sha256':m['sha256'],'width':im.width,'height':im.height},'reconstructed_value':None,'selected_for_build':False,'selected_for_reference':True,'selected_for_p2_technical_input':True,'source_ids':[a['source_id']],'source_family':'NEXON_OFFICIAL_GUIDE_SHARED','source_locator':{'archive_url':a['final_response_url'],'actual_archive_capture_at':a['actual_archive_capture_at'],'archive_member':original_name},'input_sha256':a['sha256'],'parser_version':'p15-official-zone-item-v1+bounded-zip-pcx','game_region':'KR','client_build':'UNKNOWN; capture date does not specify executable version','content_era':'Official archived20010612map attachment','fact_status':'ORIGINAL_VERIFIED','fact_scope':'Official target-period map image bytes and depicted landscape reference, not a verified MAP tile/collision conversion. Two sizes are related representations, not independent sources.','use_status':'IDENTIFIED','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','consumer_feature':'P2-01 Korean map/landmark comparison reference','required_implementation':'Compare KR125map candidates and landmarks against these original images, determine independent scale/origin; do not infer collision/exits from decorative labels.','missing_information':'Exact Korean MAP file, cell/grid correspondence, source executable build, full exits/spawn/interior coordinates. Bu full-map image remains CRCFAIL.'})
 a.update(format_validation='PASS',capture_within_target=True);alt_catalog.append(a)
(repo/'selected_content/kr_official_full_maps.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in fullmaps))
report['sources']+=alt_catalog
report['alternate_map_acquisition']={'manifest_private_path':str(alt_path),'manifest_sha256':hashlib.sha256(alt_bytes).hexdigest(),'new_valid_paths_attempted':3,'full_map_zip_crc_and_image_decode_pass':2,'acquired_zip_member_crc_fail':1,'pcx_images':len(fullmaps),'repeated_fragment_requests':0,'interpretation':'2original full Korean map images supplement18thumbnails; CRC-damaged BuZIP retained withFAIL, not counted as an absent source or adoptedimage.'}
# Explicit profile dispatch, with no implicit mixed global game default.
names=['items','services','map_assets','image_bindings','npc_appearance','full_maps']
for n in names:
 f=repo/'selected_content'/('kr_official_'+n+'.jsonl');rs=[json.loads(l) for l in f.read_text().splitlines()]
 for r in rs:
  v=r.get('original_value') or {};loc=r.get('source_locator') or {}
  ts=v.get('image_actual_capture_at') or v.get('actual_archive_capture_at') or loc.get('image_actual_capture_at') or loc.get('actual_archive_capture_at') or loc.get('archive_capture_at') or (loc.get('table') or {}).get('archive_capture_at')
  year=str(ts)[:4] if ts else 'UNKNOWN';profile='KR_GUIDE_'+year+'_SNAPSHOT' if year in ['2000','2001'] else 'POST_CUTOFF_REFERENCE_'+year
  r.update(build_profile_id=profile,selection_scope='DOCUMENTED_FIELDS_WITHIN_CAPTURE_SNAPSHOT_ONLY',require_profile_dispatch=True,global_default_selected=False)
  if profile.startswith('POST_CUTOFF'):
   r['selected_for_build']=False;r['selected_for_reference']=True
 f.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rs))
report['outputs']=[]
for n in names:
 f=repo/'selected_content'/('kr_official_'+n+'.jsonl');b=f.read_bytes();report['outputs'].append({'path':f.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'records':len(b.splitlines())})
report['global_default_build_profile']=None
report['selection_profile_policy']='KR_GUIDE_2000_SNAPSHOT and KR_GUIDE_2001_SNAPSHOT are separate capture namespaces; required profile dispatch, no global mixed content default. Post2001images reference only. Existing2001-end proposal remains unfrozen.'
report['counts']['full_map_image_references']=len(fullmaps)
report['visual_review']['parts_lookup_status']='Bounded exactRGB comparison against7136MonsterEPFframes returned0exactmatches for all4namedcrops (fittingcandidates2600/1638/1061/1439); no lookIDadopted. Body/headcomposition,recolor,GIFquantization outside scope; no sourceabsence claim.'
report['visual_review']['parts_lookup_evidence_private']='private-research-assets/npc_frame_comparison.json'
report['asset_acquisition']['alternate_zip_results']='3additionalvalidURLs:2CRC/imagePASS,1memberCRCFAIL; original828request counts unchanged.'
report['parser_fingerprints']={str(Path(__file__).name):hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'normalize_official_zone_item.py':hashlib.sha256(Path(__file__).with_name('normalize_official_zone_item.py').read_bytes()).hexdigest()}
report['input_manifest_fingerprints']={'acquisition.json':hashlib.sha256((base/'acquisition.json').read_bytes()).hexdigest(),'FROZEN_assets_acquisition.json':args.assets_manifest_sha256,'alternate_map_acquisition.json':alt_expected}
report['reproduction_commands']=['python tools/rebuild/p1_5/normalize_official_zone_item.py --source-dir <private-official-dir> --output-dir <new-output-dir> --manifest-sha256 '+report['input_manifest_fingerprints']['acquisition.json'],'python tools/rebuild/p1_5/finalize_official_zone_item.py --source-dir <private-official-dir> --output-dir <new-output-dir> --assets-manifest-sha256 '+args.assets_manifest_sha256]
report['source_access_note']='Raw HTML/images/ZIPs/PCX remain private. Reproduction resolves flat basename below provided source-dir and verifies input/asset manifest and every consumed byte hash. Source collection network requests are not part of these static tools.'
report['freeze_status']='FROZEN_FOR_INTEGRATION_20261016_FINAL'
reportp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'final_outputs':report['outputs'],'sources':len(report['sources']),'full_map_images':len(fullmaps),'crc_fail':1,'global_default':None},ensure_ascii=False))
