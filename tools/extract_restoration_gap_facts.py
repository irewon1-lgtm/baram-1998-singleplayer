#!/usr/bin/env python3
"""Extract only additional explicit cast/heal/buff numbers from archived fan rows."""
import argparse, datetime, hashlib, json, re
from pathlib import Path
from lxml import html
from review_restoration_candidates import clean, norm

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'research/restoration-integrated-20261013'

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-dir',required=True);a=p.parse_args();records=[]
    for s in json.loads((ROOT/'research/korean-history-20261013/sources.json').read_text()):
        url=s.get('original_url','')
        match=re.search(r'magic([2345])\.(?:php|htm)',url)
        if not match:continue
        file=Path(a.private_dir)/'kr-html'/(s['id']+'.html')
        if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=s['sha256']:continue
        tree=html.fromstring(file.read_bytes().decode(s.get('encoding') or 'cp949'))
        for ti,table in enumerate(tree.xpath('//table'),1):
            rows=table.xpath('./tr')
            if not rows:continue
            header=[clean(c.text_content()) for c in rows[0].xpath('./td|./th')]
            if not header or header[0]!='기술명' or len(header) not in [5,6]:continue
            for ri,row in enumerate(rows[1:],2):
                cells=[clean(c.text_content()) for c in row.xpath('./td|./th')]
                if len(cells)!=len(header) or not cells[0] or not re.search(r'Lv\s*\d+',cells[1]):continue
                description=cells[-2];fields={};tokens={}
                patterns=[('cast_mp',r'마력(?:을|의)?\s*([\d,]+)\s*(?:과|소모|을\s*소모)'),
                          ('heal_amount',r'체력(?:을|의)?\s*([\d,]+)\s*(?:만큼\s*)?(?:회복|채워)'),
                          ('armor_delta',r'갑옷강도를?\s*([\d,]+)\s*내려'),
                          ('strength_bonus',r'힘을\s*([\d,]+)\s*올려')]
                for key,pattern in patterns:
                    m=re.search(pattern,description)
                    if m:fields[key]=int(m[1].replace(',',''))*(-1 if key=='armor_delta' else 1);tokens[key]=m[0]
                m=re.search(r'체력의\s*(\d+)\s*%\s*를?\s*(?:씁니다|사용)',description)
                if m:fields['cast_hp_fraction']=int(m[1])/100;tokens['cast_hp_fraction']=m[0]
                if not fields:continue
                records.append(dict(id=f'GAP-{s["id"]}-{ti}-{ri}',category='spell',name=cells[0],year=2001,region='KR',
                                    class_scope={'2':'전사','3':'주술사','4':'도적','5':'도사'}[match[1]],fields=fields,
                                    source_id=s['id'],source_url=s['final_url'],source_sha256=s['sha256'],position=dict(table_1based=ti,row_1based=ri,description_column_1based=len(header)-1),
                                    source_numeric_tokens=tokens,evidence_status='CONTEMPORANEOUS_FAN_ROW_EXPLICIT_NUMBER',
                                    verification_scope='SOURCE_CONTENT_ONLY',game_runtime_verified=False))
    (OUT/'GAP_SUPPLEMENT_FACTS.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in records))
    print(json.dumps(dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_explicit_records=len(records),numeric_fields=sum(len(r['fields']) for r in records),not_gameplay_verified=True),ensure_ascii=False))

if __name__=='__main__':main()
