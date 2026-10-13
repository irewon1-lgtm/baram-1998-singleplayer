#!/usr/bin/env python3
"""Validate evidence references/date isolation/curated transcriptions; no gameplay PASS."""
import pathlib,json,hashlib,datetime,collections,re,sys
ROOT=pathlib.Path(__file__).parent
s=json.loads((ROOT/'sources.json').read_text());sm={x['id']:x for x in s};f=[json.loads(x) for x in (ROOT/'facts.jsonl').read_text().splitlines()];c=[json.loads(x) for x in (ROOT/'extracted-candidates.jsonl').read_text().splitlines()];cm={x['id']:x for x in c};checks=[]
def check(n,v,detail):checks.append({'name':n,'result':'PASS' if v else 'FAIL','scope':'RESEARCH_DATA_ONLY','detail':detail})
check('Unique source/fact identifiers',len(sm)==len(s) and len({x['id'] for x in f})==len(f),{'sources':len(s),'facts':len(f)})
check('All curated source references resolve',all(x['source_id'] in sm and x.get('source_url') for x in f),'URL/source id/position linkage')
check('Dates cannot silently cross profiles',all((sm[x['source_id']].get('publication_date') or sm[x['source_id']].get('capture_timestamp') or '').startswith(str(x['year'])) for x in f),'Source year checked, exact patch validity remains unknown')
check('No 2002 mislabeled scan admitted to1998',not any(x['year']==1998 and 'gamechamp' in x['source_id'] for x in f),'All3 incorrectly indexed scans excluded')
check('1999 data comes from inspected user images',all(sm[x['source_id']]['kind']=='CONTEMPORANEOUS_MAGAZINE_USER_SUPPLIED_IMAGE' and x['position'].get('printed_page') in [272,273,274,275] for x in f if x['year']==1999) and len({x['source_id'] for x in f if x['year']==1999})==4,'User supplied original screenshots; source-content scope only, no runtime PASS')
check('Null unknowns retained',all(x.get('game_runtime_verified') is False and x.get('game_version') is None for x in f),'Game runtime not verified; no inferred common patch')
check('Learning material parser removed currency prefix',not any(m['name'].startswith('전') for x in f if x['category']=='spell' for m in x['fields'].get('learn_materials',[])), 'Regression: 전 도토리70 must be 도토리70')
check('Profile files equal canonical facts',all(json.loads((ROOT/f'KR-{y}.json').read_text())==[x for x in f if x['year']==y] for y in [1998,1999,2000,2001]),'No out-of-date derived per-year output')
# Compare each curated table row against already extracted candidate; manual exceptions explicitly listed.
found=0;bad=[]
for x in f:
 p=x.get('position',{})
 if 'table_1based' not in p or 'row_1based' not in p:continue
 cid=f'C-{x["source_id"]}-{p["table_1based"]}-{p["row_1based"]}'
 if cid not in cm:bad.append(cid);continue
 cc=cm[cid];found+=1
 for k,v in x['fields'].items():
  if k in ['drop_item_names','drop_probability']:continue # manually disambiguated document tokens
  if k in cc['fields'] and cc['fields'][k]!=v:bad.append((cid,k,v,cc['fields'][k]))
check('Curated HTML numeric cells agree with extraction',not bad,{'rows_compared':found,'mismatches':bad})
summary=json.loads((ROOT/'SUMMARY.json').read_text());check('Summary recount',summary['curated_fact_records']==len(f) and summary['extracted_candidate_rows']==len(c),{'curated':len(f),'candidate':len(c)})
check('No raw protected assets included',all(x.suffix in ['.json','.jsonl','.md','.py'] for x in ROOT.iterdir() if x.is_file()),'No scan/client/DAT/EPF/audio/source archive bytes in publish directory')
check('Conflict entry remains blocked',all(x['evidence_status']=='CONFLICTING_SOURCE_CONFIRMED' for x in f if x['name']=='동귀어진 잔여HP'),'No promotion to unconditional mechanic')
a=json.loads((ROOT/'IMPLEMENTATION_AVERAGES.json').read_text());fm={x['id']:x for x in f};avg_bad=[]
for x in a['values']:
 values=x['distinct_source_values']
 if abs(sum(values)/len(values)-x['arithmetic_mean'])>1e-12:avg_bad.append(x['id'])
 for o in x['observations']:
  source=fm.get(o['fact_id'])
  if not source or o['source_url']!=source['source_url'] or o['value'] not in values or source['region']!='KR':avg_bad.append(x['id'])
check('Averages reproduce linked originals',not avg_bad and len(a['values'])==summary['implementation_average_fields'],{'fields':len(a['values']),'bad':avg_bad,'scope':'USER_DIRECTED_ARITHMETIC_ONLY'})
check('Numeric cells recount',summary['verified_scalar_numeric_cells']==sum(type(v) in (int,float) for x in f for v in x['fields'].values()),'Numeric cell count is not distinct complete game entities')
r={'executed_at' :datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'overall':'PASS_RESEARCH_INTEGRITY_ONLY' if all(x['result']=='PASS' for x in checks) else 'FAIL','historical_completeness':'NOT_PASS','gameplay_runtime':'NOT_RUN','KR_resource_full_match':'NOT_RUN'}
(ROOT/'VALIDATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False));sys.exit(any(x['result']=='FAIL' for x in checks))
