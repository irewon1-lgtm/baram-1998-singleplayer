"""Explicit P6 QA fixtures; never a claim of naturally earned level/items."""
import argparse,hashlib,json,shutil,sqlite3,csv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();o=a.output.resolve();o.mkdir(exist_ok=False)
assets=json.loads((w/'p1998-private/p5/converted-4/assets.json').read_text());maps={m['id']:m for m in assets['maps']}
manifest=[]
def clone(label,source,change=None):
 target=o/label;(target/'v2').mkdir(parents=True);shutil.copyfile(source/'v2/identity.json',target/'v2/identity.json')
 with sqlite3.connect(source/'v2/progress.db') as before,sqlite3.connect(target/'v2/progress.db') as after:
  before.backup(after);after.execute('pragma journal_mode=DELETE');data=json.loads(after.execute('select json from checkpoint where slot=1').fetchone()[0])
  original=data['character'].copy()
  if change:change(data)
  text=json.dumps(data,ensure_ascii=False,separators=(',',':'));checksum=hashlib.sha256(text.encode()).hexdigest()
  after.execute('update checkpoint set json=?,sha256=?',(text,checksum));after.commit()
 (target/'EXPECTED_INITIAL.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 manifest.append({'case':label,'source':str(source),'explicit_fixture':change is not None,'character':data['character'],'db_sha256':hashlib.sha256((target/'v2/progress.db').read_bytes()).hexdigest()})
 return target
p5=w/'p1998-private/p5'
clone('p5-update',p5/'qa-journey-state-2')
for path,hall in [(1,11),(2,15),(3,13),(4,17)]:
 edge=next(x for x in maps[0]['warps'] if x['DestinationMapId']==hall)
 def change(d,edge=edge):
  c=d['character'];c.update(Name='ClassHero',ClassName='Peasant',Level=5,Exp=0,Coins=0,Map=0,MapXs=maps[0]['width'],MapYs=maps[0]['height'],X=edge['SourceX']+1,Y=edge['SourceY'],Spells=[],Equipment=[],Armor=0,Weapon=0)
  c['Inventory']=[{'Slot':slot,'ItemId':item,'Amount':20,'Dura':0,'CustomName':'','Repair':0,'Protected':0,'Owner':''} for slot,item in [(0,10009),(1,10012)]]
 clone('class-'+str(path),p5/'class-state-1',change)
# Reuse the already documented P5 offensive-spell fixture rather than invent a
# new game rule. Reset only its explicit level5/heal/mana inputs and location.
def spell(d):
 c=d['character'];c.update(ClassName='Mage',Level=5,Hp=40,MaxHp=100,Mp=100,MaxMp=100,Map=0,MapXs=maps[0]['width'],MapYs=maps[0]['height'],X=58,Y=150,Spells=[int(r["SplId"]) for r in csv.DictReader((w/"inputs/source/Project1998-master/game-data/Spells.csv").open()) if r["SplIdentifier"] in ["soothe","gateway","thunder_bolt_mage"]])
clone('spells',p5/'spells-final-state-2',spell)
def death(d):
 original=json.loads((p5/'qa-death-1/GUI.json').read_text())['initial']['character']
 c=d['character'];c.update(Hp=1,Coins=100,Map=int(original['Map']),X=int(original['X']),Y=int(original['Y']),MapXs=int(original['MapXs']),MapYs=int(original['MapYs']))
clone('death',p5/'death-state',death)
# Natural P4 save is copied read-only; the unchanged P5 migrator creates v2.
t=o/'journey';t.mkdir();shutil.copytree(w/'p1998-private/p4/golden-checkpoint/v1',t/'v1')
(o/'FIXTURES.json').write_text(json.dumps({'warning':'level5 classes and spells are explicit fixtures, not a normal journey','cases':manifest},indent=2)+'\n')
print('P6_FIXTURES',len(manifest)+1)
