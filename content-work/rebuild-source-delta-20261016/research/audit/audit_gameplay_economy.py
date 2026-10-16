"""Independent source/record/join audit of the proposed economy/AI deltas.

Does not run the derivation tool and never imports any reference game code.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent/'gameplay_economy'
PRIVATE=Path('/workspace/scratch/3624c67f59e8/private_delta/gameplay_economy')
BASE=Path('/workspace/scratch/68a0f3ea5a03/receiver/package/docs/rebuild/p1_5')


def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(r):return sha(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def rows(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def collapse(s):return re.sub(r'\s+',' ',s).strip()
def no_space(s):return re.sub(r'\s+','',s)


class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def main():
    errors=[];checks=0
    def check(ok,label):
        nonlocal checks
        checks+=1
        if not ok:errors.append(label)
    pub=rows(RESEARCH/'field_candidates.jsonl')
    priv=rows(PRIVATE/'field_candidates.private.jsonl')
    by={r['candidate_id']:r for r in priv}
    check(len(pub)==126 and len(priv)==126 and len(by)==126,'expected nonempty complete candidate set')
    table={};tablefile={};tableline={};source_bytes={}
    catalog=json.loads((BASE/'selected_content/catalog.json').read_text())['normalized_catalogs']
    for name in ['kr_official_items.jsonl','kr_official_core.jsonl','kr_official_services.jsonl','kr_official_crafting_facts.jsonl']:
        p=BASE/'selected_content'/name;b=p.read_bytes();spec=next(c for c in catalog if Path(c['path']).name==name)
        check(sha(b)==spec['sha256'] and len(b)==spec['bytes'],'baseline whole-file bytes '+name)
        values=rows(p);check(len(values)==spec['records'],'baseline row count '+name)
        for line,r in enumerate(values,1):table[r['content_id']]=r;tablefile[r['content_id']]=name;tableline[r['content_id']]=line
    for p in (PRIVATE/'source_bytes').glob('*.html'):
        b=p.read_bytes();check(sha(b)==p.stem,'HTML source bytes '+p.stem);source_bytes[p.stem]=b
    check(len(source_bytes)==32,'32 unique prior HTML references')
    semantic_counts={}
    for r in pub:
        cid=r['candidate_id'];p=by[cid];private_ref=r['private_value']
        check(private_ref['candidate_id']==cid and canonical(p)==private_ref['record_canonical_sha256'],'private record canonical hash '+cid)
        check('candidate_value' not in r and 'original_value' not in r,'public excludes candidate/original payload '+cid)
        check(p['test_status']=='NOT_RUN' and p['new_runtime_binding']=='NOT_STARTED' and p['adoption_status']=='UNACKNOWLEDGED' and p['global_default_selected'] is False,'runtime/adoption boundary '+cid)
        check(r['existing_record_ids']==p['existing_record_ids'],'public/private stable refs '+cid)
        owner=table[p['content_id']]
        check(canonical(owner)==p['expected_existing_record_sha256'],'expected existing owner hash '+cid)
        for e in p['source_evidence']:
            rid=e['content_id'];row=table.get(rid);loc=e['normalized_locator'];name=Path(loc['path']).name
            check(row is not None and tablefile[rid]==name and tableline[rid]==loc['line'],'stable row/file/line '+cid+':'+rid)
            check(canonical(row)==loc['record_canonical_sha256'],'stable canonical hash '+cid+':'+rid)
            check(row['build_profile_id']==p['build_profile_id'],'same profile '+cid+':'+rid)
            check(row['input_sha256']==e['input_sha256'] and row['source_locator']==e['source_locator'],'original source locator/hash '+cid+':'+rid)
            b=source_bytes[e['input_sha256']]
            check(sha(b)==e['input_sha256'],'source actual bytes '+cid+':'+rid)
            source_loc=e['source_locator'];lo=source_loc.get('line_start',source_loc.get('html_line_start'));hi=source_loc.get('line_end',lo+36)
            lines=b.decode('cp949').splitlines()
            check(0<lo<=len(lines) and lo<=hi,'source line bounds '+cid+':'+rid)
        v=p['candidate_value'];kind=p['kind'];field=p['field']
        semantic_counts[kind]=semantic_counts.get(kind,0)+1
        if kind=='EXISTING_SOURCE_NEW_SEMANTICS':
            e=p['source_evidence'][0];loc=e['source_locator'];lines=source_bytes[e['input_sha256']].decode('cp949').splitlines();parser=Text();parser.feed('\n'.join(lines[loc['line_start']-1:loc['line_end']]))
            text=collapse(' '.join(parser.parts))
            check(p['entity_name_ko'] in text,'same named monster in original row '+cid)
            check(collapse(v['documented_original']) in text,'independent HTMLParser qualitative phrase '+cid)
            if 'documented_spell_name' in v:check(v['documented_spell_name'] in text,'named spell explicit source '+cid)
            for uncertain in ['attack_interval','spell_native_id','target_geometry','hp_threshold','flee_speed','duration','damage']:
                if uncertain in v:check(v[uncertain] is None,'no invented numeric/native '+cid+':'+uncertain)
        elif field.startswith('shop.stock_relation.'):
            direction=v['trade_direction'];key='sale_tokens' if direction=='npc_sells' else 'buy_only_tokens';token=v['documented_original']
            check(token in owner['original_value'][key],'same NPC explicit trade direction/token '+cid)
            for itemid in v['item_content_ids']:check(no_space(table[itemid]['entity_name_ko'])==no_space(token),'item exact/whitespace relation '+cid+':'+itemid)
            check(v['actual_npc_sell_price'] is None and v['actual_npc_buy_price'] is None,'no unproven transaction price '+cid)
        elif field=='skill.learning.teacher_and_material_relations':
            orig=owner['original_value'];job=v['job']
            check(job==orig['job'] and v['learn_level']==orig['learn_level'] and v['learn_money']==orig['learn_money'],'job-specific original learn rule '+cid)
            teachers=v['teacher_candidates_by_country']
            check(len(teachers)==2,'two city guild teacher candidates '+cid)
            for t in teachers:
                row=table[t['teacher_id']]['original_value'];check(job+'길드' in row['location_label_documented'] and 'teach_skill' in row['services'],'same job teacher capability '+cid)
        elif field.startswith('monster.drop_item_relation.'):
            token=v['documented_original'];check(token in owner['original_value']['possible_item_names'],'explicit possible drop name '+cid)
            for itemid in v['candidate_item_ids']:check(no_space(table[itemid]['entity_name_ko'])==no_space(token),'same name possible drop item '+cid)
            check(v['probability'] is None and v['quantity'] is None,'drop exact rate/quantity unasserted '+cid)
        elif kind=='EXISTING_DATA_LOCATION_RELATION_HYPOTHESIS':
            check(v['exact_npc_script_or_dialogue_verified'] is False and p['certainty']=='LOCATION_INFERENCE','craft location only inference '+cid)
            check(table[v['candidate_service_id']]['entity_name_ko']==v['candidate_npc_name'],'named service candidate exists '+cid)
        elif kind=='EXISTING_SOURCE_CONFLICT_IDENTIFIED':
            check(v['selected_price'] is None,'price conflict no selected price '+cid)
            for row in v['documented_original']:
                original=table[row['item_id']];check(original['original_value']['listed_price']==row['value'],'conflict original listed prices '+cid)
        else:errors.append('unreviewed candidate kind '+cid)
    result={'schema':'baram.work_delta.gameplay_independent_ai_audit/1','result':'PASS' if not errors else 'FAIL','scope':'126 proposed field/reference records; public/private canonical hashes, 4 frozen table identities, 32 actual prior HTML bytes, profile and ID joins; explicit qualitative text checked with HTMLParser independent of derivation regex','checks':checks,'candidate_records':len(pub),'candidate_kinds':semantic_counts,'errors':errors,'new_original_downloads':0,'runtime':'NOT_RUN','historical_accuracy':'PARTIAL_NOT_A_GLOBAL_PASS','limits':['Independent semantic review covers explicit phrases and relation constraints; no original runtime observations or complete historical behavior proof.','Existing official pages are one shared source family and their snapshot profiles do not establish exact client build.','The 32 HTML files are prior-input verification copies; a final immutable batch can reference their P1.5 hashes instead of duplicating them.']}
    (HERE/'GAMEPLAY_ECONOMY_INDEPENDENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
