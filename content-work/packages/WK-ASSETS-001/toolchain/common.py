"""Work-only deterministic package primitives; never modify game or integration."""
import collections
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'content-work'
BASE = 'dea6574c9a69ebb04432d10fc32951aacd8b66cb'
PROTOCOL = 'BARAM_PARALLEL_V1'
VERSION = 'work-tools-1.0.0'

def sha(data): return hashlib.sha256(data).hexdigest()
def file_sha(path): return sha(Path(path).read_bytes())
def canonical(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value)+'\n', encoding='utf-8')
def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def lines(path): return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
def round_int(value): return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
def ratio(value, denominator=1000000):
    return {'numerator': round_int(Decimal(str(value))*denominator), 'denominator': denominator}
def average(observations):
    unique = {o['origin_key']:o for o in observations}
    units = {o['unit'] for o in unique.values()}; conditions = {canonical(o['condition']) for o in unique.values()}
    if len(units)!=1 or len(conditions)!=1 or not unique: raise ValueError('Non-comparable average')
    raw = sum(Decimal(str(o['value'])) for o in unique.values()) / len(unique)
    return {'raw':str(raw), 'value':round_int(raw), 'observations':list(unique.values()), 'rounding':'HALF_AWAY_FROM_ZERO'}

class IDs:
    """IDs are stored by origin key, never content hashes or per-run UUIDs."""
    def __init__(self):
        self.path=WORK/'catalog/permanent_ids.json'
        self.entries=load(self.path) if self.path.exists() else {}
    def get(self, kind, origin):
        key=kind+':'+origin
        if key not in self.entries:
            slug=re.sub(r'[^a-zA-Z0-9_.-]+','_',origin).strip('_')
            if not slug or len(slug)>130: raise ValueError('Use an explicit stable source key')
            ident='wk.'+kind+'.'+slug
            if ident in self.entries.values(): raise ValueError('ID slug collision: '+key)
            self.entries[key]=ident
        return self.entries[key]
    def save(self): write(self.path,self.entries)

def record(ident, kind, data, prov, refs=(), mode='INFERRED', target=None, old=None):
    r={'id':ident,'kind':kind,'operation':'propose_patch' if target else 'add','data':data,
       'references':list(refs),'provenance_refs':list(prov),'source_mode':mode}
    if target:
        r.update(target_id=target,base_game_commit=BASE,changes=[dict(path='runtime_definition',
          before={'exists':False},after=data,reason='Complete declarative definition with field provenance; existing canonical fields are preserved',provenance_ref=prov[-1])])
    return r

def ref(role, ident, selector=None):
    r={'role':role,'id':ident}
    if selector is not None:r['selector']=selector
    return r

def shard(package, records, stem='content', max_bytes=56000):
    package=Path(package); package.mkdir(parents=True,exist_ok=True)
    existing=list(package.glob(stem+'-*.jsonl'))
    if existing: raise ValueError('Frozen output already exists; use a new batch')
    chunk=[];size=0;number=0;paths=[]
    def flush():
        nonlocal number,chunk,size
        p=package/f'{stem}-{number:03d}.jsonl';p.write_text(''.join(chunk),encoding='utf-8');paths.append(p.name)
        number+=1;chunk=[];size=0
    for r in sorted(records,key=lambda r:r['id']):
        s=canonical(r)+'\n';n=len(s.encode())
        if chunk and size+n>max_bytes:flush()
        chunk.append(s);size+=n
    if chunk:flush()
    return paths

def seal(package, records, dependencies=(), capabilities=(), external=()):
    package=Path(package)
    if (package/'manifest.json').exists():raise ValueError('Manifest already fixed')
    m={'protocol_id':PROTOCOL,'schema_id':'BARAM_CONTENT_PACKAGE','schema_version':1,
       'batch_id':package.name,'producer':'Work','base_game_commit':BASE,
       'files':[{'path':str(p.relative_to(package)),'size_bytes':p.stat().st_size,'sha256':file_sha(p)} for p in sorted(package.rglob('*')) if p.is_file()],
       'counts':dict(collections.Counter(r['kind'] for r in records)),
       'operations':dict(collections.Counter(r['operation'] for r in records)),
       'dependencies':list(dependencies),'external_references':sorted(set(external)),
       'required_capabilities':list(capabilities),'supersedes':[],
       'schemas':[{'path':'schema/content-v1.json','sha256':file_sha(package/'schema/content-v1.json')}],
       'generator_version':VERSION,'scope':'DATA_ONLY_GAMEPLAY_NOT_RUN'}
    write(package/'manifest.json',m);return m
