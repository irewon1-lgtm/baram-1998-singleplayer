#!/usr/bin/env python3
"""Independent metadata validation, not the upstream C# loader or game."""
import argparse, csv, json, collections
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    p=Path(args.source)/'game-data';out=Path(args.out);out.mkdir(parents=True,exist_ok=True);report={};details=[]
    for n in ['Maps.csv','map_index.csv','mobs.csv','Items.csv','Spells.csv','NPCs.csv','Warps.csv','Sources.csv','EraFeatures.csv','LevelExp.csv']:
        with (p/n).open(encoding='utf-8-sig',newline='') as f:
            # Upstream permits comment lines. Do not call comments entities.
            r=list(csv.DictReader(line for line in f if line.strip() and not line.lstrip().startswith('#')))
        report[n]={'raw_noncomment_rows':len(r),'columns':list(r[0]) if r else []}
    with (p/'map_index.csv').open(encoding='utf-8-sig') as f:idx=list(csv.DictReader(f))
    for r in idx:
        f=p/'maps'/('TK'+r['id']+'.map');want=int(r['xs'])*int(r['ys'])*4;actual=f.stat().st_size if f.exists() else None
        status='MISSING' if actual is None else ('EXACT' if actual==want else ('SUFFICIENT_EXTRA' if actual>want else 'SHORT'))
        details.append({'id':r['id'],'path':str(f.relative_to(p.parent)),'xs':int(r['xs']),'ys':int(r['ys']),'expected_bytes':want,'actual_bytes':actual,'status':status})
    report['map_check']={'method':'Independent byte-length vs xs*ys*4; no C# runtime or rendered gameplay','counts':dict(collections.Counter(x['status'] for x in details)),'total_map_files':len(list(p.rglob('*.map'))),'unique_map_sha256':None}
    (out/'project1998-content-check.json').write_text(json.dumps(report,indent=2)+'\n');(out/'project1998-map-check.json').write_text(json.dumps(details,indent=2)+'\n')
    print(json.dumps(report['map_check']))
    return 0 if all(x['status']=='EXACT' for x in details) else 1

if __name__=='__main__':raise SystemExit(main())
