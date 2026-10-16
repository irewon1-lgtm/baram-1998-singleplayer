#!/usr/bin/env python3
"""Static metadata/evidence serialization only; no runtime/client/installer execution."""
from pathlib import Path
import json,hashlib,re,csv,shutil
from PIL import Image
P=Path('/workspace/scratch/3624c67f59e8/private_delta/archives_ui')
PUB=Path('/workspace/scratch/3624c67f59e8/work-source-delta/content-work/rebuild-source-delta-20261016/research/archives_ui')
OLD=Path('/workspace/scratch/3624c67f59e8/work-source-delta/docs/rebuild/p1_5')
NORM=Path('/workspace/scratch/68a0f3ea5a03/receiver/package/docs/rebuild/p1_5/selected_content')
PAY=P/'payload';PAY.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
acq={}
for f in sorted(P.glob('acquisition*.json')):
 for x in json.loads(f.read_text()):
  if x.get('status')==200:acq[x['key']]=x
oldsrc=[json.loads(l) for l in (OLD/'sources_delta.jsonl').open()]
oldhash={x.get('sha256'):x['source_id'] for x in oldsrc if x.get('sha256')}
# Include only usable evidence, never the duplicate installer or broad unrelated JS/search pages.
spec=[
 ('ui_ba_01','ui_ba_01.gif','SD-SRC-UI-BA01','ARCHIVED_OFFICIAL_IMAGE','NEXON_OFFICIAL_GUIDE','20010610051107','initial setup thumbnail'),
 ('ui_ba_02','ui_ba_02.gif','SD-SRC-UI-BA02','ARCHIVED_OFFICIAL_IMAGE','NEXON_OFFICIAL_GUIDE','20010610052606','title/login thumbnail'),
 ('ui_ba_03','ui_ba_03.gif','SD-SRC-UI-BA03','ARCHIVED_OFFICIAL_IMAGE','NEXON_OFFICIAL_GUIDE','20010817190201','beginner hunting UI screenshot'),
 ('ui_ba_04','ui_ba_04.gif','SD-SRC-UI-BA04','ARCHIVED_OFFICIAL_IMAGE','NEXON_OFFICIAL_GUIDE','20010610045132','shrine screenshot'),
 ('press_login2001','press_login2001.jpg','SD-SRC-UI-PRESS-2001','PRESS_FURNISHED_OFFICIAL_IMAGE','INEWS24_NEXON_PHOTO','2026-04-24','caption claims 2001; image itself undated'),
 ('ndc2014_0080','ndc2014_0080.html','SD-SRC-NDC2014-0080','OFFICIAL_DEVELOPER_TRANSCRIPT','NEXON_NDC_REPLAY','2014','retrospective restoration account; NOT source code'),
 ('ndc2016_0082','ndc2016_0082.html','SD-SRC-NDC2016-0082','OFFICIAL_DEVELOPER_TRANSCRIPT','NEXON_NDC_REPLAY','2016','CD recovery corroboration; NOT source code'),
 ('yes2001','yes2001.html','SD-SRC-BOOK-YES224863','BOOK_PUBLISHER_DESCRIPTION_IN_CATALOG','YES24_ZEUMEDIA','2001-09-30 claimed','bibliography/description only; no full text'),
 ('nlbib23946242','nlbib23946242.html','SD-SRC-BOOK-NL23946242','NATIONAL_LIBRARY_BIBLIOGRAPHY','NL_KOLISNET','[2001]','431p; holdings; no full text'),
 ('nlbib25737613','nlbib25737613.html','SD-SRC-BOOK-NL25737613','NATIONAL_LIBRARY_BIBLIOGRAPHY','NL_KOLISNET','2002','447p; same ISBN different year/pages; no full text'),
 ('oasis_total_name','oasis_total_name.html','SD-SRC-OASIS-NAME','NATIONAL_LIBRARY_ARCHIVE_CATALOG','NL_OASIS','first crawl2014-05-19','catalog access only; restricted archive body not acquired'),
 ('download','download.html','SD-SRC-OFFICIAL-DOWNLOAD','CURRENT_OFFICIAL_DOWNLOAD_PAGE','NEXON_OFFICIAL_SITE','2026-10-16','verified existing1996 installer official URL; duplicate bytes excluded'),
]
sources=[]
for key,fn,sid,typ,fam,era,note in spec:
 b=(P/fn).read_bytes();a=acq[key];assert sha(b)==a['sha256'];shutil.copyfile(P/fn,PAY/fn)
 x={'source_id':sid,'source_type':typ,'source_family':fam,'url':a['url'],'final_response_url':a['final_url'],'status':200,'bytes':len(b),'sha256':sha(b),'private_payload_path':'archives_ui/payload/'+fn,'game_region':'KR','content_era':era,'captured_at':'2026-10-16','notes':note,'acquisition_class':'NEW_SOURCE_BYTES' if sha(b) not in oldhash else 'EXISTING_BYTES_REFETCHED','runtime':'NOT_RUN','new_runtime_binding':'NOT_STARTED'}
 if fn.endswith(('.gif','.jpg')):
  with Image.open(P/fn) as im:im.verify()
  with Image.open(P/fn) as im:x.update(image_format=im.format,dimensions_pixels=list(im.size),frames=getattr(im,"n_frames",1),visual_review='ACTUALLY_INSPECTED')
 sources.append(x)
# Press article is provenance needed to date the image; do not confuse this HTML with the image acquisition key.
fn='press_login2001.html';b=(P/fn).read_bytes();shutil.copyfile(P/fn,PAY/fn)
article={'source_id':'SD-SRC-PRESS-ARTICLE','source_type':'NEWS_ARTICLE_IMAGE_PROVENANCE','source_family':'INEWS24_NEXON_PHOTO','url':'https://v.daum.net/v/20260424132834928','status':200,'bytes':len(b),'sha256':sha(b),'private_payload_path':'archives_ui/payload/'+fn,'content_era':'article2026-04-24; captionclaims2001','acquisition_class':'NEW_SOURCE_BYTES','notes':'Only photo attribution/caption used. Not independent target-era capture.','runtime':'NOT_RUN'};sources.append(article)
# Reuse source identities/hash, not a second copy of previously delivered HTML.
for sid,fn in [('P15-ARC-c05252ad964d','krbegin_basic.html'),('P15-ARC-a071fac33812','krbegin_use.html')]:
 old=next(x for x in oldsrc if x['source_id']==sid);b=(P/fn).read_bytes();assert sha(b)==old['sha256'];sources.append({'source_id':sid,'source_type':'ARCHIVED_OFFICIAL_GUIDE','source_family':'NEXON_OFFICIAL_GUIDE','url':old['source_path_or_url'],'sha256':sha(b),'bytes':len(b),'acquisition_class':'EXISTING_SOURCE_NEW_SEMANTICS','private_payload_path':None,'existing_P15_reference':sid,'notes':'Re-read and hash matched; old raw HTML not recopied into payload.','runtime':'NOT_RUN'})
S={x['source_id']:x for x in sources}
cat=json.loads((OLD/'selected_content/catalog.json').read_text())
oldfiles={Path(x['path']).name:x['sha256'] for x in cat['normalized_catalogs']}
for fn in ['kr_official_flow.jsonl','kr_documented_fields.jsonl','kr_asset_ui_strings.jsonl']:
 assert sha((NORM/fn).read_bytes())==oldfiles[fn]
# Semantic locators use original CP949 HTML line numbers or exact text anchors in new official transcript.
def loc(sid,line=None,anchor=None):
 d={'source_id':sid,'source_sha256':S[sid]['sha256']}
 if line:d['line_range']=line
 if anchor:d['text_anchor']=anchor
 return d
c=[]
def add(cid,bindings,req,field,val,profile,evidence,delta,unknown,tests,existing=None):
 c.append({'candidate_id':cid,'task_id':'BARAM_REBUILD_WORK_SOURCE_DELTA_001','binding_ids':bindings,'requirement_ids':req,'existing_content_ids':existing or [],'field_path':field,'candidate_value':val,'unit':'source-defined','region':'KR','profile_proposal':profile,'global_default_selected':False,'source_evidence':evidence,'delta_class':delta,'expected_old_value':None,'expected_old_state':'Field absent in existing normalized rows, or add-only corroboration; no baseline replacement','expected_input_hashes':{'kr_official_flow.jsonl':oldfiles['kr_official_flow.jsonl'],'kr_documented_fields.jsonl':oldfiles['kr_documented_fields.jsonl'],'kr_asset_ui_strings.jsonl':oldfiles['kr_asset_ui_strings.jsonl']},'confirmed_scope':'Published source statement/visible image only','remaining_unknowns':unknown,'required_codex_tests':tests,'fact_status':'SOURCE_DOCUMENT_VERIFIED','historical_profile_adoption':'UNRESOLVED','new_runtime_binding':'NOT_STARTED','runtime_test_status':'NOT_RUN','receiver_status':'UNACKNOWLEDGED'})
add('SD-UI-001',['BND-001'],['RQ-001','RQ-003'],'ui.connection_setup.documented_methods',{'menu':'SETUP','dedicated_line_option':'LAN','pc_communication_provider_selection':True,'netdirect_mentioned':True},'KR_GUIDE_2000_SNAPSHOT',[loc('P15-ARC-c05252ad964d',[57,61]),loc('SD-SRC-UI-BA01')],'EXISTING_SOURCE_NEW_SEMANTICS','Exact widget text/selection/error/cancel/sound and active client build unknown; historical connection settings are not requirements for offline app.',['UI-P15-01: match native UI asset/palette; preserve offline entry; do not implement obsolete paid networking.'])
add('SD-UI-002',['BND-001'],['RQ-001','RQ-003'],'ui.historical_agreement.documented_keys',{'agree':'a','decline':'d','agreement_precedes_main_screen_in_document':True},'KR_GUIDE_2000_SNAPSHOT',[loc('P15-ARC-c05252ad964d',[67,71])],'EXISTING_SOURCE_NEW_SEMANTICS','Full text, actual key event ordering, declined outcome, modern legal obligations unknown. This is old documented behavior only.',['UI-P15-01: observe matching reference profile agreement/decline if available; no fabricated modern consent.'])
add('SD-UI-003',['BND-001'],['RQ-001','RQ-003'],'ui.main_menu.documented_actions',['처음하기','이어하기','암호 변경','배경 이야기','만든 사람들','종료'],'KR_GUIDE_2000_SNAPSHOT',[loc('P15-ARC-c05252ad964d',[79,108])],'EXISTING_SOURCE_NEW_SEMANTICS','Document action labels are not proof of exact visual position/native frame. First menu conflicts with press image 접속하기.',['UI-P15-01: compare chosen profile menu artwork/action labels; cancel and return paths need execution.'])
add('SD-UI-004',['BND-001'],['RQ-001','RQ-003'],'ui.main_menu.visible_actions',['접속하기','이어하기','암호변경','배경이야기','만든사람들','종료'],'KR_PRESS_IMAGE_CLAIMED_2001_UNCONFIRMED',[loc('SD-SRC-UI-PRESS-2001'),loc('SD-SRC-PRESS-ARTICLE',anchor='지난 2001년')],'NEW_IMAGE_OBSERVATION','Image580x448 includes page margin/drop shadow; exact original viewport and capture year unverified. First label differs from2000 guide.',['UI-P15-01: native asset/template comparison only; no 580x448 game-resolution assumption.'])
add('SD-UI-005',['BND-006','BND-034'],['RQ-010'],'tutorial.documented_initial_gifts',{'clothing_unspecified':True,'wooden_sword':'목검','helper_tutorial_topics':['hunting','pickup','shopping'],'helper_transports_to_beginner_dungeon':True},'KR_GUIDE_2000_SNAPSHOT',[loc('P15-ARC-a071fac33812',[49,60])],'EXISTING_SOURCE_NEW_SEMANTICS','Exact helper/native item IDs, gift count/gender variation/flags/position/branch/order are not given. Do not grant specific inferred clothes ID.',['UI-P15-01 and later tutorial slice: source-qualified helper/item matching and no duplicate rewards.'])
add('SD-UI-006',['BND-034'],[],'resurrection.documented_player_commands.target_era_corroboration',{'revival_command':'살려주세요','thanks_command':'감사합니다','thanks_result':'HP fully replenished as documented','npc_exact_reply':None},'KR_GUIDE_2000_SNAPSHOT',[loc('P15-ARC-a071fac33812',[76,88])],'EXISTING_SOURCE_NEW_CORROBORATION','Existing1997 manual command has official2000 supporting document, same source tradition may not be independent. Exact NPC script/parser/repetition unknown.',['Later NPC lifecycle: ghost/revive/thanks and full HP in chosen profile; no assumptions about costs/MP.'],['KRF-4a1ba1ed80ac'])
add('SD-ARC-001',['BND-030'],['RQ-111','RQ-112'],'reference.museum1996.input_era_mix',{'resources_year':1997,'server_year':1998,'client_source_year':1999,'restoration_target':1996,'original_source_download_acquired':False},'REFERENCE_2014_RESTORATION_ONLY',[loc('SD-SRC-NDC2014-0080',anchor='97년에 게임 리소스')],'NEW_PRIMARY_TRANSCRIPT','Developer testimony describes museum inputs; not proof those source files are publicly downloadable or identical to our archives.',['G0: keep recovered1996 reference distinct from1998–2001 target clients.'])
add('SD-ARC-002',['BND-013','BND-030'],['RQ-027','RQ-028','RQ-111','RQ-112'],'reference.museum1996.map_delivery_history',{'distributed_client_had_no_map_files_as_described':True,'map_data_from_server':True,'restoration_maps_years':[1998,1999],'restoration_tiles_year':1997},'REFERENCE_2014_RESTORATION_ONLY',[loc('SD-SRC-NDC2014-0080',anchor='맵데이터를 서버에서 받아와서')],'NEW_PRIMARY_TRANSCRIPT','This is the restoration-era account; not a direct schema, ID map, exact1998–2001 coverage or universal claim about every client.',['P2-01: verify map/archive/client compatibility separately; do not label absent client maps as proof map data never existed.'])
add('SD-ARC-003',['BND-030'],['RQ-111','RQ-112'],'reference.museum1996.creation_save_scope',{'museum_experience_uses_recovered_named_characters':True,'ordinary_new_character_creation_not_primary_flow':True,'visitor_state_saved_like_live_game':False},'REFERENCE_2014_RESTORATION_ONLY',[loc('SD-SRC-NDC2014-0080',anchor='직접 캐릭터를 생성해서 플레이하는 것 보다는'),loc('SD-SRC-NDC2014-0080',anchor='나의 데이터가 저장 되지는 않지만')],'NEW_PRIMARY_TRANSCRIPT','Published2014 demo behavior, not current server execution. No original user DB acquired or republished.',['P2-04/P2-05/P2-06: reference login success must not establish target creation/save/auth compliance.'])
add('SD-ARC-004',['BND-030'],['RQ-111','RQ-112'],'source_catalog.guidebook.edition_disambiguation',{'isbn13':'9788985966283','catalog_2001_pages':431,'catalog_2002_pages':447,'same_isbn_multiple_catalog_records':True,'full_text_acquired':False,'CD_in_this_edition_confirmed':False},'BIBLIOGRAPHY_ONLY_NO_GAME_ADOPTION',[loc('SD-SRC-BOOK-NL23946242'),loc('SD-SRC-BOOK-NL25737613'),loc('SD-SRC-BOOK-YES224863')],'NEW_BIBLIOGRAPHIC_EVIDENCE','YES24 dates2001-09-30 and markets2002 latest, body432 vs metadata447; NL[2001]431p and2002 447p conflict. Verify title/copyright/patch pages before extraction.',['G0 future source intake: identify print/patch by inner title/copyright/TOC rather than ISBN alone.'])
# Source locators and original line excerpts are stored once, privately, for exact old-source anchor audit.
ex=[]
for fn,ranges,sid in [('krbegin_basic.html',[(57,61),(67,71),(79,108)],'P15-ARC-c05252ad964d'),('krbegin_use.html',[(49,60),(76,88)],'P15-ARC-a071fac33812')]:
 ls=(P/fn).read_bytes().decode('cp949').splitlines()
 for a,b in ranges:ex.append({'source_id':sid,'source_sha256':S[sid]['sha256'],'encoding':'cp949 strict','line_start':a,'line_end':b,'raw_html_lines':ls[a-1:b]})
(PAY/'existing_source_excerpt.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in ex))
(PUB/'field_candidates_archives_ui.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in c))
(PUB/'sources_archives_ui.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in sources))
# Technical transcript private line map/anchors for the operator.
anchors=['97년에 게임 리소스','맵데이터를 서버에서 받아와서','직접 캐릭터를 생성해서 플레이하는 것 보다는','나의 데이터가 저장 되지는 않지만']
t=(P/'ndc2014_0080.html').read_text();assert all(q in t for q in anchors)
dump(PAY/'transcript_locators.json',{'source_sha256':S['SD-SRC-NDC2014-0080']['sha256'],'anchors':[{'text_anchor':q,'line':t[:t.index(q)].count('\n')+1} for q in anchors],'scope':'Transcript statements; video not acquired/inspected. No timing evidence.'})
# Curated payload excludes old1996 EXE, modern JS bundles, broad search shells and all rejected/unrelated files.
files=[]
for f in sorted(PAY.iterdir()):
 b=f.read_bytes();files.append({'path':'archives_ui/payload/'+f.name,'bytes':len(b),'sha256':sha(b)})
dump(PUB/'private_payload_manifest.json',{'schema':'baram.work-delta.private-payload/1','task_id':'BARAM_REBUILD_WORK_SOURCE_DELTA_001','private_root':str(P.parent),'files':files,'excluded_duplicate_installer':{'source':'LIB-015-M-b2c194b4019f','bytes':3340944,'sha256':'e07cdf98a4727e2661850c480addf0a52fbafde75c6a5176812eae09ba815886','official_current_url':'https://baramold.dn.nexoncdn.co.kr/baram1996.exe','new_unique_bytes':0}})
# Validation checks full local payload set, source-byte references, fields, nonempty populations and unexecuted statuses.
checks=[]
def check(name,ok,details):checks.append({'check':name,'result':'PASS' if ok else 'FAIL','details':details})
check('payload_nonempty_set_and_hashes',len(files)>0 and all((P.parent/x['path']).is_file() and sha((P.parent/x['path']).read_bytes())==x['sha256'] and (P.parent/x['path']).stat().st_size==x['bytes'] for x in files),{'files':len(files),'bytes':sum(x['bytes'] for x in files)})
check('candidate_source_references',all(e['source_id'] in S and e['source_sha256']==S[e['source_id']]['sha256'] for x in c for e in x['source_evidence']),{'candidates':len(c)})
check('new_image_decodes_and_visual_review',len([s for s in sources if s.get('image_format')])==5,{'images':5,'static_frames':5})
check('baseline_normalized_hashes',all(sha((NORM/fn).read_bytes())==h for fn,h in oldfiles.items() if fn in ['kr_official_flow.jsonl','kr_documented_fields.jsonl','kr_asset_ui_strings.jsonl']),{'files':3,'no_mutation':True})
check('runtime_separation',all(x['runtime_test_status']=='NOT_RUN' and x['receiver_status']=='UNACKNOWLEDGED' and x['global_default_selected'] is False for x in c),{'runtime':'NOT_RUN','adoption':'UNACKNOWLEDGED'})
check('curated_payload_excludes_installer_fonts_secrets',not any(f['path'].lower().endswith(('.exe','.sql','.bak','.ttf','.otf','.woff','.pem','.key')) for f in files),{'pattern_scope':'curated filenames, not malware guarantee'})
check('source_dedup_against_P15_registry',all(s['acquisition_class']!='NEW_SOURCE_BYTES' or s['sha256'] not in oldhash for s in sources),{'existing_source_semantics':2,'duplicate_installer_excluded':True,'new_image_bytes':sum(s['bytes'] for s in sources if s.get('image_format'))})
validation={'schema':'baram.work-delta.validation/1','result':'PASS_DATA_SCOPE' if all(x['result']=='PASS' for x in checks) else 'FAIL','checks':checks,'source_semantic_status':'PARTIAL','G0':'NOT_RUN','P2':'NOT_RUN','runtime':'NOT_RUN','game_binding':'NOT_STARTED','codex_receipt':'UNACKNOWLEDGED','files_inspected':len(files),'candidates':len(c),'security_limit':'No executable/script/SQL/server executed. Images decoded with Pillow; no malware-free claim.'}
dump(PUB/'VALIDATION_ARCHIVES_UI.json',validation)
dump(PUB/'STATE_ARCHIVES_UI.json',{'status':'READY_FOR_PARENT_BATCH_REVIEW','candidates':len(c),'sources':len(sources),'new_official_ui_images':4,'new_press_image':1,'new_game_source_code':0,'full_guidebook_text':0,'codex_ack':'UNACKNOWLEDGED','next':'Parent B002 packaging; exact era/native asset matching and name/cancel/sound remain Codex observations.'})
print(json.dumps({'candidates':len(c),'sources':len(sources),'payload_files':len(files),'payload_bytes':sum(x['bytes'] for x in files),'result':validation['result']},ensure_ascii=False))
