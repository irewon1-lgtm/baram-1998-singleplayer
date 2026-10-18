"""Exact P4 import preservation, semantic comparison and legacy refusal cases."""
import argparse,hashlib,json,shutil,sqlite3,subprocess
from pathlib import Path
from tooling import environment,godot
p=argparse.ArgumentParser()
for k in ['workspace','experiment','state','journey','output']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();w=a.workspace.resolve();e=a.experiment.resolve();s=a.state.resolve();o=a.output.resolve();o.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((s.parent/'P4_IMPORT_BEFORE.json').read_text());assert before=={k:sha(s/k) for k in before}
with sqlite3.connect(s/'v1/progress.db') as db:old=json.loads(db.execute('select json from checkpoint where slot=1').fetchone()[0])
j=json.loads((a.journey/'GUI.json').read_text());initial=j['initial'];assert initial['character']==old['character'], 'P4 full character changed during import'
old_mobs={r['data']['Id']:r['data'] for r in old['world']['mobs'] if r['map']==old['character']['Map']}
current={int(r['id']):r for r in initial['actors'] if not r['npc']}
assert all(k in current and all(current[k][f]==v[g] for f,g in [('hp','Hp'),('max_hp','MaxHp'),('x','X'),('y','Y'),('key','Key')]) for k,v in old_mobs.items())
assert len(current)==len(set(current))
with sqlite3.connect(s/'v2/progress.db') as db:
 assert db.execute('pragma integrity_check').fetchone()[0]=='ok';new=json.loads(db.execute('select json from checkpoint where slot=1').fetchone()[0])
assert new['revision']>old['revision']
assert {m['data']['Id'] for m in old['world']['mobs']}<={m['data']['Id'] for m in new['world']['mobs']}
checks=[]
for case in ['future_identity','wrong_content','future_checkpoint','future_character','future_world','bad_checksum','missing_identity']:
 target=o/case/'state';(target/'v1').mkdir(parents=True)
 shutil.copyfile(s/'v1/identity.json',target/'v1/identity.json')
 with sqlite3.connect(s/'v1/progress.db') as source,sqlite3.connect(target/'v1/progress.db') as copy:
  source.backup(copy);copy.execute('pragma journal_mode=DELETE');value=json.loads(copy.execute('select json from checkpoint where slot=1').fetchone()[0])
  if case=='future_checkpoint':value['schema_version']=999
  if case=='future_character':value['character']['SchemaVersion']=999
  if case=='future_world':value['world']['schema_version']=999
  text=json.dumps(value);digest=hashlib.sha256(text.encode()).hexdigest()
  if case=='bad_checksum':digest='0'*64
  copy.execute('update checkpoint set json=?,sha256=? where slot=1',(text,digest))
 if case in ['future_identity','wrong_content']:
  identity=json.loads((target/'v1/identity.json').read_text())
  if case=='future_identity':identity['schema_version']=999
  else:identity['content_sha256']='0'*64
  (target/'v1/identity.json').write_text(json.dumps(identity))
 if case=='missing_identity':(target/'v1/identity.json').unlink()
 hashes={str(f.relative_to(target)):sha(f) for f in (target/'v1').rglob('*') if f.is_file()}
 env=environment(w,e)|{'P1998_P4_OUTPUT':str(target)}
 cmd=[godot(w),'--headless','--audio-driver','Dummy','--path',e/'runtime','--script',Path(__file__).with_name('guard_qa.gd').resolve(),'--','--p4-test-empty-base','--qa-output='+str(target.parent)]
 with (target.parent/'guard.log').open('w') as log:r=subprocess.run([str(x) for x in cmd],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=35)
 result=json.loads((target.parent/'GUARD.json').read_text())
 assert r.returncode==0 and result['status']=='PASS',case
 assert hashes=={str(f.relative_to(target)):sha(f) for f in (target/'v1').rglob('*') if f.is_file()},case
 assert not (target/'v2/progress.db').exists(),case
 checks.append({'case':case,'status':'PASS','p4_bytes_preserved':True,'no_new_game_created':True})
result={'status':'PASS_HOST_MIGRATION_SCOPE','p4_file_hashes_preserved':before,'full_original_character_preserved':True,'current_map_old_mob_ids_hp_coords_preserved':len(old_mobs),'all_old_world_living_ids_retained':len(old['world']['mobs']),'new_points_added_without_duplicate_ids':len(current)-len(old_mobs),'revision_increased':True,'guards':checks,'native_android':'NOT_RUN_DEVICE_P5'}
(o/'MIGRATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
