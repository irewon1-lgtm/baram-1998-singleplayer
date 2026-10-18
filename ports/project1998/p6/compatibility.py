"""Finite source comparison, explicit omissions, and executed NPC-placement proof."""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    for k in ['experiment','qa','output']:p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();exp=a.experiment;qa=json.loads(a.qa.read_text());base=json.loads((exp/'P5_SOURCE_AUDIT.json').read_text());art=json.loads((exp/'REFERENCE_ART_AUDIT.json').read_text())
    placements=qa['npc_placements'];candidates={r['npc']:r for r in art['npc_candidates']};checks=[]
    for n in placements:
        row=candidates[int(n['npc'])];pos=list(map(int,n['position']))
        coverage=next((c[2] for c in row['candidates'] if c[:2]==pos),row['source_visual_coverage'] if pos==row['source'] else None)
        checks.append({'npc':n['npc'],'native_floor_accessible':n['accessible'],'source':n['source'],'position':pos,'changed':n['changed'],'visible_object_coverage':coverage,'status':'PASS' if n['accessible'] and coverage is not None and coverage<=0.04 else 'FAIL'})
    changed=[x for x in base['bounded_content'] if x.get('kept_rows')!=x.get('source_rows')]
    result={'status':'PASS_DECLARED_COMPARISON_AND_NPC_SCOPE' if all(x['status']=='PASS' for x in checks) else 'FAIL',
        'original_commit':'65cb3ef28f289ee35d19abfb6829d6120b9ec0cd','original_repository':'https://github.com/project1998/Project1998',
        'comparison':'pinned original source and every CSV preparation selection; not a claim of full-world equivalence',
        'capsule_sha256':hashlib.sha256((exp/'runtime/capsule.json').read_bytes()).hexdigest(),
        'denominators':{'map_metadata_rows':9850,'map_index_rows':2031,'included_maps':47,'original_npc_rows':380,'included_npc_instances':36},
        'all_content_tables':base['bounded_content'],'filtered_or_empty_tables':changed,'npc_execution':checks,
        'repaired_npc_count':sum(x['changed'] for x in checks),'restored_merchant_icon_count':len(art['supplemental_item_icons']),
        'remaining_icon_keys':art['merchant_icon_gaps'],
        'retained_native_bindings':['walk/turn/attack','pickup','use/eat/equip/unequip','native spell casting and paid learning','NPC click/menu/text/input','shop categories/buy/sell/confirmation/amount','ordinary speech including Lua speech handlers','F1 central functions','drop one/drop stack','original mini-text/speech event history','original running timed-effect names and remaining time'],
        'unported_or_not_equivalent':[
            '47-map starting region only; remaining indexed maps/geography are absent, not marked playable',
            '4 harvesting definitions 542..545 and 52 fixed spawn rows still deferred from the prior capsule',
            '51 boundary warp rows retain native rejection for destinations outside the capsule; 3 original out-of-bounds/duplicate tutorial source rows remain recorded in REGION_SOURCE_AUDIT.json',
            'Gold-drop, item-throw and the complete original dedicated packet/UI collection are not all bound; multiplayer exchange/group/clan/boards are not reproduced as a complete offline social simulation',
            'MIDI music and complete spell-effect/ghost/morph/riding/face/hair/equipment visual layers remain incomplete',
            'Supplied screenshot decoration and scalable live layout reproduce the reference hierarchy and brown palette; the supplied English-client DAT/font differs from the original Korean-client skin. Full pixel-by-pixel equivalence is not asserted',
            'Full quest completion for all retained NPCs is not inferred from source loading, placement access, or representative GUI flows',
            'Current APK Android/Galaxy execution, actual IME/rotation/lifecycle/FPS/heat/battery remain NOT_RUN_DEVICE'
        ]}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result['status'],'NPC',len(checks),'moved',result['repaired_npc_count'],'icons',result['restored_merchant_icon_count']);assert result['status']!='FAIL'

if __name__=='__main__':main()
