"""Synthetic test.* fixtures; none count as Work or restored content."""
import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from baram_content import PackageStore, IntakeError, encode, decode, sha, atomic_write, extract_zip, probability_ratio, round_half_away

COMMIT = "1" * 40
GAME = "2" * 40


def record(id="test.item.sword", kind="item", data=None, **fields):
    return dict(id=id, kind=kind, operation="add", data=data or dict(name="시험 검", values=dict(damage_max=7, stack_limit=1)),
                references=[], provenance_refs=["synthetic-test-not-original"], source_mode="INFERRED", **fields)


def package(root, records=None, batch="synthetic-1", **manifest_fields):
    root.mkdir(parents=True, exist_ok=True)
    contents = encode(records or [record()]);validation = encode(dict(status="PASS_SYNTHETIC_DATA_ONLY"))
    atomic_write(root / "contents.json", contents);atomic_write(root / "validation.json", validation)
    counts = {}
    for item in records or [record()]:counts[item["kind"]] = counts.get(item["kind"],0) + 1
    manifest = dict(protocol_id="BARAM_PARALLEL_V1", schema_id="BARAM_CONTENT_PACKAGE", schema_version=1, batch_id=batch,
                    producer="CodexTest", base_game_commit=GAME, files=[dict(path=n,bytes=len(d),sha256=sha(d)) for n,d in [("contents.json",contents),("validation.json",validation)]],
                    content_counts=counts, dependencies=[], external_references=[], required_capabilities=[])
    manifest.update(manifest_fields);atomic_write(root / "manifest.json", encode(manifest));return root


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = pathlib.Path(self.temp.name)
        self.baseline = {"legacy.item.sword":dict(id="legacy.item.sword",kind="item",data=dict(name="원래 검",values=dict(damage_max=5,price=20)),references=[])}
        self.store = PackageStore(self.root / "runtime",self.baseline,{"content.json.v1"})
    def tearDown(self):self.temp.cleanup()
    def run_package(self, records=None, batch="synthetic-1", **fields):
        p=package(self.root / ("pkg-"+batch),records,batch,**fields)
        return self.store.import_package(p,COMMIT,GAME,fixture=True)
    def test_idempotent_and_active_ledger(self):
        a=self.run_package();before=(self.store.root / "ACTIVE.json").read_bytes();b=self.run_package()
        self.assertEqual(a["import_status"],"IMPORTED");self.assertEqual(b["import_status"],"ALREADY_IMPORTED")
        self.assertEqual(before,(self.store.root / "ACTIVE.json").read_bytes());self.assertEqual(len(self.store.load()["records"]),1)
    def test_deterministic_fresh_outputs(self):
        a=self.run_package();other=PackageStore(self.root / "other",self.baseline,{"content.json.v1"})
        b=other.import_package(self.root / "pkg-synthetic-1",COMMIT,GAME,fixture=True);self.assertEqual(a["release_id"],b["release_id"])
    def test_same_batch_different_manifest_conflict(self):
        self.run_package();before=self.store.pointer();b=self.run_package([record(data=dict(name="변경 검",values=dict(damage_max=9)))])
        self.assertEqual(b["import_status"],"CONFLICT");self.assertEqual(before,self.store.pointer())
    def test_hash_mismatch_never_applies(self):
        p=package(self.root / "bad");(p / "contents.json").write_text("[]")
        r=self.store.import_package(p,COMMIT,GAME,fixture=True);self.assertEqual(r["import_status"],"REJECTED");self.assertIsNone(self.store.pointer())
    def test_reimport_bad_transfer_is_not_already(self):
        self.run_package();(self.root / "pkg-synthetic-1/contents.json").write_text("[]")
        r=self.store.import_package(self.root / "pkg-synthetic-1",COMMIT,GAME,fixture=True);self.assertEqual(r["import_status"],"REJECTED");self.assertEqual(len(self.store.load()["records"]),1)
    def test_forward_reference_file_order(self):
        a=record("test.quest.first","quest",dict(objectives=[]));a["references"]=["test.item.later"]
        b=record("test.item.later");r=self.run_package([a,b]);self.assertEqual(r["import_status"],"IMPORTED")
    def test_missing_reference(self):
        a=record();a["references"]=["test.item.missing"];r=self.run_package([a]);self.assertEqual(r["import_status"],"REJECTED")
    def test_duplicate_id(self):self.assertEqual(self.run_package([record(),record()])["import_status"],"REJECTED")
    def test_unknown_capability_is_pending(self):
        r=self.run_package(required_capabilities=["unknown.effect"]);self.assertEqual(r["import_status"],"PENDING_CAPABILITY");self.assertEqual(r["unmet_required_capabilities"],["unknown.effect"])
    def test_exact_dependency_required(self):
        self.assertEqual(self.run_package(dependencies=[dict(batch_id="missing",manifest_sha256="3"*64)])["import_status"],"WAITING_DEPENDENCY")
    def test_unpinned_dependency_rejected(self):self.assertEqual(self.run_package(dependencies=[dict(batch_id="anything")])["import_status"],"REJECTED")
    def test_old_patch_cannot_overwrite(self):
        p=record("test.item.proposal");p.update(operation="propose_patch",target_id="legacy.item.sword",data={"values.damage_max":9},preconditions={"values.damage_max":4})
        r=self.run_package([p]);self.assertEqual(r["import_status"],"CONFLICT");self.assertEqual(r["errors"][0]["current"],5)
    def test_patch_only_requested_field_and_stable_mapping(self):
        p=record("test.item.proposal");p.update(operation="propose_patch",target_id="legacy.item.sword",data={"values.damage_max":9},preconditions={"values.damage_max":5})
        r=self.run_package([p]);self.assertEqual(r["import_status"],"IMPORTED");s=self.store.load();self.assertEqual(s["records"]["legacy.item.sword"]["data"]["values"],dict(damage_max=9,price=20));self.assertEqual(s["id_map"][p["id"]],p["target_id"])
    def test_before_activation_failure_preserves_data_and_ledger(self):
        self.run_package();before=(self.store.root / "ACTIVE.json").read_bytes();p=package(self.root / "new",[record("test.item.new")],"new")
        r=self.store.import_package(p,COMMIT,GAME,fixture=True,interrupt="before_activate");self.assertEqual(r["import_status"],"VALIDATED_NOT_APPLIED");self.assertEqual(before,(self.store.root / "ACTIVE.json").read_bytes());self.assertNotIn("new",self.store.load()["imports"])
    def test_after_activation_receipt_recovery(self):
        p=package(self.root / "new");r=self.store.import_package(p,COMMIT,GAME,fixture=True,interrupt="after_activate");self.assertEqual(r["import_status"],"IMPORTED");self.assertEqual(self.store.import_package(p,COMMIT,GAME,fixture=True)["import_status"],"ALREADY_IMPORTED")
    def test_supersedes_keeps_id(self):
        self.run_package();r=self.run_package([record(data=dict(name="새 이름",values=dict(damage_max=8)))],"replacement",supersedes=["synthetic-1"])
        self.assertEqual(r["import_status"],"IMPORTED");s=self.store.load();self.assertEqual(len(s["records"]),1);self.assertEqual(s["id_map"]["test.item.sword"],"test.item.sword")
    def test_current_manifest_corruption_detected_and_recovered(self):
        self.run_package();self.run_package([record("test.item.new")],"new");active=self.store.pointer();p=self.store.root / "releases" / active["release_id"] / "release.json";p.write_text("{}")
        with self.assertRaises(IntakeError):self.store.load()
        state=self.store.recover_previous();self.assertEqual(set(state["imports"]),{"synthetic-1"})
    def test_negative_ac_is_allowed(self):self.assertEqual(self.run_package([record(data=dict(values=dict(armor_class=-11)))])["import_status"],"IMPORTED")
    def test_time_not_rounded_to_zero(self):
        r=self.run_package([record(data=dict(values=dict(cooldown_ms=300))) ]);self.assertEqual(r["import_status"],"IMPORTED");self.assertEqual(self.store.load()["records"]["test.item.sword"]["data"]["values"]["cooldown_ms"],300)
    def test_wrong_ms_precision(self):self.assertEqual(self.run_package([record(data=dict(values=dict(cooldown_ms=0.3)))])["import_status"],"REJECTED")
    def test_exact_rare_probability(self):
        self.assertEqual(probability_ratio("0.000000001"),dict(numerator=1,denominator=1000000000))
        self.assertEqual(probability_ratio(dict(numerator=100,denominator=1000000)),dict(numerator=100,denominator=1000000))
    def test_half_away_and_probability_bounds(self):
        self.assertEqual([round_half_away(x) for x in [137.5,-137.5,0.5,-0.5]],[138,-138,1,-1])
        for value in [-0.1,1.1,"0.00000000000000000001"]:
            with self.assertRaises(IntakeError):probability_ratio(value)
    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(IntakeError):decode(b'{"id":1,"id":2}')
    def test_zip_traversal_links_expansion(self):
        for index,name in enumerate(["../escape","/absolute","C:/overwrite"]):
            p=self.root / (str(index)+".zip")
            with zipfile.ZipFile(p,"w") as z:z.writestr(name,b"bad")
            with self.assertRaises(IntakeError):extract_zip(p,self.root / ("out"+str(index)))
        p=self.root / "big.zip"
        with zipfile.ZipFile(p,"w") as z:z.writestr("big",b"A"*100)
        with self.assertRaises(IntakeError):extract_zip(p,self.root / "out-big",maximum=50)
    def test_published_schema_hash_and_validation(self):
        p=package(self.root / "schema");m=decode((p / "manifest.json").read_bytes());schema=encode({"$schema":"https://json-schema.org/draft/2020-12/schema","type":"array","items":{"type":"object","required":["not_present"]}})
        (p / "schema.json").write_bytes(schema);m["files"].append(dict(path="schema.json",bytes=len(schema),sha256=sha(schema),kind="schema"));m["schema_hashes"]={"schema.json":sha(schema)};m["files"][0]["schema"]="schema.json";(p / "manifest.json").write_bytes(encode(m))
        r=self.store.import_package(p,COMMIT,GAME,fixture=True);self.assertEqual(r["import_status"],"REJECTED");self.assertEqual(r["errors"][0]["code"],"SCHEMA_VALIDATION")


    def test_partial_scope_extends_without_duplicate_or_repatch(self):
        first=record('test.item.first');second=record('test.item.second')
        p=package(self.root/'partial',[first,second])
        self.store.selection={'synthetic-1':{'test.item.first'}}
        r=self.store.import_package(p,COMMIT,GAME,fixture=True)
        self.assertEqual(r['import_status'],'PARTIALLY_IMPORTED');self.assertEqual(r['held_ids'],['test.item.second'])
        self.assertEqual(self.store.import_package(p,COMMIT,GAME,fixture=True)['import_status'],'ALREADY_IMPORTED')
        self.store.selection={}
        r=self.store.import_package(p,COMMIT,GAME,fixture=True)
        self.assertEqual(r['import_status'],'IMPORTED');self.assertEqual(len(self.store.load()['records']),2)

    def test_partial_scope_does_not_resolve_unapplied_reference(self):
        a=record('test.item.first');a['references']=['test.item.second']
        p=package(self.root/'partial',[a,record('test.item.second')])
        self.store.selection={'synthetic-1':{'test.item.first'}}
        r=self.store.import_package(p,COMMIT,GAME,fixture=True)
        self.assertEqual(r['import_status'],'WAITING_DEPENDENCY');self.assertIsNone(self.store.pointer())

    def test_published_absence_guard_preserves_source_values(self):
        p=record('test.item.proposal');p.update(operation='propose_patch',target_id='legacy.item.sword',
            data={'name':'runtime sword','stats':{'damage_max':8}},changes=[{'path':'runtime_definition','before':{'exists':False},'after':{'name':'runtime sword','stats':{'damage_max':8}},'reason':'test','provenance_ref':'test'}])
        r=self.run_package([p]);self.assertEqual(r['import_status'],'IMPORTED')
        active=self.store.load()['records']['legacy.item.sword']
        self.assertEqual(active['data']['values']['damage_max'],5)
        self.assertEqual(active['runtime_definition']['stats']['damage_max'],8)
        r=self.run_package([p],'other');self.assertEqual(r['import_status'],'CONFLICT')

    def test_rebuilt_members_require_exact_published_hash(self):
        raw=b'not-a-real-wave';a=record('test.asset.audio','asset',{'name':'synthetic','asset_type':'blob','acquisition':{'bundle_id':'test.bundle','member':'audio.bin','sha256':sha(raw)},'metadata':{}})
        p=package(self.root/'member',[a]);acquisition=encode({'bundle_id':'test.bundle','size_bytes':1,'sha256':'a'*64})
        (p/'acquisition.json').write_bytes(acquisition);m=decode((p/'manifest.json').read_bytes());m['files'].append({'path':'acquisition.json','bytes':len(acquisition),'sha256':sha(acquisition)});(p/'manifest.json').write_bytes(encode(m))
        directory=self.root/'rebuild';directory.mkdir();(directory/'audio.bin').write_bytes(b'wrong')
        self.store.member_dirs={'test.bundle':directory}
        r=self.store.import_package(p,COMMIT,GAME,fixture=True)
        self.assertEqual(r['import_status'],'REJECTED');self.assertIsNone(self.store.pointer())
        (directory/'audio.bin').write_bytes(raw)
        r=self.store.import_package(p,COMMIT,GAME,fixture=True)
        self.assertEqual(r['import_status'],'IMPORTED');self.assertFalse(r['whole_private_zip_acquired'])

    def test_published_partial_patch_never_replaces_unrelated_fields(self):
        first=record('test.item.initial');first.update(operation='propose_patch',target_id='legacy.item.sword',data={'name':'old','stats':{'damage':5},'other':7},changes=[{'path':'runtime_definition','before':{'exists':False},'after':{'name':'old','stats':{'damage':5},'other':7}}])
        self.assertEqual(self.run_package([first])['import_status'],'IMPORTED')
        second=record('test.item.later');second.update(operation='propose_patch',target_id='legacy.item.sword',data={'name':'old','stats':{'damage':8},'other':99},changes=[{'path':'runtime_definition.stats.damage','before':{'exists':True,'value':5},'after':8}])
        self.assertEqual(self.run_package([second],'later')['import_status'],'IMPORTED')
        self.assertEqual(self.store.load()['records']['legacy.item.sword']['runtime_definition']['other'],7)

    def test_dependency_package_commit_checked_even_when_manifest_matches(self):
        initial=self.run_package()
        receipt=self.run_package([record('test.item.next')],'next',dependencies=[{'batch_id':'synthetic-1','manifest_sha256':initial['manifest_sha256'],'package_commit':'f'*40}])
        self.assertEqual(receipt['import_status'],'WAITING_DEPENDENCY')

if __name__ == "__main__":unittest.main()
