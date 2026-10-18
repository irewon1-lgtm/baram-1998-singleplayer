"""Copy real previous checkpoints; change only labelled pickup fixture fields."""
import argparse,hashlib,json,shutil,sqlite3
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();w=a.workspace.resolve();o=a.output.resolve();o.mkdir(exist_ok=False)

def clone(name,source,change=None):
    target=o/name;(target/'v2').mkdir(parents=True)
    shutil.copyfile(source/'v2/identity.json',target/'v2/identity.json')
    if (source/'profile-p6.json').exists():shutil.copyfile(source/'profile-p6.json',target/'profile-p6.json')
    with sqlite3.connect(source/'v2/progress.db') as before,sqlite3.connect(target/'v2/progress.db') as after:
        before.backup(after);after.execute('pragma journal_mode=DELETE')
        data=json.loads(after.execute('select json from checkpoint where slot=1').fetchone()[0])
        if change:
            change(data);text=json.dumps(data,ensure_ascii=False,separators=(',',':'))
            after.execute('update checkpoint set json=?,sha256=?',(text,hashlib.sha256(text.encode()).hexdigest()));after.commit()
    (target/'FIXTURE.json').write_text(json.dumps({'source':str(source),'explicit_fixture':change is not None,'initial':data},indent=2)+'\n')

def pickup(d):
    c=d['character'];gold=next(i for i in d['world']['loot'] if i['item']['ItemId']==-1)
    # Same native death-drop gold record; revive and stand on it for the test.
    c.update(Hp=c['MaxHp'],X=gold['item']['X'],Y=gold['item']['Y'])
    d['world']['loot']=[gold]

def spells(d):
    d['character'].update(Hp=40,MaxHp=100,Mp=100,MaxMp=100,Map=0,MapXs=220,MapYs=220,X=58,Y=150)

clone('pickup',w/'p1998-private/p6/fixtures-3/death',pickup)
clone('spells',w/'p1998-private/p6/fixtures-3/spells',spells)
clone('p6-update',w/'p1998-private/p6/qa-ui-6/app-state')
print('REPAIR_FIXTURES',o)
