"""Fresh reconstruction tests. Synthetic fixtures are not gameplay evidence."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import baram_content
from baram_content import PackageStore, IntakeError, atomic_write, decode, encode, sha
from prepare_recovery_content import release_pointer, semantic_content, prepare


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def test_pointer_requires_exact_hash_and_rejects_path_escape(self):
        raw=encode({'generation':7});ident=sha(raw)
        atomic_write(self.root/'private_content/releases'/ident/'release.json',raw)
        self.assertEqual(release_pointer(self.root,ident)['generation'],7)
        with self.assertRaises(ValueError):release_pointer(self.root,'../bad')
        atomic_write(self.root/'private_content/releases'/ident/'release.json',b'changed')
        with self.assertRaises(ValueError):release_pointer(self.root,ident)

    def test_semantic_comparison_ignores_only_consumer_commit(self):
        a={'records':{'item':{'name':'original'}},'imports':{'batch':{'applied_before_game_commit':'a','source_commit':'pinned'}}}
        b=copy.deepcopy(a);b['imports']['batch']['applied_before_game_commit']='b'
        self.assertEqual(semantic_content(a),semantic_content(b))
        b['records']['item']['name']='changed'
        self.assertNotEqual(semantic_content(a),semantic_content(b))
        self.assertEqual(a['imports']['batch']['applied_before_game_commit'],'a')

    def test_existing_or_nested_output_is_rejected_before_writing(self):
        from types import SimpleNamespace
        source=self.root/'source';source.mkdir()
        with self.assertRaises(ValueError):
            prepare(SimpleNamespace(repo=str(self.root),runtime=str(source),output=str(source/'nested')))
        occupied=self.root/'occupied';occupied.mkdir()
        with self.assertRaises(ValueError):
            prepare(SimpleNamespace(repo=str(self.root),runtime=str(source),output=str(occupied)))
        self.assertFalse((source/'nested').exists())

    def test_windows_atomic_write_skips_directory_open(self):
        # Executes the Windows code branch on this host; not a native Windows
        # platform certification. The real tempfile/file replace still runs.
        with mock.patch.object(baram_content,'os',wraps=os) as wrapped:
            wrapped.name='nt'
            atomic_write(self.root/'windows-branch.bin',b'kept')
            wrapped.open.assert_not_called()
        self.assertEqual((self.root/'windows-branch.bin').read_bytes(),b'kept')

    def test_followup_reads_verified_old_member_instead_of_local_namesake(self):
        raw=b'pinned shared member'
        old=baram_content.empty_release();member_path=sha(raw)+'/sheet.bin'
        info={'stored_path':member_path,'sha256':sha(raw),'bytes':len(raw)}
        old['assets']['bundle_file:test.bundle:sheet.bin']=info
        old_bytes=encode(old);ident=sha(old_bytes)
        store=PackageStore(self.root/'runtime',{})
        atomic_write(store.root/'releases'/ident/'release.json',old_bytes)
        atomic_write(store.root/'releases'/ident/'files'/member_path,raw)
        atomic_write(store.root/'ACTIVE.json',encode({'release_id':ident,'bytes':len(old_bytes),'sha256':ident}))
        package=self.root/'package';package.mkdir()
        record={'id':'test.asset.reused','kind':'asset','operation':'add','source_mode':'DERIVED','references':[],'provenance_refs':[],
                'data':{'name':'shared','asset_type':'blob','acquisition':{'bundle_id':'test.bundle','member':'sheet.bin','sha256':sha(raw)}}}
        contents=encode([record]);validation=encode({'status':'PASS_SYNTHETIC_ONLY'})
        files=[]
        for name,data in [('contents.json',contents),('validation.json',validation)]:
            atomic_write(package/name,data);files.append({'path':name,'bytes':len(data),'sha256':sha(data)})
        manifest={'protocol_id':baram_content.PROTOCOL,'schema_id':'BARAM_CONTENT_PACKAGE','schema_version':1,'batch_id':'synthetic',
                  'producer':'CodexTest','base_game_commit':'a'*40,'files':files,'counts':{'asset':1}}
        atomic_write(package/'manifest.json',encode(manifest))
        result=store.import_package(package,'b'*40,'c'*40,fixture=True)
        self.assertEqual(result['import_status'],'IMPORTED')
        self.assertEqual(store.load()['assets'][record['id']]['sha256'],sha(raw))

    def test_npc_resolution_rejects_mixed_fields_wrong_pin_and_missing_capability(self):
        old={'services':[{'type':'old'}],'dialogue':[{'text':'old'}]}
        shield={'services':[{'type':'old'},{'type':'shield'}],'dialogue':[{'text':'shield'}]}
        bow={'services':[{'type':'old'},{'type':'bow'}],'dialogue':[{'text':'bow'}]}
        both={'services':[{'type':'old'},{'type':'shield'},{'type':'bow'}],'dialogue':[{'text':'both'}]}
        document={'source_packages':[{'batch_id':'WK-CONTENT-008','manifest_sha256':'8'*64,'package_commit':'8'*40},
                                    {'batch_id':'WK-CONTENT-010','manifest_sha256':'a'*64,'package_commit':'a'*40}],
                  'npc_resolutions':[{'target_id':'npc','source_proposal_ids':['proposal'],'field_paths':['services','dialogue'],
                    'accepted_exact_field_sets':{'common_baseline':old,'content008_only':shield,'content010_only':bow,'already_reconciled':both},'merged_fields':both}]}
        store=PackageStore(self.root/'runtime',{},capabilities={'fan_weapon_animation_attachment','offhand_slot_and_shield_animation_attachment',
                  'original_bow_firing_pose_attachment','ranged_physical_weapon_attack'},npc_reconciliation={
                      'document':document,'sha256':'d'*64,'source_commit':'d'*40,'path':'resolution.json'})
        target={'data':dict(shield,unrelated='preserved')}
        ledger={'imports':{'WK-CONTENT-008':{'status':'IMPORTED','manifest_sha256':'8'*64,'source_commit':'8'*40}}}
        guards={k:{'exists':True,'value':v} for k,v in old.items()}
        def call(value=target,current=ledger):
            return store._reconcile_npc_fields({'id':'proposal','target_id':'npc'},value,{'batch_id':'WK-CONTENT-010'},'a'*40,current,bow,guards,{'manifest_sha256':'a'*64})
        changes,_,proof=call();self.assertEqual(changes,both);self.assertEqual(proof['accepted_state'],'content008_only')
        self.assertEqual(target['data']['unrelated'],'preserved')
        with self.assertRaises(IntakeError):call({'data':dict(shield,dialogue=old['dialogue'])})
        bad=copy.deepcopy(ledger);bad['imports']['WK-CONTENT-008']['source_commit']='f'*40
        with self.assertRaises(IntakeError):call(current=bad)
        store.capabilities.remove('ranged_physical_weapon_attack')
        with self.assertRaises(IntakeError):call()


if __name__=='__main__':unittest.main()
