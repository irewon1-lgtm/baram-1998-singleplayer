#!/usr/bin/env python3
"""Reconcile every prior candidate with pinned original HTML and curated facts.

Outputs source-content confirmation, never runtime or whole-entity confirmation.
No source HTML, copyrighted illustrations, or external program code is emitted.
"""
import argparse, collections, datetime, hashlib, json, re
from pathlib import Path
from lxml import html

ROOT=Path(__file__).resolve().parents[1]
KR=ROOT/'research/korean-history-20261013'
OUT=ROOT/'research/restoration-integrated-20261013'

def load_jsonl(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def clean(text):return re.sub(r'\s+',' ',text or '').strip()
def norm(text):return re.sub(r'\s+','',text or '')
def number(token):
    token=norm(token).replace(',','')
    token=re.sub(r'^(?:레벨|AC|체력|마력|금전[:：]?)','',token,flags=re.I)
    token=re.sub(r'(?:전|개|필요)$','',token)
    if not token or '?' in token or '_' in token:return None
    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',token):return float(token) if '.' in token else int(token)
    match=re.fullmatch(r'(\d+(?:\.\d+)?)(천만|만|천)',token)
    if match:return float(match[1])*{'천만':10000000,'만':10000,'천':1000}[match[2]]
    if re.fullmatch(r'(?:\d+(?:\.\d+)?[만천백십])+(?:\d+)?',token):
        values=re.findall(r'(\d+(?:\.\d+)?)([만천백십]?)',token)
        return sum(float(value)*{'만':10000,'천':1000,'백':100,'십':10,'':1}[unit] for value,unit in values)
    return None

def spell_scope(source,table):
    url=source['original_url']
    for part,scope in [('fighter.html','전사'),('thidf.html','도적'),('wizard.html','주술사'),('dosa.html','도사'),('common.html','공통')]:
        if part in url:return scope
    if 'seung.html' in url:return {4:'전사',6:'도적',8:'주술사',10:'도사'}.get(table,'미확정')
    return '미확정'

def material_values(token):
    token=clean(token)
    # Currency is removed before parsing material names. Blank is unknown.
    token=re.sub(r'금전\s*[:：]\s*(?:필요\s*없음|[\d,]+\s*전)','',token)
    token=re.sub(r'재료\s*[:：]','',token)
    result=[]
    for match in re.finditer(r'([가-힣A-Za-z][가-힣A-Za-z\s]*?)\s*[:：]?\s*(\d[\d,]*)\s*개',token):
        name=clean(match[1]).removeprefix('필요 ').removeprefix('전 ')
        result.append(dict(name=name,quantity=int(match[2].replace(',',''))))
    return result

def parsed_row(candidate,source,row):
    nodes=row.xpath('./td|./th');cells=[clean(n.text_content()) for n in nodes]
    cat=candidate['category'];fields={};tokens={};issues=[]
    if not cells:raise ValueError('No direct table cells')
    if norm(candidate['name'])!=norm(cells[0]):raise ValueError('Name cell mismatch')
    if cat=='monster':
        if len(cells) not in [4,5]:raise ValueError('Unexpected monster columns')
        fields['experience']=number(cells[-2]);tokens['experience']=cells[-2]
        drop=cells[-1]
        if not drop or '?' in drop:fields['drop_item_names']=None
        elif drop=='없음':fields['drop_item_names']=[]
        else:
            item_text=re.sub(r'\d+(?:\.\d+)?\s*%\s*(?:의\s*)?확률로\s*[,，]?','',drop)
            fields['drop_item_names']=[clean(p) for p in re.split(r'[,，]|또는',item_text) if clean(p)]
            fields['drop_mode']='ALTERNATIVE_NOT_INDEPENDENT' if '또는' in drop else 'LISTED_POSSIBILITIES_NOT_PROVEN_GUARANTEED'
            prob=re.search(r'(\d+(?:\.\d+)?)\s*%',drop)
            if prob:
                fields['drop_probability']=float(prob[1])/100
                tokens['drop_probability']=prob[0]
                if len(fields['drop_item_names'])!=1:issues.append('DROP_PROBABILITY_ITEM_SCOPE_AMBIGUOUS')
        # Descriptive evidence is classified, not copied as a passage.
        desc=cells[-3]
        if '먼저 공격하지' in desc:fields['ai_aggressive']=False
        elif '호전적' in desc:fields['ai_aggressive']=True
        if candidate['name']=='백호왕' and fields.get('experience')==800:issues.append('C10_SUSPICIOUS_XP_800')
    elif cat=='item':
        if len(cells) not in [5,7]:raise ValueError('Unexpected item columns')
        fields['guide_listed_price']=number(cells[2]);tokens['guide_listed_price']=cells[2]
        if '/weapon' in source['original_url']:
            damage=re.fullmatch(r'\s*(\d+)\s*[m~～\-]\s*(\d+)\s*',cells[3])
            fields.update(damage_min=int(damage[1]) if damage else None,damage_max=int(damage[2]) if damage else None,
                          level_required=number(cells[4]),strength_required=number(cells[5]))
            tokens.update(damage_min=cells[3],damage_max=cells[3],level_required=cells[4],strength_required=cells[5])
            fields['item_kind']='weapon'
        elif '/accessory' in source['original_url']:
            fields.update(armor_class=number(cells[3]),durability=number(cells[4]),level_required=number(cells[5]))
            tokens.update(armor_class=cells[3],durability=cells[4],level_required=cells[5])
            if '_' in cells[3]:issues.append('ARMOR_SIGN_UNDERSCORE_UNRESOLVED')
            fields['item_kind']='armor'
        else:fields['item_kind']='consumable_or_material'
        description=cells[-1]
        for pattern,key in [(r'체력\s*([\d,]+)\s*(?:회복|만큼)', 'heal_amount'),(r'마력\s*([\d,]+)\s*(?:회복|만큼)','restore_mp')]:
            match=re.search(pattern,description)
            if match:fields[key]=int(match[1].replace(',',''));tokens[key]=match[0]
        for pattern,key in [(r'체력\s*\+\s*([\d,]+)','hp_bonus'),(r'(?:마력|기력)\s*\+\s*([\d,]+)','mp_bonus'),(r'명중률\s*\+\s*(\d+)','hit_bonus'),(r'파괴력\s*\+\s*(\d+)','damage_bonus'),(r'재생력\s*\+\s*(\d+)','regen_bonus')]:
            match=re.search(pattern,description)
            if match:fields[key]=int(match[1].replace(',',''));tokens[key]=match[0]
    elif cat=='spell':
        fields['class_scope']=spell_scope(source,candidate['position']['table_1based'])
        if len(cells) not in [4,5]:raise ValueError('Unexpected spell columns')
        headers=[clean(n.text_content()) for n in row.getparent().xpath('./tr')[0].xpath('./td|./th')]
        combined='/' in (headers[0] if headers else '')
        if combined:
            following=row.getnext()
            while following is not None and not isinstance(following.tag,str):following=following.getnext()
            level_token=clean(following.text_content()) if following is not None else ''
            found=re.search(r'(\d+)\s*$',level_token)
            fields['learn_level']=int(found[1]) if found else None
            if 'seung.html' in source['original_url']:fields['advancement_required_token']=re.sub(r'\s*\d+\s*$','',level_token)
        else:level_token=cells[1];fields['learn_level']=number(level_token)
        tokens['learn_level']=level_token
        materials=cells[3]
        money=re.search(r'금전\s*[:：]\s*([\d,]+)\s*전',materials)
        fields['learn_money']=int(money[1].replace(',','')) if money else 0 if re.search(r'금전\s*[:：]\s*필요\s*없음',materials) else None
        parsed_materials=material_values(materials)
        fields['learn_materials']=parsed_materials if parsed_materials else None
        tokens['learn_money']=money[0] if money else '금전: 필요없음' if fields['learn_money']==0 else materials
        tokens['learn_materials']=materials
        xp=re.search(r'경험치\s*([\d,.]+\s*(?:천만|만|천)?)',materials)
        if xp:fields['learn_experience_cost']=number(xp[1]);tokens['learn_experience_cost']=xp[0]
        description=cells[2]
        heal=re.search(r'체력을?\s*(\d[\d,]*)\s*만큼\s*회복',description)
        if heal:fields['heal_amount']=int(heal[1].replace(',',''));tokens['heal_amount']=heal[0]
        hp_fraction=re.search(r'체력의\s*(\d+(?:\.\d+)?)\s*%\s*를?\s*사용',description)
        if hp_fraction:fields['cast_hp_fraction']=float(hp_fraction[1])/100;tokens['cast_hp_fraction']=hp_fraction[0]
        if norm(candidate['name'])=='동귀어진':issues.append('C05_EFFECT_CONFLICT_MECHANIC_BLOCKED')
    elif cat=='npc':
        if len(cells)!=4:raise ValueError('Unexpected NPC columns')
        fields['guide_location']=cells[1]
        coord=re.fullmatch(r'\s*(\d+)\s*[,/]\s*(\d+)\s*',cells[3])
        fields['guide_coordinate']=[int(coord[1]),int(coord[2])] if coord else None
        tokens['guide_coordinate']=cells[3] if coord else ''
        if any(p in candidate['name'] for p in ['왈숙네 왈숙언니','연실네 연실언니','형제들']):issues.append('COMPOSITE_NPC_IDENTITY_REQUIRES_SPLIT')
    return fields,tokens,issues

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private-dir',required=True);args=parser.parse_args()
    sources={row['id']:row for row in json.loads((KR/'sources.json').read_text())}
    candidates=load_jsonl(KR/'extracted-candidates.jsonl');facts=load_jsonl(KR/'facts.jsonl')
    fact_rows=collections.defaultdict(list)
    for f in facts:
        p=f.get('position',{})
        if 'table_1based' in p and 'row_1based' in p:fact_rows[(f['source_id'],p['table_1based'],p['row_1based'])].append(f['id'])
    trees={};source_checks={};reviews=[];confirmed=[];dedup={}
    for c in candidates:
        sid=c['source_id'];s=sources.get(sid);path=Path(args.private_dir)/'kr-html'/(sid+'.html')
        out=dict(candidate_id=c['id'],category=c['category'],name=c['name'],year=c['year'],source_id=sid,position=c['position'],
                 original_candidate_fields=c['fields'],linked_curated_fact_ids=fact_rows.get((sid,c['position']['table_1based'],c['position']['row_1based']),[]),
                 verification_scope='SOURCE_TABLE_CELLS_ONLY',game_runtime_verified=False)
        if sid not in source_checks:
            try:
                raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
                source_checks[sid]=dict(source_id=sid,sha256=actual,expected_sha256=s['sha256'],status='PASS' if actual==s['sha256'] else 'FAIL')
                trees[sid]=html.fromstring(raw.decode(s.get('encoding') or 'cp949'))
            except Exception as exc:source_checks[sid]=dict(source_id=sid,status='BLOCKED',error=str(exc))
        out['source_bytes_check']=source_checks[sid]
        if source_checks[sid]['status']!='PASS':out.update(outcome='INSUFFICIENT_DATA',reason='Original bytes absent or hash mismatch')
        else:
            try:
                rows=trees[sid].xpath(c['position']['xpath'])
                if len(rows)!=1:raise ValueError('Expected one source row')
                parsed,tokens,issues=parsed_row(c,s,rows[0]);out.update(reviewed_fields=parsed,source_numeric_tokens=tokens,issues=issues)
                mismatches=[]
                for key,value in c['fields'].items():
                    # Unknown candidate cells can be filled by source review. An empty
                    # extracted list is not proof that the original says no drops/materials.
                    if value is None or value==[] or key.endswith('_source_token'):continue
                    if key=='learn_materials' and key in parsed:
                        left=[(norm(m['name']),m['quantity']) for m in value]
                        right=[(norm(m['name']),m['quantity']) for m in parsed[key] or []]
                        different=left!=right
                    else:different=key in parsed and value!=parsed[key]
                    if different:mismatches.append(dict(field=key,original=value,source_value=parsed[key]))
                out['corrected_fields']=mismatches
                sig=(c['category'],norm(c['name']),parsed.get('class_scope'),c['year'],json.dumps(parsed,ensure_ascii=False,sort_keys=True))
                has_information=any(value is not None for key,value in parsed.items() if key not in ['class_scope','item_kind','guide_location'])
                if mismatches:out.update(outcome='ERROR',reason='Candidate extraction differs from original cell; corrected values retained')
                elif any('C10_' in issue or 'C05_' in issue or 'COMPOSITE_' in issue for issue in issues):out.update(outcome='DEFERRED',reason='Source verified but identity or gameplay meaning remains conflicted')
                elif not has_information:out.update(outcome='INSUFFICIENT_DATA',reason='Original table contains no actionable numeric cell')
                elif sig in dedup:out.update(outcome='DUPLICATE',reason='Same category/name/class/year and reviewed fields',duplicate_of=dedup[sig])
                else:out.update(outcome='VERIFIED',reason='Every provided candidate numeric cell compared with hash-matched source row')
                dedup.setdefault(sig,c['id'])
                # Valid corrected rows are preserved even when the candidate itself was erroneous.
                confirmed.append(dict(id='R-'+c['id'],candidate_id=c['id'],category=c['category'],name=c['name'],year=c['year'],region='KR',
                                      game_version=None,class_scope=parsed.get('class_scope'),source_id=sid,source_url=s['final_url'],
                                      source_sha256=source_checks[sid]['sha256'],position=c['position'],fields=parsed,source_numeric_tokens=tokens,
                                      outcome=out['outcome'],issues=issues,evidence_status='SOURCE_CONTENT_CONFIRMED',game_runtime_verified=False))
            except Exception as exc:out.update(outcome='ERROR',reason=type(exc).__name__+': '+str(exc))
        reviews.append(out)
    OUT.mkdir(parents=True,exist_ok=True)
    for name,rows in [('CANDIDATE_REVIEW.jsonl',reviews),('VERIFIED_CANDIDATE_FACTS.jsonl',confirmed)]:
        (OUT/name).write_text(''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in rows))
    summary=dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command='python tools/review_restoration_candidates.py --private-dir '+args.private_dir,
                 input_rows=len(candidates),reviewed_rows=len(reviews),unique_input_ids=len({c['id'] for c in candidates}),
                 outcomes=dict(collections.Counter(r['outcome'] for r in reviews)),by_category={cat:dict(collections.Counter(r['outcome'] for r in reviews if r['category']==cat)) for cat in ['monster','item','spell','npc']},
                 source_checks=list(source_checks.values()),coverage_status='PASS_ALL_IDS_RECONCILED' if len(reviews)==len(candidates)==1674 else 'FAIL',
                 row_validation_status='PASS' if all(r['status']=='PASS' for r in source_checks.values()) else 'BLOCKED',runtime_status='NOT_RUN')
    (OUT/'CANDIDATE_REVIEW_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_checks'},ensure_ascii=False,indent=2))
    return int(summary['coverage_status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
