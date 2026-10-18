"""Join reviewed display fields by original numeric ID AND immutable key.

This never modifies a rule CSV, Lua program, price, spell cost or save capsule.
Candidate wording and composed names are translations, not era certification.
"""
import argparse,csv,hashlib,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'p5'))
from scope import MAPS,EXCLUDED_NPCS,DEFERRED_MOBS,rows

def clean(s):return s.replace("\\'", "'")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    for k in ['source','ko-source','output','audit']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();source=a.source/'game-data';ko=a.ko_source/'game-data-ko'
    manual=json.loads((HERE/'translations.json').read_text());catalog={'schema':1,'text':manual['text'],'patterns':manual['patterns'],'names':dict(manual['names']),'entities':{}}
    audit={'method':'presentation-only join on (original ID, immutable identifier); candidate and proper-name era accuracy REVIEW',
           'inputs':[],'categories':{},'rows':[],'unmatched_manual_names':[]}
    columns=[('maps','Maps.csv','MapId','MapId','MapName'),('items','Items.csv','ItmId','ItmIdentifier','ItmDescription'),
             ('spells','Spells.csv','SplId','SplIdentifier','SplDescription'),('npcs','NPCs.csv','NpcId','NpcIdentifier','NpcDescription'),
             ('mobs','mobs.csv','MobId','Identifier','Description')]
    npcs=[r for r in rows(source/'NPCs.csv') if int(r['NpcMapId']) in MAPS and r['NpcIdentifier'] not in EXCLUDED_NPCS]
    npc_keys={r['NpcIdentifier'] for r in npcs}
    regional_items=set('sword_of_power swift_dagger staff_of_power staff_of_defense jade_scale_mail summer_mail_dress merchant_waistcoat summer_blouse summer_garb summer_dress summer_robes summer_gown merchant_helm spring_helmet wooden_saber spring_garb novice_sword acorn rabbit_meat bears_liver herb_pipe'.split())
    for r in rows(source/'ShopStock.csv'):
        if r['NpcIdentifier'] in npc_keys:regional_items.update(r['ItemKeys'].split('|'))
    for r in rows(source/'ShopBuysFrom.csv'):
        if r['NpcIdentifier'] in npc_keys:regional_items.update(k for k in r['ItemKeys'].split('|') if k!='-')
    mob_ids={r['SpnMobId'] for r in rows(source/'Spawns.csv') if int(r['SpnMapId']) in MAPS}
    mob_ids|={r['MobId'] for r in rows(source/'AreaSpawns.csv') if int(r['Map']) in MAPS};mob_ids-=DEFERRED_MOBS
    mob_keys={r['Identifier'] for r in rows(source/'mobs.csv') if r['MobId'] in mob_ids}
    for r in rows(source/'MobDrops.csv'):
        if r['MobKey'] in mob_keys:
            for field in ['Loot','RareLoot']:
                regional_items.update(entry.split(':')[0] for entry in r[field].split('|') if entry)
    used=set()
    for category,file,idcol,keycol,namecol in columns:
        original=rows(source/file);candidate={r[idcol]:r for r in rows(ko/file)}
        audit['inputs'].append({'file':file,'original_sha256':sha(source/file),'candidate_sha256':sha(ko/file)})
        total=applied=regional=regional_applied=0
        for r in original:
            key=r[keycol];raw=clean(r[namecol]);c=candidate.get(r[idcol]);proposed=raw;origin='ORIGINAL_FALLBACK'
            if c is not None:
                assert c[keycol]==key,('immutable translation key changed',file,r[idcol])
                if re.search('[가-힣]',c[namecol]):proposed=clean(c[namecol]);origin='KO_CANDIDATE_REVIEW_ERA'
            if raw in manual['names']:
                proposed=manual['names'][raw];origin='P6_TRANSLATION_REVIEW_ERA';used.add(raw)
            # Narrow clothing morphology only. No fuzzy substitutions for lore,
            # quest prose or the native name sent to a merchant.
            if category=='items' and raw not in manual['names']:
                words=raw.lower().split();vocabulary=manual['clothing_words']
                if words and all(w in vocabulary for w in words):proposed=' '.join(vocabulary[w] for w in words);origin='COMPOSED_TRANSLATION_REVIEW_ERA'
            in_scope=(int(r[idcol]) in MAPS if category=='maps' else key in regional_items if category=='items' else
                      r in npcs if category=='npcs' else r[idcol] in mob_ids if category=='mobs' else
                      r['SplPthId'] in ['0','1','2','3','4'] and r['SplAlignment'] in ['0','-1'] and not key.startswith('='))
            full=bool(re.search('[가-힣]',proposed)) and not re.search('[A-Za-z]',proposed)
            total+=1;applied+=full;regional+=in_scope;regional_applied+=full and in_scope
            if proposed!=raw:
                catalog['names'][raw]=proposed;catalog['entities'][category+':'+r[idcol]]=proposed
                if category=='spells':catalog['entities']['spell:'+key]=proposed
                if category=='items':catalog['entities']['item:'+key]=proposed
                if category=='mobs':catalog['entities']['mob:'+key]=proposed
            audit['rows'].append({'category':category,'id':r[idcol],'key':key,'original':raw,'display':proposed,'scope':in_scope,
                                  'fully_korean':full,'provenance':origin,'era_review':'REVIEW' if proposed!=raw else 'NOT_TRANSLATED'})
            if category=='spells' and c is not None and c.get('SplQuestion')!=r.get('SplQuestion') and re.search('[가-힣]',c.get('SplQuestion','')):
                catalog['text'][clean(r['SplQuestion'])]=clean(c['SplQuestion'])
        audit['categories'][category]={'all_rows':total,'all_fully_korean':applied,'regional_rows':regional,'regional_fully_korean':regional_applied,
             'regional_application_percent':round(100*regional_applied/regional,2) if regional else None,'execution_verified':'see real GUI evidence, not inferred from application'}
    audit['unmatched_manual_names']=sorted(set(manual['names'])-used)
    audit['dialogue']={'exact_entries':len(catalog['text']),'dynamic_patterns':len(catalog['patterns']),
                      'coverage':'selected tutorial, merchants and four trainer flows; later quests retain original fallback; no all-dialogue claim'}
    a.output.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n');a.audit.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit['categories'],ensure_ascii=False))
if __name__=='__main__':main()
