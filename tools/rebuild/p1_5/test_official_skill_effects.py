#!/usr/bin/env python3
"""Actual-source coverage, semantic regressions and isolated failure propagation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--repo", default=".")
parser.add_argument("--source-manifest", required=True)
args = parser.parse_args()
REPO = Path(args.repo).resolve()
SCRIPT = REPO / "tools/rebuild/p1_5/extract_official_skill_effects.py"
ROOT = REPO / "docs/rebuild/p1_5"
CORE = ROOT / "selected_content/kr_official_core.jsonl"
ROWS = list(map(json.loads, (ROOT / "selected_content/kr_official_skill_effects.jsonl").read_text().splitlines()))
SPEC = importlib.util.spec_from_file_location("official_effects_test_target", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TestOfficialEffects(unittest.TestCase):
    def matching(self, name):
        return [row for row in ROWS if row["entity_name_ko"] == name]

    def test_all377_actual_source_cells_and_fact_anchors(self):
        parents = {r["content_id"]: r for r in map(json.loads, CORE.read_text().splitlines()) if r["record_type"] == "skill"}
        sources = {s["source_id"]: s for s in json.loads(Path(args.source_manifest).read_text())}
        self.assertEqual(set(parents), {r["parent_content_id"] for r in ROWS})
        self.assertEqual(len(ROWS), 377)
        for row in ROWS:
            parent = parents[row["parent_content_id"]]
            text, _ = MOD.get_description(parent, sources[row["source_ids"][0]])
            for fact in row["original_value"]["published_effect_facts"]:
                fragment = text[fact["description_char_start"]:fact["description_char_end"]]
                self.assertEqual(MOD.sha(fragment.encode()), fact["evidence_fragment_sha256"])
                self.assertEqual(fact["value"], row["selected_original_value"][fact["field_path"].removeprefix("skill.effect.")])

    def test_mp_restore_is_not_resurrection(self):
        allowed = {"공력증강", "공력증가", "공력주입"}
        self.assertEqual({r["entity_name_ko"] for r in ROWS if "effect_type.MP_RESTORE" in r["selected_original_value"]}, allowed)
        for row in self.matching("부활"):
            selected = row["selected_original_value"]
            self.assertTrue(selected["effect_type.RESURRECTION"])
            self.assertEqual(selected["cost.mp"]["mode"], "all")
            self.assertNotIn("effect_type.MP_RESTORE", selected)

    def test_percent_interval_reflection_and_damage_are_distinct(self):
        for row in self.matching("노도성황"):
            self.assertEqual(row["selected_original_value"]["damage.periodic_hp_loss"]["fraction"], 0.03)
            self.assertEqual(row["selected_original_value"]["damage.periodic_hp_loss"]["interval_unit"], "second")
        for row in self.matching("반탄공"):
            self.assertEqual(row["selected_original_value"]["reflection.probability"]["value"], 0.5)
            self.assertIsNone(row["original_value"]["cast_success_probability"])
        for row in self.matching("보호"):
            self.assertEqual(row["selected_original_value"]["damage.incoming_multiplier"]["value"], 0.5)
            self.assertIsNone(row["original_value"]["duration_seconds"])

    def test_pull_blink_and_archival_target_changes(self):
        for row in self.matching("초혼비무"):
            self.assertTrue(row["selected_original_value"]["movement.pull_target_to_caster_front_then_attack"])
            self.assertNotIn("movement.caster_to_target_then_attack", row["selected_original_value"])
        for row in self.matching("쇄혼비무"):
            self.assertTrue(row["selected_original_value"]["movement.caster_to_target_then_attack"])
        for row in self.matching("파력무참"):
            selected = row["selected_original_value"]
            self.assertEqual(selected["damage.conditional_multiplier"]["scope"], "finisher_magic_attack_only")
            self.assertEqual("target.group_members" in selected, row["build_profile_id"] == "KR_GUIDE_2000_SNAPSHOT")
            self.assertEqual("target.all_nearby_people_and_monsters" in selected, row["build_profile_id"] == "KR_GUIDE_2001_SNAPSHOT")

    def test_no_invented_recipient_or_immediate_damage(self):
        for row in self.matching("투명"):
            self.assertNotIn("effect_type.DAMAGE_DEALING", row["selected_original_value"])
            self.assertTrue(row["selected_original_value"]["effect_type.ATTACK_MODIFIER_FOLLOWUP"])
        for row in self.matching("백호의희원"):
            self.assertNotIn("target.other_player_supported", row["selected_original_value"])
            self.assertEqual(row["selected_original_value"]["target.other_entity_supported"]["entity_class"], "UNSPECIFIED")
        for row in self.matching("백호참"):
            self.assertEqual(row["selected_original_value"]["cost.hp"]["basis"], "caster_HP_current_or_max_UNSTATED")

    def invoke_isolated(self, mutation):
        with tempfile.TemporaryDirectory(prefix="official-effect-negative-") as tmp:
            root = Path(tmp) / "docs/rebuild/p1_5"
            (root / "selected_content").mkdir(parents=True)
            data = CORE.read_bytes()
            report = json.loads((ROOT / "research_official_core.json").read_text())
            manifest = json.loads(Path(args.source_manifest).read_text())
            data, report, manifest = mutation(data, report, manifest, Path(tmp))
            (root / "selected_content/kr_official_core.jsonl").write_bytes(data)
            (root / "research_official_core.json").write_text(json.dumps(report))
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            command = [sys.executable, str(SCRIPT), "--repo", tmp, "--source-manifest", str(manifest_path)]
            result = subprocess.run(command, capture_output=True, text=True)
            return result.returncode, json.loads(result.stderr)

    def test_empty_parent_file_rejected(self):
        code, result = self.invoke_isolated(lambda data, report, sources, tmp: (b"", report, sources))
        self.assertEqual((code, result["result"]), (1, "FAIL"))

    def test_duplicate_parent_id_rejected_even_after_rehash(self):
        def mutation(data, report, sources, tmp):
            rows = list(map(json.loads, data.decode().splitlines()))
            skills = [r for r in rows if r["record_type"] == "skill"]
            skills[1]["content_id"] = skills[0]["content_id"]
            data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
            report["outputs"][0]["sha256"] = hashlib.sha256(data).hexdigest()
            return data, report, sources
        code, result = self.invoke_isolated(mutation)
        self.assertEqual((code, result["result"]), (1, "FAIL"))

    def test_missing_source_is_blocked(self):
        def mutation(data, report, sources, tmp):
            skill = next(r for r in map(json.loads, data.decode().splitlines()) if r["record_type"] == "skill")
            next(s for s in sources if s["source_id"] == skill["source_ids"][0])["local_private_path"] = str(tmp / "missing.html")
            return data, report, sources
        code, result = self.invoke_isolated(mutation)
        self.assertEqual((code, result["result"]), (2, "BLOCKED"))

    def test_modified_source_is_fail(self):
        def mutation(data, report, sources, tmp):
            skill = next(r for r in map(json.loads, data.decode().splitlines()) if r["record_type"] == "skill")
            source = next(s for s in sources if s["source_id"] == skill["source_ids"][0])
            changed = tmp / "changed.html"
            changed.write_bytes(Path(source["local_private_path"]).read_bytes() + b"X")
            source["local_private_path"] = str(changed)
            return data, report, sources
        code, result = self.invoke_isolated(mutation)
        self.assertEqual((code, result["result"]), (1, "FAIL"))


unittest.main(argv=[sys.argv[0]], verbosity=2)
