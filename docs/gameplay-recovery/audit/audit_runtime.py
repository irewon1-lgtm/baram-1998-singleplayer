#!/usr/bin/env python3
"""Read-only topology/content audit. Static success is never gameplay success.

Input world must be emitted by export_runtime_world.gd using the exact engine
registry and private source assets. Output contains identities/metrics, not pixels
or full layouts. Direction masks mirror main.gd free_cell at f248613d.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess

DIRS = ((0, -1), (-1, 0), (0, 1), (1, 0))
BITS = (1, 8, 2, 4)


def load(path):
    return json.loads(Path(path).read_text())


def definition(record):
    return record.get("runtime_definition", record.get("data", {}).get("runtime_definition", record.get("data", {})))


def git_bytes(ref, path):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"])


def packages(release, ref):
    index = json.loads(git_bytes(ref, "content-work/HANDOFF_INDEX.json"))
    result = []
    for row in index["packages"]:
        if not row["batch_id"].startswith("WK-CONTENT-"):
            continue
        raw = git_bytes(ref, row["manifest_path"])
        manifest = json.loads(raw)
        issues = []
        prefix = row["manifest_path"].rsplit("/", 1)[0]
        for member in manifest["files"]:
            data = git_bytes(ref, prefix + "/" + member["path"])
            if len(data) != member["size_bytes"] or hashlib.sha256(data).hexdigest() != member["sha256"]:
                issues.append(member["path"])
        imported = release["imports"].get(row["batch_id"])
        manifest_match = hashlib.sha256(raw).hexdigest() == row["manifest_sha256"]
        result.append({
            "batch_id": row["batch_id"], "source_commit": row["package_commit"],
            "manifest_sha256": hashlib.sha256(raw).hexdigest(), "authored_counts": manifest["counts"],
            "authoring_files_check": "PASS" if not issues and manifest_match else "FAIL",
            "authoring_file_hash_errors": issues,
            "import_status": imported["status"] if imported else "NOT_IMPORTED",
            "import_identity_result": "PASS" if imported and imported["manifest_sha256"] == row["manifest_sha256"] and imported["source_commit"] == row["package_commit"] else "NOT_RUN",
            "runtime_reflection": "PASS" if imported else "FAIL",
            "active_import_identity_match": bool(imported and imported["manifest_sha256"] == row["manifest_sha256"] and imported["source_commit"] == row["package_commit"]),
            "applied_records": len(imported.get("applied_ids", [])) if imported else 0,
            "whole_package_gameplay": "NOT_RUN", "producer_combined_import_status": row.get("combined_import_status"),
            "required_capabilities": manifest.get("required_capabilities", []),
        })
    return result


def blockers(m):
    return {(int(n["x"]), int(n["y"])) for n in m["npcs"] if n.get("blocking", True)}


def valid(m, p, blocked_npcs=True):
    x, y = p
    return (0 <= x < int(m["width"]) and 0 <= y < int(m["height"])
            and not m["blocked"][y][x]
            and (not blocked_npcs or p not in m["_npc"]))


def flood(m, seed, initial=None):
    # No moving monsters: proves terrain/NPC connectivity only.
    reached = set() if initial is None else initial
    seed = tuple(map(int, seed))
    if seed in reached:
        return reached
    if not valid(m, seed):
        return reached
    q = collections.deque([seed])
    reached.add(seed)
    masks = m.get("collision_masks")
    while q:
        x, y = q.popleft()
        for d, (dx, dy) in enumerate(DIRS):
            p = (x + dx, y + dy)
            if p in reached or not valid(m, p):
                continue
            if masks and int(masks[p[1]][p[0]]) & BITS[d]:
                continue
            reached.add(p)
            q.append(p)
    return reached


def adjacent_reached(p, reached, radius=1):
    x, y = map(int, p)
    return any((x + dx, y + dy) in reached for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1))


def portal_reached(portal, reached):
    p = int(portal["x"]), int(portal["y"])
    return adjacent_reached(p, reached) if portal.get("trigger", "walk") == "interact" else p in reached


def melee_reached(p, reached):
    x, y = map(int, p)
    return any((x + dx, y + dy) in reached for dx, dy in DIRS)


def travel_destinations(m):
    for npc in m["npcs"]:
        if npc.get("role") == "travel":
            for target in npc.get("destinations", []):
                yield npc, target
        for service in npc.get("services", []):
            if service.get("type") in ("travel", "teleport"):
                for target in service.get("map_ids", []):
                    yield npc, target


def topology(world):
    maps = {m["id"]: m for m in world["maps"]}
    for m in maps.values():
        m["_npc"] = blockers(m)
    graph = set()
    q = collections.deque([world["home"]["map"]])
    while q:
        mid = q.popleft()
        if mid in graph:
            continue
        graph.add(mid)
        q.extend(p["target"] for p in maps[mid]["portals"] if p["target"] in maps)
        q.extend(target for _, target in travel_destinations(maps[mid]) if target in maps)
    global_cells = collections.defaultdict(set)
    queued_entries = {(world["home"]["map"], tuple(map(int, world["home"]["entry"])))}
    q = collections.deque(queued_entries)
    bad_arrivals = []
    while q:
        mid, entry = q.popleft()
        m = maps[mid]
        if not valid(m, entry):
            bad_arrivals.append({"map_id": mid, "entry": entry})
            continue
        if entry in global_cells[mid]:
            continue
        flood(m, entry, global_cells[mid])
        for p in m["portals"]:
            if p["target"] not in maps or not portal_reached(p, global_cells[mid]):
                continue
            key = p["target"], tuple(map(int, p["entry"]))
            if key not in queued_entries:
                queued_entries.add(key)
                q.append(key)
        for npc, target in travel_destinations(m):
            if target not in maps or not adjacent_reached((npc["x"], npc["y"]), global_cells[mid]):
                continue
            key = target, tuple(map(int, maps[target]["entry"]))
            if key not in queued_entries:
                queued_entries.add(key)
                q.append(key)
    summaries = []
    errors = []
    for mid, m in maps.items():
        reached = flood(m, m.get("entry", world["home"]["entry"]))
        portals = [p for p in m["portals"] if not portal_reached(p, reached)]
        spawns = [s for s in m["spawns"] if not valid(m, (int(s["x"]), int(s["y"])), False)]
        unattackable = [s for s in m["spawns"] if not melee_reached((s["x"], s["y"]), reached)]
        unavailable = [n for n in m["npcs"] if not adjacent_reached((n["x"], n["y"]), reached)]
        for p in m["portals"]:
            if p["target"] not in maps:
                errors.append({"map": mid, "portal": p.get("id"), "error": "MISSING_TARGET"})
            elif not valid(maps[p["target"]], tuple(map(int, p["entry"]))):
                errors.append({"map": mid, "portal": p.get("id"), "error": "DESTINATION_BLOCKED", "target": p["target"], "entry": p["entry"]})
        summaries.append({
            "id": mid, "name": m["name"], "kind": m.get("kind"), "width": m["width"], "height": m["height"],
            "source_geometry": m.get("original_map_id"), "entry": m.get("entry"),
            "graph_reachable": mid in graph, "terrain_reachable_from_home": bool(global_cells[mid]),
            "local_reachable_cells": len(reached), "global_reachable_cells": len(global_cells[mid]),
            "portals": len(m["portals"]), "locally_unreachable_portals": [{k: p.get(k) for k in ("id", "target", "x", "y", "trigger")} for p in portals],
            "monster_instances": len(m["spawns"]), "monster_types": len({s["kind"] for s in m["spawns"]}),
            "spawn_blocked_cells": [{"id": s.get("id"), "kind": s["kind"], "x": s["x"], "y": s["y"]} for s in spawns],
            "spawns_no_terrain_attack_access_from_entry": [{"id": s.get("id"), "kind": s["kind"], "x": s["x"], "y": s["y"]} for s in unattackable],
            "npc_instances": len(m["npcs"]), "npcs_no_terrain_interaction_access_from_entry": [{"id": n.get("definition_id", n["id"]), "name": n["name"], "x": n["x"], "y": n["y"]} for n in unavailable],
            "whole_map_playthrough": "NOT_RUN",
        })
    return {
        "physical_maps": len(maps), "graph_reachable_maps": len(graph), "terrain_reachable_maps_from_home": sum(bool(v) for v in global_cells.values()),
        "graph_unreachable_map_ids": sorted(set(maps) - graph),
        "terrain_unreachable_map_ids": sorted(mid for mid in maps if not global_cells[mid]),
        "portal_reference_or_arrival_errors": errors, "invalid_global_arrivals": bad_arrivals,
        "maps_with_unreachable_local_portals": sum(bool(x["locally_unreachable_portals"]) for x in summaries),
        "blocked_spawn_instances": sum(len(x["spawn_blocked_cells"]) for x in summaries),
        "spawns_no_local_terrain_access": sum(len(x["spawns_no_terrain_attack_access_from_entry"]) for x in summaries),
        "npcs_no_local_terrain_access": sum(len(x["npcs_no_terrain_interaction_access_from_entry"]) for x in summaries),
        "empty_maps": sum(not m["spawns"] and not m["npcs"] for m in maps.values()),
        "maps": summaries,
        "scope": "STATIC_TERRAIN_DIRECTIONAL_COLLISION_AND_BLOCKING_NPCS; DYNAMIC_MONSTER_OCCUPANCY_AND_ACTUAL_PLAY_NOT_RUN",
    }


def content_links(release, world):
    defs = {rid: definition(r) for rid, r in release["records"].items()}
    kinds = collections.defaultdict(set)
    for rid, rec in release["records"].items():
        kinds[rec["kind"]].add(rid)
    placed_monsters = {s["kind"] for m in world["maps"] for s in m["spawns"]}
    placed_npcs = {n["definition_id"] for m in world["maps"] for n in m["npcs"] if "definition_id" in n}
    refs = collections.defaultdict(set)
    for nid in placed_npcs:
        for service in defs[nid].get("services", []):
            for field in ("skill_ids", "quest_ids", "recipe_ids"):
                refs[field].update(service.get(field, []))
            if service.get("recipe_id"):
                refs["recipe_ids"].add(service["recipe_id"])
            if service.get("shop_id"):
                refs["shop_ids"].add(service["shop_id"])
    acquired = set()
    for rid in kinds["drop_group"]:
        for roll in defs[rid].get("rolls", []):
            if roll.get("item_id"):
                acquired.add(roll["item_id"])
    for rid in kinds["shop"]:
        for row in defs[rid].get("offers", defs[rid].get("inventory", defs[rid].get("items", []))):
            if row.get("item_id"):
                acquired.add(row["item_id"])
    for rid in kinds["quest"] | kinds["recipe"]:
        for row in defs[rid].get("rewards", []) + defs[rid].get("outputs", defs[rid].get("produce", [])):
            if row.get("item_id"):
                acquired.add(row["item_id"])
    inactive_npcs = {rid for rid in kinds["npc"] if not defs[rid].get("identity_variants", {}).get("active", True)}
    inactive_skills = {rid for rid in kinds["skill"] if defs[rid].get("variant", {}).get("role") == "inactive"}
    direct_skill_gap = kinds["skill"] - refs["skill_ids"] - inactive_skills
    has_legacy_trainer = any(n.get("role") == "trainer" for m in world["maps"] for n in m["npcs"])
    legacy_fallback = {rid for rid in direct_skill_gap if has_legacy_trainer and int(defs[rid].get("learn", {}).get("level", 100)) <= 99 and defs[rid].get("class_ids")}
    starter_overlevel = []
    for m in world["maps"]:
        data = defs.get(m.get("definition_id", m["id"]), {})
        bounds = data.get("recommended_level", [])
        if len(bounds) != 2 or int(bounds[1]) > 8:
            continue
        for monster_id in sorted({s["kind"] for s in m["spawns"]}):
            monster = defs.get(monster_id, {})
            if int(monster.get("level", 0)) > int(bounds[1]):
                starter_overlevel.append({"map_id": m["id"], "map_name": m["name"], "recommended": bounds,
                    "monster_id": monster_id, "monster_name": monster.get("name"), "monster_level": monster.get("level"), "hp": monster.get("hp")})
    def rows(ids):
        return [{"id": rid, "name": defs[rid].get("name", rid)} for rid in sorted(ids)]
    return {
        "definition_counts": {k: len(v) for k, v in kinds.items()},
        "monsters_not_placed": rows(kinds["monster"] - placed_monsters),
        "npc_definitions_not_placed_active": rows(kinds["npc"] - placed_npcs - inactive_npcs),
        "inactive_npc_variants": rows(inactive_npcs),
        "skills_not_in_placed_Work_npc_services": rows(direct_skill_gap),
        "skills_possible_via_legacy_trainer_fallback": rows(legacy_fallback),
        "skills_no_static_trainer_route": rows(direct_skill_gap - legacy_fallback),
        "quests_not_in_placed_npc_services": rows(kinds["quest"] - refs["quest_ids"]),
        "recipes_not_in_placed_npc_services": rows(kinds["recipe"] - refs["recipe_ids"]),
        "shops_not_in_placed_npc_services": rows(kinds["shop"] - refs["shop_ids"]),
        "items_no_declared_drop_shop_quest_or_recipe_source": rows(kinds["item"] - acquired),
        "starter_map_overlevel_monster_types": starter_overlevel,
        "skill_learning_materials_no_declared_source": [{"skill_id": rid, "item_id": row["item_id"]} for rid in sorted(kinds["skill"]) for row in defs[rid].get("learn", {}).get("consume", []) if row["item_id"] not in acquired],
        "quest_kill_objectives_without_placement": [{"quest_id": rid, "monster_id": row["monster_id"]} for rid in sorted(kinds["quest"]) for row in defs[rid].get("objectives", []) if row.get("type") == "kill" and row.get("monster_id") not in placed_monsters],
        "scope": "STRUCTURAL_REFERENCES_ONLY; REACHABLE_TRAINER_AND_ELIGIBILITY_AND_GAMEPLAY_CHECKS_SEPARATE",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--release", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-ref", default="origin/work/content-import")
    ap.add_argument("--scope", default="BASELINE_DELIVERED_CONTENT_STATIC_AUDIT_NOT_FULL_GAMEPLAY_PASS")
    ap.add_argument("--source-commit", default="f248613d")
    args = ap.parse_args()
    world, release = load(args.world), load(args.release)
    report = {
        "scope": args.scope,
        "source_commit_under_audit": args.source_commit,
        "work_branch_head": subprocess.check_output(["git", "rev-parse", args.work_ref], text=True).strip(),
        "content_version": world["audit_content_version"],
        "registry_sha256": world.get("audit_registry_sha256"),
        "world_repairs_sha256": world.get("audit_world_repairs_sha256"),
        "packages": packages(release, args.work_ref),
        "topology": topology(world),
        "links": content_links(release, world),
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"packages": [(r["batch_id"], r["import_status"]) for r in report["packages"]],
        "topology": {k: v for k, v in report["topology"].items() if k != "maps"},
        "links": {k: len(v) if isinstance(v, list) else v for k, v in report["links"].items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
