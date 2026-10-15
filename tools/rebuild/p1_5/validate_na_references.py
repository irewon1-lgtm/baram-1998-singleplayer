#!/usr/bin/env python3
"""Dry-read the private NA reference catalog and expose unresolved source references.

An integrity PASS never selects KR values or certifies the reference server behavior.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True, type=Path)
    ap.add_argument("--selected", required=True, type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    meta = json.loads(args.metadata.read_text())
    sources = {s["source_id"]: s for s in meta["sources"]}
    errors, blocked, records, checks = [], [], {}, collections.Counter()
    for source_id, source in sources.items():
        root = args.source_root / ("Project1998-source" if source["repository"].startswith("project1998/") else "RTK-Server-source")
        f = root / source["path"]
        if not f.is_file():
            blocked.append({"source_id": source_id, "reason": "MISSING_FILE"})
            continue
        b = f.read_bytes()
        checks["source_files_read"] += 1
        actual_blob = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
        if hashlib.sha256(b).hexdigest() != source["sha256"] or len(b) != source["bytes"] or actual_blob != source["git_blob_sha"]:
            errors.append({"source_id": source_id, "reason": "HASH_OR_LENGTH_MISMATCH"})
    table = collections.defaultdict(list)
    for output in meta["outputs"]:
        f = args.selected / output["path"]
        if not f.is_file():
            blocked.append({"output": output["path"], "reason": "MISSING_NORMALIZED_FILE"})
            continue
        if digest(f) != output["sha256"] or f.stat().st_size != output["bytes"]:
            errors.append({"output": output["path"], "reason": "NORMALIZED_FILE_HASH_MISMATCH"})
        count = 0
        for line_num, line in enumerate(f.open(), 1):
            count += 1
            obj = json.loads(line)
            rid = obj["record_id"]
            if rid in records:
                errors.append({"record_id": rid, "reason": "DUPLICATE_RECORD_ID"})
            records[rid] = obj
            if obj["source_id"] not in sources:
                errors.append({"record_id": rid, "reason": "UNRESOLVED_SOURCE_ID"})
            if obj["selected_for_build"] or obj["KR_selected_value"] is not None or obj["new_runtime_binding"] != "NOT_STARTED":
                errors.append({"record_id": rid, "reason": "UNAUTHORIZED_KR_PROMOTION"})
            source = sources[obj["source_id"]]
            if source["path"].startswith("game-data/") and source["path"].endswith(".csv"):
                table[Path(source["path"]).stem].append(obj)
            if obj["kind"].startswith("sql_content:") and obj["kind"].split(":", 1)[1] not in meta["SQL_allowlist"]:
                errors.append({"record_id": rid, "reason": "UNAPPROVED_SQL_TABLE"})
        checks["normalized_files_read"] += 1
        checks["normalized_records_read"] += count
        if count != output["records"]:
            errors.append({"output": output["path"], "reason": "RECORD_COUNT_MISMATCH"})
    # Source-local graph: report dead/unresolved entries instead of assigning fake targets/defaults.
    links, unresolved = collections.Counter(), []
    mobs = {x["original_value"]["Identifier"] for x in table["mobs"]}
    mobids = {x["original_value"]["MobId"] for x in table["mobs"]}
    items = {x["original_value"]["ItmIdentifier"] for x in table["Items"]}
    npcs = {x["original_value"]["NpcIdentifier"] for x in table["NPCs"]}
    npcids = {x["original_value"]["NpcId"] for x in table["NPCs"]}
    spells = {x["original_value"]["SplIdentifier"] for x in table["Spells"]}
    paths = {x["original_value"]["PthId"] for x in table["Paths"]}

    def link(obj, field, value, target, relation, sentinels=()):
        if value in sentinels:
            links[relation + ":sentinel"] += 1
        elif value in target:
            links[relation + ":resolved"] += 1
        else:
            links[relation + ":unresolved"] += 1
            unresolved.append({"record_id": obj["record_id"], "relation": relation, "field": field, "value": value, "status": "UNRESOLVED_SOURCE_REFERENCE", "selected_for_build": False})

    for obj in table["MobDrops"]:
        v = obj["original_value"]
        link(obj, "MobKey", v["MobKey"], mobs, "drop_to_monster")
        for col in ["Loot", "RareLoot"]:
            for token in v.get(col, "").split("|"):
                if not token:
                    continue
                pieces = token.split(":")
                link(obj, col, pieces[0], items, "drop_to_item", ("GOLD",))
                rate = float(pieces[-1])
                if not 0 <= rate <= 100:
                    errors.append({"record_id": obj["record_id"], "reason": "RATE_OUT_OF_PERCENT_RANGE"})
    for obj in table["Spawns"]:
        v = obj["original_value"]
        link(obj, "SpnMobId", v["SpnMobId"], mobids, "static_spawn_to_monster")
        link(obj, "SpnMobIdReplace", v["SpnMobIdReplace"], mobids, "static_spawn_replacement_to_monster", ("0",))
    for name in ["AreaSpawns", "AreaSpawnsTrap", "AreaSpawnsCrafting"]:
        for obj in table[name]:
            link(obj, "MobId", obj["original_value"]["MobId"], mobids, "area_spawn_to_monster")
    for obj in table["NPCEquipment"]:
        link(obj, "NeqNpcId", obj["original_value"]["NeqNpcId"], npcids, "npc_equipment_to_npc")
    for name in ["ShopStock", "ShopBuysFrom", "ShopCatalogues"]:
        for obj in table[name]:
            v = obj["original_value"]
            field = "NpcIdentifier" if "NpcIdentifier" in v else "NpcKey"
            link(obj, field, v[field], npcs, "shop_to_npc")
            for item in v["ItemKeys"].split("|"):
                link(obj, "ItemKeys", item, items, "shop_to_item", ("-", ""))
    for obj in table["SpellLearnCosts"]:
        v = obj["original_value"]
        link(obj, "key", v["key"], spells, "learn_cost_to_spell")
        link(obj, "pathId", v["pathId"], paths, "learn_cost_to_path")
        for key in ["item1", "item2", "item3", "item4"]:
            link(obj, key, v.get(key), items, "learn_cost_to_item", ("", None))
    for obj in table["Spells"]:
        v = obj["original_value"]
        # Source Content.Spells.cs:431/461: path99 deliberately matches no normal class;
        # separate GM/proc/dog paths may call these rows. It is not a fabricated class.
        link(obj, "SplPthId", v["SplPthId"], paths, "spell_to_path", ("99",))
    status = "FAIL" if errors else "BLOCKED" if blocked else "PASS"
    result = {"scope": "STATIC_NA_SOURCE_HASH_JSON_READ_AND_DECLARED_REFERENCES_ONLY", "integrity_result": status, "reference_graph_result": "PARTIAL" if unresolved else "PASS", "errors": errors, "blocked": blocked, "checks": dict(checks), "links": dict(sorted(links.items())), "unresolved_source_references": unresolved, "KR_historical_accuracy": "UNKNOWN", "KR_selected_values": 0, "new_game_tests": "NOT_RUN", "not_claimed": ["all NA runtime rows load", "complete NPC dialogue/craft graph", "Korean historical values", "reference binary compatibility", "actual game audio or timing", "Codex G0 access"]}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["integrity_result", "reference_graph_result", "checks", "links"]}, indent=2))
    return 1 if errors else 2 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
