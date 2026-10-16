"""Read fixed P1.5 sources; propose small explicit semantic/link deltas only.

No original program, server, SQL or shared importer is run or changed.
Private values and referenced source bytes must stay in the private delta.
"""
import argparse
import collections
import hashlib
import html
import json
import pathlib
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def strip_html(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selected-dir", type=pathlib.Path, required=True)
    ap.add_argument("--catalog", type=pathlib.Path, required=True)
    ap.add_argument("--input-map", type=pathlib.Path, required=True)
    ap.add_argument("--public-output", type=pathlib.Path, required=True)
    ap.add_argument("--private-output", type=pathlib.Path, required=True)
    args = ap.parse_args()
    assert args.public_output.resolve() != args.private_output.resolve()
    args.public_output.mkdir(parents=True, exist_ok=True)
    args.private_output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.catalog.read_text())
    expected = {x["path"].split("/")[-1]: x for x in manifest["normalized_catalogs"]}
    file_map = json.loads(args.input_map.read_text())
    input_proofs = []
    source_proofs = {}
    private_records = []
    public_records = []
    tables = {}
    all_rows = {}
    row_locations = {}
    names = ["kr_official_items.jsonl", "kr_official_core.jsonl", "kr_official_services.jsonl", "kr_official_crafting_facts.jsonl"]
    for name in names:
        raw = (args.selected_dir / name).read_bytes()
        exp = expected[name]
        assert len(raw) == exp["bytes"] and sha(raw) == exp["sha256"], name
        rows = [json.loads(line) for line in raw.decode().splitlines()]
        assert len(rows) == exp["records"], name
        tables[name] = rows
        input_proofs.append({"path": "selected_content/" + name, "sha256": sha(raw), "bytes": len(raw), "rows": len(rows), "inspection": "Read unchanged for joins; not regenerated or reacquired"})
        for line, row in enumerate(rows, 1):
            assert row["content_id"] not in all_rows
            all_rows[row["content_id"]] = row
            row_locations[row["content_id"]] = {"path": "selected_content/" + name, "line": line, "file_sha256": sha(raw), "record_canonical_sha256": sha(canonical(row))}

    def source(row):
        sid = row["source_ids"][0]
        if sid not in source_proofs:
            data = pathlib.Path(file_map[sid]).read_bytes()
            assert sha(data) == row["input_sha256"], sid
            # Bounded raw official HTML only. No executable or SQL inputs.
            assert len(data) < 500_000
            data.decode("cp949", errors="strict")
            target = args.private_output / "source_bytes" / (sha(data) + ".html")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            source_proofs[sid] = {"source_id": sid, "sha256": sha(data), "bytes": len(data), "acquisition_kind": "EXISTING_P1_5_SOURCE_REUSED", "new_acquisition": False, "private_path": str(target.relative_to(args.private_output)), "url": row["source_locator"].get("url") or row["source_locator"].get("final_response_url") or row["source_locator"].get("archive_url"), "source_family": "NEXON_OFFICIAL_GUIDE_SHARED"}
        return source_proofs[sid]

    def ref(row):
        proof = source(row)
        return {"content_id": row["content_id"], "source_id": row["source_ids"][0], "input_sha256": proof["sha256"], "source_locator": row["source_locator"], "normalized_locator": row_locations[row["content_id"]]}

    def raw_slice(row):
        p = source(row)
        data = (args.private_output / p["private_path"]).read_bytes().decode("cp949").splitlines()
        loc = row["source_locator"]
        lo = loc.get("line_start", loc.get("html_line_start"))
        hi = loc.get("line_end", lo + 36)
        assert 0 < lo <= len(data) and lo <= hi
        return strip_html("\n".join(data[lo-1:hi]))

    def add(kind, owner, field, value, evidence_rows, gap_ids, binding_ids, requirements, confirmed, unknown, codex_tests, relation_state="PROPOSED"):
        evidence_rows = list({r["content_id"]: r for r in evidence_rows}.values())
        profile = owner["build_profile_id"]
        assert all(r["build_profile_id"] == profile for r in evidence_rows), "Cross-profile join forbidden"
        cid = "WSD-GE-" + sha(canonical([kind, owner["content_id"], field, value]))[:16]
        ev = [ref(row) for row in evidence_rows]
        record = {"candidate_id": cid, "kind": kind, "content_id": owner["content_id"], "entity_name_ko": owner["entity_name_ko"], "field_path": field, "original_value": value.get("documented_original"), "original_unit": value.get("unit"), "candidate_value": value, "build_profile_id": profile, "game_region": "KR", "client_build": "UNKNOWN; capture namespace is not a client build", "content_era": owner.get("content_era"), "source_evidence": ev, "expected_existing_record_sha256": row_locations[owner["content_id"]]["record_canonical_sha256"], "prior_candidate_difference": "New field-level semantic or stable-ID relation proposal; existing P1.5 row and active data remain unchanged", "gap_ids": gap_ids, "binding_ids": binding_ids, "requirement_ids": requirements, "confirmed_scope": confirmed, "unconfirmed_scope": unknown, "required_codex_tests": codex_tests, "relation_state": relation_state, "fact_status": "DOCUMENTED_SOURCE_SEMANTICS_CANDIDATE", "new_runtime_binding": "NOT_STARTED", "test_status": "NOT_RUN", "adoption_status": "UNACKNOWLEDGED", "profile_dispatch_required": True, "global_default_selected": False, "supersedes": []}
        record.update({"field": field, "existing_record_ids": [r["content_id"] for r in evidence_rows], "profile_id": profile, "source_sha256": sorted({e["input_sha256"] for e in ev}), "source_locator": [e["source_locator"] for e in ev], "old_value_or_hash": {"record_canonical_sha256": row_locations[owner["content_id"]]["record_canonical_sha256"], "active_value_changed": False}, "certainty": "QUALITATIVE_DOCUMENTED_FIELD" if kind == "EXISTING_SOURCE_NEW_SEMANTICS" else "EXPLICIT_CONFLICT_HOLD" if kind == "EXISTING_SOURCE_CONFLICT_IDENTIFIED" else "LOCATION_INFERENCE" if kind == "EXISTING_DATA_LOCATION_RELATION_HYPOTHESIS" else "ID_RELATION_CANDIDATE_REQUIRES_REVIEW", "remaining_unknowns": unknown, "codex_tests": codex_tests})
        private_records.append(record)
        # Public copy intentionally carries references, no bulk original values.
        public_records.append({k: record[k] for k in ["candidate_id", "kind", "content_id", "entity_name_ko", "field_path", "build_profile_id", "game_region", "client_build", "content_era", "expected_existing_record_sha256", "prior_candidate_difference", "gap_ids", "binding_ids", "requirement_ids", "confirmed_scope", "unconfirmed_scope", "required_codex_tests", "relation_state", "new_runtime_binding", "test_status", "adoption_status", "profile_dispatch_required", "global_default_selected", "supersedes", "field", "existing_record_ids", "profile_id", "source_sha256", "source_locator", "old_value_or_hash", "certainty", "remaining_unknowns", "codex_tests"]} | {"source_evidence": ev, "private_value": {"path": "gameplay_economy/field_candidates.private.jsonl", "candidate_id": cid, "record_canonical_sha256": sha(canonical(record))}})

    items = tables["kr_official_items.jsonl"]
    core = tables["kr_official_core.jsonl"]
    services = tables["kr_official_services.jsonl"]
    crafts = tables["kr_official_crafting_facts.jsonl"]
    item_index = collections.defaultdict(list)
    for item in items:
        item_index[item["build_profile_id"], re.sub(r"\s+", "", item["entity_name_ko"])].append(item)

    behaviors = {
        "곰": ("먼저 공격하지 않는한 공격해오지 않는다", "monster.ai.aggression", {"initiate_attack_without_player_attack": False, "retaliation_trigger": "player_attack", "attack_interval": None}, ["C/aggression"]),
        "불여우": ("체력이 낮아지면 도망", "monster.ai.flee_condition", {"trigger": "low_health_documented", "hp_threshold": None, "threshold_unit": None, "flee_speed": None, "return_rule": None}, ["C/movement_chase_return"]),
        "뇌랑": ("번개를 쏘아대며 공격함", "monster.ai.attack_behavior", {"attack_description": "lightning_attack_documented", "spell_native_id": None, "target_geometry": None, "attack_interval": None}, ["C/attack_interval"]),
        "천오": ("중독마법 사용", "monster.ai.named_spell", {"documented_spell_name": "멍석말이", "effect_description": "poison", "spell_native_id": None, "duration": None, "damage": None, "attack_interval": None}, ["C/attack_interval"]),
        "신몽": ("공격마법 사용", "monster.ai.named_spell", {"documented_spell_name": "섬광탄", "spell_native_id": None, "target_geometry": None, "damage": None, "attack_interval": None}, ["C/attack_interval"]),
        "마려": ("마법을 마구 쏘아대는", "monster.ai.attack_behavior", {"attack_description": "magic_attacks_documented", "spell_native_id": None, "attack_interval": None}, ["C/attack_interval"]),
        "소천대사": ("마법을 마구 쏘아대는", "monster.ai.attack_behavior", {"attack_description": "magic_attacks_documented", "spell_native_id": None, "attack_interval": None}, ["C/attack_interval"]),
    }
    for boss in ["운랑", "수렴귀", "풍석", "폭염귀", "암흑왕"]:
        behaviors[boss] = ("전체공격을 함", "monster.ai.area_attack_description", {"whole_area_attack_documented": True, "target_geometry": None, "scope_players_or_tiles": None, "attack_interval": None, "spell_native_id": None}, ["C/attack_interval"])
    for monster in core:
        if monster["record_type"] != "monster" or monster["entity_name_ko"] not in behaviors:
            continue
        literal, field, val, gaps = behaviors[monster["entity_name_ko"]]
        text = raw_slice(monster)
        assert literal in text, monster["content_id"]
        add("EXISTING_SOURCE_NEW_SEMANTICS", monster, field, {"documented_original": literal, "unit": "qualitative_published_description", **val}, [monster], gaps, ["BND-016"], ["RQ-037", "RQ-039", "RQ-040", "RQ-041"], "Only the explicit qualitative behavior in this official row, now linked to the existing monster ID", "No numeric aggression radius, HP threshold, chase boundary, spell ID, hit geometry, timing, damage or target-era client equivalence", ["Observe the matching monster/profile in a separately approved reference runtime; test attack-before-provocation, low-HP escape or named/area cast as applicable", "Bind only at a Codex test boundary and rerun affected AI cases; do not rerun unrelated G0/graphics cases"])

    # Three concrete vendor rows, both epochs. Generic armour categories are not expanded.
    for service in services:
        if service["entity_name_ko"] not in {"왈숙네 왈숙언니 왈숙이모", "털보", "백씨형제들"}:
            continue
        original = service["original_value"]
        for direction, key in [("npc_sells", "sale_tokens"), ("npc_buys_only", "buy_only_tokens")]:
            for token in original[key]:
                if "*" in token:
                    # This is a pre-existing combined footnote, never an item name.
                    continue
                matches = item_index[service["build_profile_id"], re.sub(r"\s+", "", token)]
                exact = [m for m in matches if m["entity_name_ko"] == token]
                match_method = "EXACT_LITERAL" if exact else "WHITESPACE_ONLY_ALIAS" if matches else "UNRESOLVED_NAME"
                if exact:
                    matches = exact
                state = "UNIQUE_ITEM_ID_CANDIDATE" if len(matches) == 1 else "MULTIPLE_ITEM_RECORDS_REVIEW_REQUIRED" if matches else "UNRESOLVED_NO_ITEM_ROW"
                restriction = original.get("trade_restriction_documented") if token in ["철단도", "철도"] else None
                if restriction:
                    state = "MERCHANT_INSTANCE_RESTRICTION_UNRESOLVED"
                add("EXISTING_DATA_NEW_ID_RELATION", service, "shop.stock_relation." + direction + "." + token,
                    {"documented_original": token, "unit": "item_identity", "trade_direction": direction, "match_method": match_method, "item_content_ids": [m["content_id"] for m in matches], "source_listed_price_candidates": [{"item_content_id": m["content_id"], "value": m["original_value"].get("listed_price"), "unit": m["original_value"].get("listed_price_unit"), "semantics": "UNSPECIFIED_PRICE_COLUMN"} for m in matches], "actual_npc_sell_price": None, "actual_npc_buy_price": None, "stock_limit": None, "merchant_instance_restriction": restriction}, [service, *matches], ["E/shop_stock_buy_sell_limit"], ["BND-020"], ["RQ-068", "RQ-069", "RQ-070", "RQ-071"], "Existing NPC stock token and trade direction; same-profile exact/whitespace-only item-ID candidates, not one global stock list", "Listed item price is not established as either NPC buy or sell price. Preserve multiple records, unknown names and restricted merchant instances. NPC name groups may be aliases or separate NPCs", ["Codex review item identity and alias before importing; do not choose first duplicate", "In runtime validate different vendor stock, explicit buy-only items, prices and restricted merchant instances independently"], state)

    # Make a few low-level loops usable: one healing name still has four jobs/IDs.
    for skill in core:
        if skill["record_type"] != "skill" or skill["entity_name_ko"] != "누리의기원":
            continue
        job = skill["original_value"]["job"]
        if job not in {"전사", "도적", "주술사", "도사"}:
            continue
        teachers = [s for s in services if s["build_profile_id"] == skill["build_profile_id"] and (job + "길드") in (s["original_value"].get("location_label_documented") or "") and "teach_skill" in s["original_value"]["services"]]
        material_relations = []
        matched_items = []
        for mat in skill["original_value"]["ingredients"]:
            matches = item_index[skill["build_profile_id"], re.sub(r"\s+", "", mat["item_name_literal"])]
            matched_items.extend(matches)
            material_relations.append({"item_name_literal": mat["item_name_literal"], "quantity": mat["quantity"], "candidate_item_ids": [m["content_id"] for m in matches], "status": "UNIQUE_ITEM_ID_CANDIDATE" if len(matches) == 1 else "UNRESOLVED_OR_MULTIPLE"})
        assert len(teachers) == 2
        add("EXISTING_DATA_NEW_ID_RELATION", skill, "skill.learning.teacher_and_material_relations", {"documented_original": skill["original_value"]["job"], "unit": "job_scoped_relation", "job": job, "learn_level": skill["original_value"]["learn_level"], "learn_money": skill["original_value"]["learn_money"], "teacher_candidates_by_country": [{"teacher_id": t["content_id"], "location": t["original_value"]["location_label_documented"]} for t in teachers], "ingredients": material_relations}, [skill, *teachers, *matched_items], ["E/four_job_learning", "E/learn_materials", "E/job_change_level_npc"], ["BND-018", "BND-020"], ["RQ-044", "RQ-045", "RQ-046", "RQ-047"], "Same named skill remains one separate published row per job; connect to both same-job city guild teachers and same-profile ingredient IDs", "Specific teacher dialogue, material consumption atomicity, early learning refusal, native skill IDs and missing meat item row remain untested", ["Test each of four job-specific learn levels/costs/material consumption, wrong job and insufficient-resource refusal; no cross-job fallback", "Confirm country/guild teacher linkage and name identity before adoption"])

    # A duplicate-price counterexample within one epoch and one source HTML.
    price_conflicts = []
    for (profile, name), group in item_index.items():
        if name != "진마반지" or profile != "KR_GUIDE_2001_SNAPSHOT":
            continue
        prices = {g["original_value"].get("listed_price") for g in group}
        if len(prices) > 1:
            for row in group:
                text = raw_slice(row)
                assert str(row["original_value"]["listed_price"]) in text
            owner = group[0]
            add("EXISTING_SOURCE_CONFLICT_IDENTIFIED", owner, "item.listed_price.same_profile_conflict", {"documented_original": [{"item_id": r["content_id"], "value": r["original_value"]["listed_price"], "source_line": r["source_locator"]["html_line_start"]} for r in group], "unit": "전", "selected_price": None, "same_name_different_prices": True, "profile_dispatch_alone_resolves": False}, group, ["E/shop_stock_buy_sell_limit", "E/equipment_condition"], ["BND-020", "BND-021"], ["RQ-068", "RQ-074"], "Two contemporaneous rows in the same2001HTML contain different price literals; both existing IDs remain available", "Which price is correct, typo versus different trade directions or historical patch, and actual NPC prices are unresolved. Do not average, append zeros or select first row", ["Resolve against another contemporaneous source or record matching NPC buy/sell observations; hold price adoption until then"], "CONFLICT_HOLD")

    for craft in crafts:
        name = craft["entity_name_ko"]
        if name not in {"방천가위", "진호박단추"}:
            continue
        npc_name = "털보" if name == "방천가위" else "떡쇠"
        targets = [s for s in services if s["build_profile_id"] == craft["build_profile_id"] and s["entity_name_ko"] == npc_name]
        assert len(targets) == 1
        add("EXISTING_DATA_LOCATION_RELATION_HYPOTHESIS", craft, "craft.npc_location_to_named_service_candidate", {"documented_original": craft["original_value"].get("npc_location_description"), "unit": "city_facility_relation", "candidate_service_id": targets[0]["content_id"], "candidate_npc_name": npc_name, "basis": "same-epoch same-country blacksmith facility", "exact_npc_script_or_dialogue_verified": False, "success_rate": None, "failure_loss": None, "money_cost": None}, [craft, *targets], ["D/npc"], ["BND-035", "BND-020"], [], "Published recipe facility and named merchant at that facility give a bounded review candidate", "Location does not prove the NPC script performs the recipe. Keep existing npc_name null until reviewed; do not enable a complete recipe from this candidate", ["Codex inspect/observe the matching country NPC service and recipe branch; retain material and availability conditions, unknown success/failure/cost"], "LOCATION_INFERENCE_REVIEW_REQUIRED")

    # Partial drop identity links; source probabilities are deliberately not copied/invented.
    starter_names = {"다람쥐", "토끼", "박쥐", "서생원", "구렁이", "호랑이", "불여우"}
    for monster in core:
        if monster["record_type"] != "monster" or monster["entity_name_ko"] not in starter_names:
            continue
        for token in monster["original_value"]["possible_item_names"]:
            matches = item_index[monster["build_profile_id"], re.sub(r"\s+", "", token)]
            add("EXISTING_DATA_NEW_ID_RELATION", monster, "monster.drop_item_relation." + token, {"documented_original": token, "unit": "possible_item_identity", "candidate_item_ids": [m["content_id"] for m in matches], "quantity": None, "probability": None, "probability_model": "UNCHANGED_UNKNOWN", "native_item_id": None}, [monster, *matches], ["C/item_relation"], ["BND-016", "BND-017"], ["RQ-037", "RQ-042"], "Connect documented possible reward names to same-profile known stable item rows where available", "This supplies identity candidates only. It neither overrides separately recorded explicit probabilities nor proves quantity, independence, mutual exclusion or no-drop probability", ["Codex review item identity, retain existing documented probabilities separately, and observe quantity/roll model before implementing exact rates"], "UNIQUE_ITEM_ID_CANDIDATE" if len(matches) == 1 else "UNRESOLVED_NO_ITEM_ROW" if not matches else "MULTIPLE_ITEM_RECORDS_REVIEW_REQUIRED")

    assert len(private_records) > 0
    ids = [r["candidate_id"] for r in private_records]
    assert len(ids) == len(set(ids))
    for record in private_records:
        assert all(e["content_id"] in all_rows for e in record["source_evidence"])
        assert record["test_status"] == "NOT_RUN"
    def write_jsonl(path, rows):
        path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))
    write_jsonl(args.private_output / "field_candidates.private.jsonl", private_records)
    write_jsonl(args.public_output / "field_candidates.jsonl", public_records)
    write_jsonl(args.public_output / "sources_delta.jsonl", list(source_proofs.values()))
    (args.public_output / "INPUT_PROOFS.json").write_text(json.dumps(input_proofs, ensure_ascii=False, indent=2) + "\n")
    summary = {"task_id": "BARAM_REBUILD_WORK_SOURCE_DELTA_001", "scope": "Gameplay/economy source interpretation only; not G0/P2/game execution", "newly_acquired_source_files": 0, "source_bytes_reused_and_verified": len(source_proofs), "normalized_inputs_read_unchanged": len(input_proofs), "candidate_records": len(private_records), "candidate_kinds": dict(collections.Counter(r["kind"] for r in private_records)), "relation_states": dict(collections.Counter(r["relation_state"] for r in private_records)), "behavior_monster_records": sum(r["kind"] == "EXISTING_SOURCE_NEW_SEMANTICS" for r in private_records), "behavior_monster_name_families": len({r["entity_name_ko"] for r in private_records if r["kind"] == "EXISTING_SOURCE_NEW_SEMANTICS"}), "format_reference_and_source_hash_validation": "PASS", "historical_interpretation": "PARTIAL_REQUIRES_CODEX_REVIEW", "runtime_tests": "NOT_RUN", "na_reference_fail154": "PRESERVED_UNCHANGED", "adoption": "UNACKNOWLEDGED", "output_hashes": {"public_candidates_sha256": sha((args.public_output / "field_candidates.jsonl").read_bytes()), "private_candidates_sha256": sha((args.private_output / "field_candidates.private.jsonl").read_bytes())}}
    (args.public_output / "VALIDATION.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
