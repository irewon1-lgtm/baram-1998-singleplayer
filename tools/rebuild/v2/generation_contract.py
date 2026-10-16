#!/usr/bin/env python3
"""Freeze G1 from actual normalized bytes; audit runtime closure without claiming play.

This tool reads the complete catalog once, keeps later Korean values and unique
older content, and accounts for every semantic row. Asset rows and source fields
are evidence, not extra playable monsters/maps. No source input is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

PLAN = "BARAM_REBUILD_V2_RESOURCE_FIRST_20261016"
PROFILE = "KR_GUIDE_2001_SNAPSHOT"
OLDER = "KR_GUIDE_2000_SNAPSHOT"
FOUR_JOBS = ("전사", "도적", "주술사", "도사")
ADVANCEMENTS = {
    "검객": ("전사", 1), "검제": ("전사", 2), "검황": ("전사", 3),
    "자객": ("도적", 1), "진검": ("도적", 2), "귀검": ("도적", 3),
    "술사": ("주술사", 1), "현사": ("주술사", 2),
    "현인": ("주술사", 3), "현자": ("주술사", 4),
    "도인": ("도사", 1), "명인": ("도사", 2), "진인": ("도사", 3),
}
ENTITY_TABLES = {
    "kr_official_core.jsonl": {"skill": "skills", "monster": "monsters"},
    "kr_official_items.jsonl": {"item": "items"},
    "kr_official_services.jsonl": {"npc_service": "npcs"},
    "kr_official_crafting_facts.jsonl": {"crafting_fact": "recipes"},
}
RULE_TABLES = ("kr_official_facility_rules.jsonl", "kr_official_flow.jsonl")
SKILL_KINDS = {"damage", "heal", "buff", "debuff", "status", "return", "shrine", "identify",
               "restore_mp", "summon", "cleanse", "revive", "loot", "blink"}
STATUS_KINDS = {"stealth", "paralysis", "poison", "slow", "silence", "protection", "haste", "blindness"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    if isinstance(value, Path):
        value = value.read_bytes()
    elif not isinstance(value, bytes):
        value = canonical(value).encode()
    return hashlib.sha256(value).hexdigest()


def clean_name(value):
    return re.sub(r"\s+", "", value or "")


def value_of(row):
    return row.get("selected_original_value") or row.get("original_value") or {}


def semantic_key(row):
    value = value_of(row)
    def hashable(field):
        selected = value.get(field)
        return canonical(selected) if isinstance(selected, (dict, list)) else selected
    # A shared spell name across jobs or guardian elements is not one spell.
    return (row["record_type"], clean_name(row.get("entity_name_ko")),
            hashable("job"), hashable("guardian"))


def covered_range_members(row, preferred_rows):
    """A source range label is not an extra item beside its selected variants."""
    if row.get("record_type") != "item":
        return []
    match = re.fullmatch(r"(.+?)(\d+)(?:번)?[~～](\d+)(?:번)?", clean_name(row.get("entity_name_ko")))
    if not match:
        return []
    prefix, first, last = match.group(1), int(match.group(2)), int(match.group(3))
    numbered = defaultdict(list)
    for candidate in preferred_rows:
        found = re.fullmatch(re.escape(prefix) + r"(\d+)(?:번)?", clean_name(candidate.get("entity_name_ko")))
        if candidate.get("record_type") == "item" and found:
            numbered[int(found.group(1))].append(candidate["content_id"])
    if first > last or not all(numbered.get(n) for n in range(first, last + 1)):
        return []
    return sorted(iid for n in range(first, last + 1) for iid in numbered[n])


def select_semantic_rows(rows):
    """Return selected rows and an explicit disposition for every source row.

    Exact duplicate IDs may be aliases later, but no nonidentical same-name rows
    are lost. Group headers, closed facilities and historical online policies
    are references; their constituent entities remain selected independently.
    """
    preferred_rows = [r for r in rows if r.get("build_profile_id") == PROFILE]
    preferred_keys = {semantic_key(r) for r in preferred_rows}
    selected, decisions = [], []
    for row in rows:
        profile = row.get("build_profile_id")
        value = value_of(row)
        reason = "SELECTED_KR2001"
        chosen = True
        if row.get("game_region") != "KR":
            chosen, reason = False, "WRONG_REGION_REFERENCE_ONLY"
        elif profile not in (PROFILE, OLDER):
            chosen, reason = False, "UNPROFILED_REFERENCE_ONLY"
        elif profile == OLDER and semantic_key(row) in preferred_keys:
            chosen, reason = False, "OLDER_VARIANT_PRESERVED_KR2001_SELECTED"
        elif profile == OLDER:
            reason = "SELECTED_UNIQUE_OLDER_KOREAN_CONTENT"
        members = covered_range_members(row, preferred_rows) if profile == OLDER else []
        if chosen and members:
            chosen, reason = False, "GROUP_RANGE_COVERED_BY_KR2001_VARIANTS"
        if chosen and row.get("selection_state") == "HOLD_GROUPED_VARIANT_ROWS":
            chosen, reason = False, "GROUP_HEADER_NOT_ADDITIONAL_PLAYABLE_ENTITY"
        if chosen and row["record_type"] == "account":
            chosen, reason = False, "ONLINE_SERVICE_POLICY_REFERENCE_ONLY_OFFLINE_SAVE_PRESERVED"
        if chosen and value.get("open_at_document_capture") is False:
            chosen, reason = False, "SOURCE_FACILITY_CLOSED_REFERENCE_ONLY"
        if chosen and not row.get("selected_for_build"):
            # Historical uncertainty no longer vetoes a reconstructable recipe.
            if row["record_type"] == "crafting_fact":
                reason = "SELECTED_RECIPE_RECONSTRUCTION_NOT_ORIGINAL_VERIFIED"
            else:
                chosen, reason = False, "NONEXECUTABLE_SOURCE_REFERENCE_ONLY"
        decisions.append({"content_id": row["content_id"], "profile": profile,
                          "decision": "SELECTED" if chosen else "REFERENCE",
                          "reason": reason, "semantic_key": list(semantic_key(row)),
                          "source_record_sha256": digest(row), **({"constituent_ids": members} if members else {})})
        if chosen:
            selected.append(row)
    return selected, decisions


def read_inventory(normalized, catalog_path):
    catalog = json.loads(catalog_path.read_text())
    tables, inventory = {}, []
    for entry in catalog["normalized_catalogs"]:
        name = Path(entry["path"]).name
        path = normalized / name
        if not path.is_file():
            raise ValueError("Required actual normalized bytes missing: " + name)
        sha = digest(path)
        if sha != entry["sha256"]:
            raise ValueError("Normalized input hash mismatch: " + name)
        value = ([json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                 if path.suffix == ".jsonl" else json.loads(path.read_text()))
        count = len(value.get("contracts", [])) if name == "save_contracts.json" else len(value)
        if count != entry["records"]:
            raise ValueError("Normalized input record count mismatch: " + name)
        if isinstance(value, list):
            tables[name] = value
        inventory.append({"path": entry["path"], "sha256": sha, "bytes": path.stat().st_size,
                          "records": count, "read_status": "BYTES_AND_RECORDS_VERIFIED",
                          "purpose": "SEMANTIC_CANDIDATES" if name in ENTITY_TABLES or name in RULE_TABLES
                          else "SUPPORT_REFERENCE_NOT_PLAYABLE_ENTITY_DENOMINATOR"})
    return tables, inventory


def source_entities(tables, runtime=None):
    """Public helper used by the content compiler; preserves every selected ID."""
    entities, decisions = {}, []
    for table, kinds in ENTITY_TABLES.items():
        selected, table_decisions = select_semantic_rows(tables[table])
        decisions.extend({"table": table, **d} for d in table_decisions)
        for row in selected:
            kind = kinds[row["record_type"]]
            if row["content_id"] in entities:
                raise ValueError("Source ID reused across entity rows: " + row["content_id"])
            entities[row["content_id"]] = (kind, row, table)
    # Exact-semantic duplicate rows are explicitly reported. All source IDs are
    # still required; a runtime may implement them separately or bind aliases.
    groups = defaultdict(list)
    for iid, (kind, row, table) in entities.items():
        groups[(kind, semantic_key(row), digest(value_of(row)))].append(iid)
    aliases = []
    existing = {i for kind, entries in (runtime or {}).items()
                if isinstance(entries, dict) for i in entries}
    for ids in groups.values():
        if len(ids) > 1:
            ordered = sorted(ids, key=lambda iid: (iid not in existing, iid))
            aliases.extend({"content_id": iid, "canonical_id": ordered[0],
                            "reason": "EXACT_SAME_NAME_JOB_GUARDIAN_AND_SELECTED_VALUES",
                            "runtime_alias_optional": True} for iid in ordered[1:])
    return entities, decisions, sorted(aliases, key=lambda r: r["content_id"])


def make_contract(normalized, catalog_path, baseline):
    tables, inventory = read_inventory(normalized, catalog_path)
    entities, decisions, aliases = source_entities(tables, baseline)
    required = {kind: {} for kind in ("maps", "npcs", "items", "monsters", "skills", "recipes")}
    runtime_ids = set()
    for kind in required:
        for iid, row in baseline.get(kind, {}).items():
            runtime_ids.add(iid)
            required[kind][iid] = {"content_id": iid, "name": row.get("name"),
                                   "origin": "PRESERVED_BASELINE_RUNTIME_ID", "source_tier": "LEGACY_RECONSTRUCTED",
                                   "required": True, "runtime_ref": "/" + kind + "/" + iid,
                                   "functional_test": "NOT_RUN_IN_CONTRACT_TOOL"}
    for iid, (kind, row, table) in sorted(entities.items()):
        value = value_of(row)
        required[kind][iid] = {"content_id": iid, "name": row.get("entity_name_ko"),
                               "origin": "SOURCE_ENTITY", "required": True,
                               "source_tier": "LEGACY_VERIFIED" if row.get("selected_for_build") else "LEGACY_RECONSTRUCTED",
                               "profile": row.get("build_profile_id"), "source_table": table,
                               "source_record_sha256": digest(row), "selected_value_sha256": digest(value),
                               "source_ref": row.get("source_ids", []), "source_locator": row.get("source_locator"),
                               "runtime_ref": "/" + kind + "/" + iid,
                               "functional_test": "NOT_RUN_IN_CONTRACT_TOOL"}
        if kind == "skills":
            job = value.get("job")
            parent, rank = ADVANCEMENTS.get(job, (job, 0))
            if parent not in FOUR_JOBS and parent != "COMMON_FOUR_STARTER_JOBS":
                raise ValueError("Unsupported selected job: " + str(job))
            required[kind][iid].update(base_job=parent, required_advancement=rank,
                                       learn_level=value.get("learn_level"), guardian=value.get("guardian"))
        if kind == "monsters":
            required[kind][iid]["source_region"] = value.get("region")
    rules = []
    for table in RULE_TABLES:
        selected, table_decisions = select_semantic_rows(tables[table])
        decisions.extend({"table": table, **d} for d in table_decisions)
        for row in selected:
            offline_reference = bool(value_of(row).get("single_player_applicability"))
            rules.append({"content_id": row["content_id"], "name": row.get("entity_name_ko"),
                          "record_type": row["record_type"], "source_table": table,
                          "selected_value_sha256": digest(value_of(row)), "required_binding": not offline_reference,
                          "scope_decision": "OFFLINE_REFERENCE_EXCLUDED" if offline_reference else "BOUND_OR_RECONSTRUCTED_REQUIRED",
                          "rationale": "Original PVP/spouse other-player service excluded from offline singleplayer; NPC theme may be adapted separately"
                          if offline_reference else "Explicit source rule needs an executable binding or a documented reconstruction"})
    regions = sorted({r["source_region"] for r in required["monsters"].values() if r.get("source_region")})
    by_kind = {kind: sorted(rows) for kind, rows in required.items()}
    deferred = baseline.get("deferred", {})
    obligations = {"skills": sorted(deferred.get("higher_skill_ids", [])),
                   "npcs": sorted(deferred.get("unplaced_npc_contract_ids", []))}
    for kind, ids in obligations.items():
        missing = set(ids) - set(by_kind[kind])
        if missing:
            raise ValueError("Prior deferred obligations silently lost: " + str(sorted(missing)))
    contract = {"schema": "baram.generation.contract/1", "plan_id": PLAN, "generation": "G1",
                "scope_status": "FROZEN_SOURCE_ID_SET_RUNTIME_BINDING_REQUIRED",
                "source_policy": "KR2001 values; unique KR2000 entities retained; source uncertainty reconstructed; all variants accounted",
                "inventory": inventory, "inventory_total_records": sum(r["records"] for r in inventory),
                "baseline_content_sha256": digest(baseline), "required_content": required,
                "required_ids": by_kind, "required_counts": {k: len(v) for k, v in required.items()},
                "source_entity_counts": dict(Counter(kind for kind, row, table in entities.values())),
                "source_dispositions": sorted(decisions, key=lambda r: (r["table"], r["content_id"])),
                "exact_semantic_aliases": aliases, "rule_bindings": rules,
                "grouped_source_bindings": [d for d in decisions if d["reason"] == "GROUP_RANGE_COVERED_BY_KR2001_VARIANTS"],
                "source_regions": regions, "preserved_runtime_ids": sorted(runtime_ids),
                "retained_handoff_obligations": obligations,
                "four_jobs": list(FOUR_JOBS), "level_range": [1, 99],
                "advancement_branches": {k: {"base_job": v[0], "rank": v[1]} for k, v in ADVANCEMENTS.items()},
                "required_features": ["offline_creation", "four_job_change", "growth_1_99", "selected_advancement",
                                      "distinct_job_skill_actions", "reachable_city_hunting_exits", "monster_loot",
                                      "role_specific_shops", "equipment_conditions_durability_repair", "normal_item_acquisition_use",
                                      "npc_dialogue_services", "quests_crafting", "death_revival_return", "stable_id_save_migration",
                                      "windows_android_update", "same_account_sequential_continuation"],
                "completion_gates": {"registered_not_functional": True, "source_fallback_not_pass": True,
                                     "required_ids_may_not_silently_disappear": True,
                                     "runtime_missing_id_is_code_fail": True, "platform_tests_separate": True},
                "functional_tests_performed": 0}
    alias_counts = Counter(entities[a["content_id"]][0] for a in aliases)
    contract["exact_semantic_source_counts"] = {
        kind: count - alias_counts[kind] for kind, count in contract["source_entity_counts"].items()}
    contract["count_unit_note"] = "Required stable/source IDs include aliases. Exact-semantic source counts remove 13 duplicate monster rows; no global completion percentage."
    contract["public_source_crosscheck"] = {
        "observed_date": "2026-10-17", "source_family": "NEXON_OFFICIAL_CURRENT_GUIDE",
        "page_url": "https://baram.nexon.com/Guide/Contents/01-02",
        "image_url": "https://ssl.nexon.com/S2/Game/baram/2016/renewal/guide02_v2026.png",
        "image_sha256": "d9150cd42a21e4d0814297f89b25c00d7ac25acc20c0ab96859c404b0c8136f4",
        "image_bytes": 4906011, "image_dimensions": [1130, 6956], "source_updated_date": "2026-04-07",
        "access_evidence": "HTML read; web image fetch timeout; alternate urllib image bytes acquired and visually read",
        "observed_scope": "Whole guide image; detailed role header and skill-information UI crops",
        "qualitative_findings": {"전사": "frontline melee", "도적": "concealment and burst",
                                 "주술사": "ranged attack spells", "도사": "healing support"},
        "adoption": "REFERENCE_CROSSCHECK_ONLY_NO_NEW_G1_IDS_OR_MODERN_NUMERIC_VALUES",
        "reason": "Existing Korean archived inputs cover G1; modern 11 jobs and 9 advancement stages exceed four-job1-99 scope",
        "full_modern_skill_or_map_dataset_acquired": False}
    contract["scope_sha256"] = digest({"required_ids": by_kind, "source_dispositions": contract["source_dispositions"],
                                        "features": contract["required_features"], "level_range": [1, 99]})
    contract["source_scope_sha256"] = contract["scope_sha256"]
    contract["rule_scope_sha256"] = digest(rules)
    return contract


def freeze_derived_ids(contract, runtime):
    """Freeze explicit reconstructed maps/dependency IDs after deterministic compile.

    Required source IDs are never removed, even if the compiler omitted them.
    This is the final B2 map/dependency extension, not an implementation PASS.
    """
    result = deepcopy(contract)
    added = list(result.get("derived_dependencies", []))
    for kind in ("quests", "advancements", "training_rules"):
        if runtime.get(kind):
            result["required_ids"].setdefault(kind, [])
            result["required_content"].setdefault(kind, {})
            result["required_counts"].setdefault(kind, 0)
    for kind in result["required_ids"]:
        for iid, entry in runtime.get(kind, {}).items():
            if iid not in result["required_content"][kind]:
                result["required_content"][kind][iid] = {
                    "content_id": iid, "name": entry.get("name"), "required": True,
                    "origin": "EXPLICIT_RECONSTRUCTED_G1_DEPENDENCY", "source_tier": "LEGACY_RECONSTRUCTED",
                    "runtime_ref": "/" + kind + "/" + iid, "functional_test": "NOT_RUN_IN_CONTRACT_TOOL"}
                added.append({"kind": kind, "content_id": iid})
        result["required_ids"][kind] = sorted(result["required_content"][kind])
        result["required_counts"][kind] = len(result["required_ids"][kind])
    result["derived_dependencies"] = sorted(added, key=lambda r: (r["kind"], r["content_id"]))
    result["derived_runtime_content_sha256"] = digest(runtime)
    result["scope_status"] = "FROZEN_FULL_G1_ID_SET_RUNTIME_TESTS_REQUIRED"
    result["scope_sha256"] = digest({"source_scope_sha256": result["source_scope_sha256"],
                                      "rule_scope_sha256": result.get("rule_scope_sha256"),
                                      "required_ids": result["required_ids"], "derived_dependencies": result["derived_dependencies"]})
    return result


def audit_runtime(contract, runtime):
    """Check references, map reachability and normal acquisition; never play PASS."""
    errors, stats = [], Counter()
    def fail(code, iid, detail=None):
        errors.append({"code": code, "content_id": iid, "detail": detail})
    aliases = runtime.get("id_aliases", {})
    def resolve(kind, iid):
        seen = set()
        while iid in aliases:
            if iid in seen:
                return None
            seen.add(iid)
            target = aliases[iid]
            iid = target.get("canonical_id") if isinstance(target, dict) else target
        return runtime.get(kind, {}).get(iid)
    for kind, ids in contract["required_ids"].items():
        for iid in ids:
            if resolve(kind, iid) is None:
                fail("REQUIRED_ID_UNBOUND", iid, kind)
            else:
                stats[kind + "_bound"] += 1
    # These are semantic source fields, not extra playable entity counts.
    runtime_rules = runtime.get("rule_bindings", {})
    for rule in contract.get("rule_bindings", []):
        binding = runtime_rules.get(rule["content_id"], {})
        if not binding:
            fail("RULE_DISPOSITION_MISSING", rule["content_id"])
        elif rule["required_binding"]:
            if binding.get("status") not in ("IMPLEMENTED", "ADAPTED") or not binding.get("runtime_refs") or not binding.get("rationale"):
                fail("RULE_REQUIRED_BINDING_INVALID", rule["content_id"])
            else:
                stats["source_rules_bound"] += 1
                for reference in binding["runtime_refs"]:
                    current = runtime
                    parts = reference.strip("/").split("/") if reference.startswith("/") else reference.split(".")
                    for part in parts:
                        if not isinstance(current, dict) or part not in current:
                            fail("RULE_RUNTIME_REF_MISSING", rule["content_id"], reference)
                            break
                        current = current[part]
        elif binding.get("status") != "NON_G1_OFFLINE_REFERENCE" or not binding.get("rationale"):
            fail("RULE_OFFLINE_EXCLUSION_UNDOCUMENTED", rule["content_id"])
        else:
            stats["source_rules_explicit_offline_exclusions"] += 1
    maps = runtime.get("maps", {})
    start_map = runtime.get("start", {}).get("map_id")
    start = runtime.get("start", {})
    cell_reach = defaultdict(set)
    reached = set()
    q = deque([(start_map, start.get("x", -1), start.get("y", -1))])
    while q:
        mid, sx, sy = q.popleft()
        if mid not in maps:
            continue
        m = maps[mid]
        blocked = {tuple(p) for p in m.get("blocked", [])}
        if not (0 <= sx < m["width"] and 0 <= sy < m["height"]) or (sx, sy) in blocked:
            continue
        exits_at = defaultdict(list)
        for exit_ in m.get("exits", []):
            exits_at[(exit_.get("x"), exit_.get("y"))].append(exit_)
        walk = deque([(sx, sy)])
        while walk:
            x, y = walk.popleft()
            if (x, y) in cell_reach[mid]:
                continue
            cell_reach[mid].add((x, y))
            reached.add(mid)
            for exit_ in exits_at[(x, y)]:
                q.append((exit_.get("to_map"), exit_.get("to_x", -1), exit_.get("to_y", -1)))
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < m["width"] and 0 <= ny < m["height"] and (nx, ny) not in blocked and (nx, ny) not in cell_reach[mid]:
                    walk.append((nx, ny))
    for mid, m in maps.items():
        if mid not in reached:
            fail("MAP_NOT_REACHABLE_FROM_START", mid)
        w, h = m.get("width", 0), m.get("height", 0)
        blocked = {tuple(p) for p in m.get("blocked", [])}
        def walkable(x, y):
            return 0 <= x < w and 0 <= y < h and (x, y) not in blocked
        for e in m.get("exits", []):
            if e.get("to_map") not in maps:
                fail("EXIT_MAP_MISSING", mid, e.get("to_map"))
            if not walkable(e.get("x", -1), e.get("y", -1)):
                fail("EXIT_SOURCE_CELL_BLOCKED", mid, e.get("id"))
            elif (e["x"], e["y"]) not in cell_reach[mid]:
                fail("EXIT_SOURCE_CELL_UNREACHABLE", mid, e.get("id"))
            target = maps.get(e.get("to_map"))
            if target and not (0 <= e.get("to_x", -1) < target["width"] and 0 <= e.get("to_y", -1) < target["height"]
                               and [e["to_x"], e["to_y"]] not in target.get("blocked", [])):
                fail("EXIT_DESTINATION_CELL_BLOCKED", mid, e.get("id"))
        for spawn in m.get("spawns", []):
            if resolve("monsters", spawn.get("monster_id")) is None:
                fail("SPAWN_MONSTER_MISSING", mid, spawn.get("monster_id"))
            if not walkable(spawn.get("x", -1), spawn.get("y", -1)):
                fail("SPAWN_CELL_BLOCKED", mid, spawn.get("id"))
            elif (spawn["x"], spawn["y"]) not in cell_reach[mid]:
                fail("SPAWN_CELL_UNREACHABLE", mid, spawn.get("id"))
    acquired, spawned = set(), set()
    for s in runtime.get("start", {}).get("starter_items", []):
        acquired.add(s["item_id"])
    for mid in reached:
        spawned.update(s["monster_id"] for s in maps[mid].get("spawns", []))
    for iid, monster in runtime.get("monsters", {}).items():
        if iid not in spawned and not any(resolve("monsters", sid) is monster for sid in spawned):
            fail("MONSTER_HAS_NO_REACHABLE_SPAWN", iid)
        for drop in monster.get("drops", []):
            if resolve("items", drop.get("item_id")) is None:
                fail("DROP_ITEM_MISSING", iid, drop.get("item_id"))
            elif drop.get("chance", 0) > 0:
                acquired.add(drop["item_id"])
    for nid, npc in runtime.get("npcs", {}).items():
        mid = npc.get("map_id")
        if mid not in reached:
            fail("NPC_MAP_UNREACHABLE", nid, mid)
        elif not any((npc.get("x", -1) + dx, npc.get("y", -1) + dy) in cell_reach[mid]
                     for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))):
            fail("NPC_INTERACTION_CELL_UNREACHABLE", nid, mid)
        for iid, prices in npc.get("shop", {}).items():
            if resolve("items", iid) is None:
                fail("SHOP_ITEM_MISSING", nid, iid)
            elif prices.get("buy_price") is not None:
                acquired.add(iid)
    # Only rewards whose material prerequisites are already reachable expand
    # the acquisition set. A self-dependent recipe is not a valid acquisition.
    pending = list(runtime.get("recipes", {}).values()) + list(runtime.get("quests", {}).values())
    for _ in range(len(pending) + 1):
        previous = len(acquired)
        for entry in pending:
            materials = entry.get("ingredients", entry.get("materials", {}))
            if isinstance(materials, list):
                material_ids = [m.get("item_id") for m in materials if isinstance(m, dict)]
            else:
                material_ids = list(materials)
            material_ids.extend(o.get("id") for o in entry.get("objectives", []) if o.get("kind") == "collect")
            if any(i not in acquired for i in material_ids):
                continue
            if any(o.get("id") not in spawned for o in entry.get("objectives", []) if o.get("kind") == "kill"):
                continue
            if any(o.get("id") not in reached for o in entry.get("objectives", []) if o.get("kind") == "visit"):
                continue
            rewards = entry.get("rewards", [])
            if isinstance(rewards, dict):
                acquired.update(rewards.get("items", {}))
            else:
                for reward in rewards:
                    if isinstance(reward, dict) and reward.get("item_id"):
                        acquired.add(reward["item_id"])
            acquired.update(entry.get("results", {}))
            if entry.get("result_item_id"):
                acquired.add(entry["result_item_id"])
        if len(acquired) == previous:
            break
    for iid in runtime.get("items", {}):
        if iid not in acquired and not any(resolve("items", aid) is runtime["items"][iid] for aid in acquired):
            fail("ITEM_HAS_NO_NORMAL_ACQUISITION", iid)
        if runtime["items"][iid].get("action_type", "") not in ("", "return", "cleanse"):
            fail("ITEM_ACTION_UNSUPPORTED", iid, runtime["items"][iid].get("action_type"))
    for iid, skill in runtime.get("skills", {}).items():
        if skill.get("kind") not in SKILL_KINDS:
            fail("SKILL_ACTION_UNSUPPORTED", iid, skill.get("kind"))
        if skill.get("delivery", "melee") not in ("melee", "projectile", "area"):
            fail("SKILL_DELIVERY_UNSUPPORTED", iid, skill.get("delivery"))
        if skill.get("kind") in ("status", "debuff") and skill.get("status_type", skill.get("status")) not in STATUS_KINDS:
            fail("SKILL_STATUS_UNSUPPORTED", iid, skill.get("status_type", skill.get("status")))
        if not skill.get("teacher_ids"):
            fail("SKILL_HAS_NO_TEACHER", iid)
        for nid in skill.get("teacher_ids", []):
            if resolve("npcs", nid) is None:
                fail("SKILL_TEACHER_MISSING", iid, nid)
        for item_id, quantity in skill.get("ingredients", {}).items():
            if resolve("items", item_id) is None or quantity <= 0:
                fail("SKILL_INGREDIENT_INVALID", iid, item_id)
    if runtime.get("config", {}).get("level_cap") != 99 or len(runtime.get("xp_thresholds", [])) < 99:
        fail("LEVEL_1_99_CONTRACT_UNBOUND", "growth")
    return {"status": "STATIC_PASS" if not errors else "STATIC_FAIL", "errors": errors,
            "error_counts": dict(Counter(e["code"] for e in errors)), "stats": dict(stats),
            "reachable_maps": len(reached), "registered_maps": len(maps),
            "functional_runtime_test": "NOT_RUN", "platform_test": "NOT_RUN",
            "contract_scope_sha256": contract["scope_sha256"], "runtime_sha256": digest(runtime)}


def self_test():
    def row(iid, profile, name="같은 기술", job="도사", value=5):
        return {"content_id": iid, "record_type": "skill", "entity_name_ko": name,
                "build_profile_id": profile, "game_region": "KR", "selected_for_build": True,
                "selected_original_value": {"job": job, "learn_level": value}}
    rows = [row("new", PROFILE), row("old", OLDER, "같은기술", value=9),
            row("unique", OLDER, "다른 기술"), row("different-job", PROFILE, job="도적")]
    selected, decisions = select_semantic_rows(rows)
    assert {r["content_id"] for r in selected} == {"new", "unique", "different-job"}
    assert next(d for d in decisions if d["content_id"] == "old")["reason"].startswith("OLDER_VARIANT")
    # Same-name different stats must survive within the chosen profile.
    selected, _ = select_semantic_rows([row("a", PROFILE), row("b", PROFILE, value=6)])
    assert len(selected) == 2
    range_rows = [{**row("range", OLDER), "record_type": "item", "entity_name_ko": "망또00번~01번"},
                  {**row("v0", PROFILE), "record_type": "item", "entity_name_ko": "망또00"},
                  {**row("v1", PROFILE), "record_type": "item", "entity_name_ko": "망또01"}]
    selected, decisions = select_semantic_rows(range_rows)
    assert {r["content_id"] for r in selected} == {"v0", "v1"}
    base = {"maps": {"town": {"width": 3, "height": 3, "exits": [], "blocked": [],
                              "spawns": [{"monster_id": "mob", "x": 1, "y": 1}]}},
            "start": {"map_id": "town", "x": 0, "y": 0, "starter_items": []},
            "monsters": {"mob": {"drops": [{"item_id": "loot", "chance": 1}]}},
            "items": {"loot": {}}, "npcs": {}, "skills": {}, "config": {"level_cap": 99},
            "xp_thresholds": list(range(99))}
    contract = {"required_ids": {"items": ["loot"], "monsters": ["mob"]}, "scope_sha256": "fixture"}
    assert audit_runtime(contract, base)["status"] == "STATIC_PASS"
    broken = deepcopy(base)
    broken["monsters"]["mob"]["drops"] = []
    assert audit_runtime(contract, broken)["error_counts"]["ITEM_HAS_NO_NORMAL_ACQUISITION"] == 1
    broken = deepcopy(base)
    broken["maps"]["town"]["exits"] = [{"id": "bad", "x": 0, "y": 0, "to_map": "missing", "to_x": 0, "to_y": 0}]
    assert audit_runtime(contract, broken)["error_counts"]["EXIT_MAP_MISSING"] == 1
    broken = deepcopy(base)
    broken["id_aliases"] = {"loot": "lost", "lost": "loot"}
    assert audit_runtime(contract, broken)["error_counts"]["REQUIRED_ID_UNBOUND"] == 1
    broken = deepcopy(base)
    broken["recipes"] = {"cycle": {"ingredients": {"loot": 1}, "result_item_id": "loot"}}
    broken["monsters"]["mob"]["drops"] = []
    assert audit_runtime(contract, broken)["error_counts"]["ITEM_HAS_NO_NORMAL_ACQUISITION"] == 1
    broken = deepcopy(base)
    broken["items"]["loot"]["action_type"] = "unsupported-silent-fallback"
    assert audit_runtime(contract, broken)["error_counts"]["ITEM_ACTION_UNSUPPORTED"] == 1
    source_contract = {"required_ids": {"items": ["must-remain"]},
                       "required_content": {"items": {"must-remain": {}}},
                       "required_counts": {"items": 1}, "source_scope_sha256": "source"}
    frozen = freeze_derived_ids(source_contract, {"items": {"extra": {"name": "dependency"}}})
    assert frozen["required_ids"]["items"] == ["extra", "must-remain"]
    assert freeze_derived_ids(frozen, {"items": {"extra": {"name": "dependency"}}}) == frozen
    blindness = deepcopy(base)
    blindness["npcs"] = {"teacher": {"map_id": "town", "x": 2, "y": 2, "shop": {}}}
    blindness["skills"] = {"blindness": {"kind": "status", "status": "blindness", "teacher_ids": ["teacher"], "ingredients": {}}}
    assert audit_runtime(contract, blindness)["status"] == "STATIC_PASS"
    unknown = deepcopy(blindness)
    unknown["skills"]["blindness"]["status"] = "unsupported-mind-control"
    assert audit_runtime(contract, unknown)["error_counts"]["SKILL_STATUS_UNSUPPORTED"] == 1
    print(canonical({"status": "PASS", "scope": "deterministic selector and negative static-closure fixtures only",
                     "fixture_assertions": 14, "game_tests_performed": 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit-runtime", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--freeze-derived", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.freeze_derived:
        result = freeze_derived_ids(json.loads(args.contract.read_text()), json.loads(args.freeze_derived.read_text()))
    elif args.audit_runtime:
        result = audit_runtime(json.loads(args.contract.read_text()), json.loads(args.audit_runtime.read_text()))
    else:
        result = make_contract(args.normalized, args.catalog, json.loads(args.baseline.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(canonical({"output": str(args.output), "sha256": digest(args.output),
                     "status": result.get("scope_status", result.get("status")),
                     "counts": result.get("required_counts", result.get("error_counts"))}))


if __name__ == "__main__":
    main()
