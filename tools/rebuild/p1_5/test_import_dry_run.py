#!/usr/bin/env python3
"""Small isolated corruption checks for P1.5 import gate; no original writes."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT/'tools/rebuild/p1_5/import_dry_run.py'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'docs/rebuild/p1_5/import_regression.json');a=ap.parse_args();cases=[]
 with tempfile.TemporaryDirectory(prefix='baram-import-fixture-') as tmp:
  for case in ['normal_complete','duplicate_id','broken_source_reference','changed_source_bytes','wrong_row_input_hash','zero_catalogs','unsupported_script_semantics','empty_jsonl','empty_json_array','malformed_registry','malformed_source_ids','wrong_locator_url','wrong_parser_fingerprint','missing_declared_catalog','wrong_relative_catalog_path','unexecuted_audio_PASS','broken_normalized_record_reference','unproved_pool_selector_is_not_mob']:
   base=Path(tmp)/case;base.mkdir();content=base/'selected';content.mkdir();reg=base/'registry';reg.mkdir();source=base/'synthetic.txt';source.write_text('synthetic fixture source\n')
   sid='P15-FIXTURE-SOURCE';h=sha(source.read_bytes())
   src={'source_id':sid,'source_type':'SYNTHETIC_TEST_FIXTURE','source_family':'ISOLATED_FIXTURE','local_private_path':str(source),'sha256':h,'byte_length':source.stat().st_size}
   (reg/'sources_delta.jsonl').write_text(json.dumps(src)+'\n');write(base/'input_map.json',{})
   row={'id':'FIXTURE:row:1','record_type':'fixture','original_value':{'value':1},'reconstructed_value':None,'source_ids':[sid],'input_sha256':h,'source_locator':{'line_start':1,'line_end':1},'fact_status':'UNKNOWN','new_runtime_binding':'NOT_STARTED','test_status':'NOT_RUN','selected_for_build':False}
   expected='FAIL';expected_integrity='FAIL'
   rows=[row]
   if case=='normal_complete':expected=expected_integrity='PASS'
   elif case=='duplicate_id':rows.append(dict(row))
   elif case=='broken_source_reference':row['source_ids']=['NONEXISTENT-FIXTURE']
   elif case=='changed_source_bytes':source.write_text('synthetic changed fixture\n')
   elif case=='wrong_row_input_hash':row['input_sha256']='0'*64
   elif case=='zero_catalogs':rows=[];expected=expected_integrity='BLOCKED'
   elif case=='unsupported_script_semantics':row['kind']='static_script_index';expected='BLOCKED';expected_integrity='PASS'
   elif case=='empty_jsonl':rows=[];expected=expected_integrity='BLOCKED';(content/'empty.jsonl').write_text('')
   elif case=='empty_json_array':rows=[];expected=expected_integrity='BLOCKED';write(content/'empty.json',[])
   elif case=='malformed_registry':write(reg/'research_bad.json',42)
   elif case=='malformed_source_ids':row['source_ids']=[{}]
   elif case=='wrong_locator_url':row['source_locator']['url']='fixture://wrong-source'
   elif case=='broken_normalized_record_reference':row['original_value']['parent_record_id']='KRO-MISSING';expected_integrity='PASS'
   elif case=='unexecuted_audio_PASS':row['game_output_test']='PASS'
   elif case=='unproved_pool_selector_is_not_mob':
    source.write_text('(synthetic fixture source)\n');h=sha(source.read_bytes());src.update(repository='unkmc/RTK-Server',path='synthetic.txt',sha256=h,byte_length=source.stat().st_size);(reg/'sources_delta.jsonl').write_text(json.dumps(src)+'\n')
    row.update(source_id=sid,input_sha256=h,source_locator={'line_start':1,'line_end':1,'character_offset':0},kind='literal_drop_table',original_value={'mob_key':'nagnag_armory_0','tables':{}})
    rows.append(dict(row,id='FIXTURE:row:2',kind='sql_content:Mobs',original_value={'MobIdentifier':'known_mob'}));expected_integrity='PASS'
   elif case=='wrong_parser_fingerprint':row['source']={'source_id':sid,'member_sha256':h,'container_sha256':h,'member_byte_offset':0,'parser_sha256':'0'*64}
   elif case=='missing_declared_catalog':expected=expected_integrity='BLOCKED'
   if rows:(content/'fixture.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   out=base/'result.json';cmd=[sys.executable,str(SCRIPT),'--registry-dir',str(reg),'--content-dir',str(content),'--input-map',str(base/'input_map.json'),'--output',str(out)]
   if case in ('missing_declared_catalog','wrong_relative_catalog_path'):
    declared=[{'path':'selected_content/missing.jsonl' if case=='missing_declared_catalog' else 'selected_content/wrong/fixture.jsonl','sha256':'0'*64,'records':1}]
    if case=='missing_declared_catalog':
     fixture_bytes=(content/'fixture.jsonl').read_bytes();declared.append({'path':'selected_content/fixture.jsonl','sha256':sha(fixture_bytes),'bytes':len(fixture_bytes),'records':1})
    write(base/'manifest.json',{'normalized_catalogs':declared});cmd+=['--catalog-manifest',str(base/'manifest.json')]
   p=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60);actual=json.loads(out.read_text()) if out.is_file() else {}
   code={'PASS':0,'FAIL':1,'BLOCKED':2,'NOT_RUN':3}[expected]
   assertions={'status':actual.get('result')==expected,'integrity':actual.get('integrity_result')==expected_integrity,'exit':p.returncode==code,'runtime_not_run':actual.get('runtime_tests')=='NOT_RUN','no_defaults':actual.get('zero_defaults_inserted')==0}
   cases.append({'case_id':case,'input_origin':'SYNTHETIC_FIXTURE_ONLY','expected':expected,'actual':actual.get('result'),'exit_code':p.returncode,'result':'PASS' if all(assertions.values()) else 'FAIL','assertions':assertions,'command':cmd,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()})
 result={'task_id':'BARAM_REBUILD_P1_5_001','executed_at_utc':datetime.now(timezone.utc).isoformat(),'validator_sha256':sha(SCRIPT.read_bytes()),'regression_script_sha256':sha(Path(__file__).read_bytes()),'result':'PASS' if all(c['result']=='PASS' for c in cases) else 'FAIL','cases':cases,'scope':'IMPORTER CONTROL FLOW/INTEGRITY REGRESSION; synthetic normal PASS is not original-data/history/gameplay PASS','runtime_tests':'NOT_RUN'}
 a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,result);print(json.dumps({'result':result['result'],'cases':len(cases),'case_results':[c['result'] for c in cases]}));return 0 if result['result']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
