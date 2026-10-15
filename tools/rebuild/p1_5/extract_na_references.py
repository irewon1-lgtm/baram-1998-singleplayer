#!/usr/bin/env python3
"""Static NA reference extraction. Never imports or executes reference code/SQL/Lua.

Not a KR restoration importer. Every record remains unselected for the new game.
SQL is parsed only for named content tables; account/save tables are excluded.
"""
from __future__ import annotations
import argparse
import collections
import csv
from decimal import Decimal, ROUND_FLOOR
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

P_SHA = "65cb3ef28f289ee35d19abfb6829d6120b9ec0cd"
R_SHA = "e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6"
TABLES = {
    "npc": "NPCs NPCEquipment NpcAbilities",
    "monster": "mobs MobDrops MobEquipment MobFlees MobStationary MobSpells MobChatter MobSpawnRules MobBosses Spawns AreaSpawns AreaSpawnsTrap AreaSpawnsCrafting",
    "economy": "Items ItemParams ShopStock ShopBuysFrom ShopCatalogues CraftingToggles ArmorQuests MinorQuests HarvestNodes ForageAreas",
    "job_skill": "Paths PathHalls PathGrowth LevelExp Spells SpellLevels SpellLearnCosts SpellParams SpellMods SpellText spell_effects",
    "map": "Warps GatewayGates WorldMapDests WorldMapTriggers WarpQuestLocks Inns EraFeatures",
}
SQL_TABLES = {"Items", "ItemSets", "Maps", "MobEquipment", "Mobs", "NPCEquipment0", "NPCs0", "Paths", "Recipes", "Spawns0", "Spawns1", "Spells", "Warps"}
CONSUMERS = {
    "npc": ["Server/Content.Csv.cs", "Server/Content.Mobs.cs", "Server/NpcScripts.cs", "Server/NpcScript.cs", "Server/NpcAbility.cs", "Server/World.Populate.cs"],
    "monster": ["Server/Content.Csv.cs", "Server/Content.Mobs.cs", "Server/World.SpawnDirector.cs", "Server/World.MobAiTick.cs"],
    "economy": ["Server/Content.Csv.cs", "Server/Content.Items.cs", "Server/Shops.cs", "Server/NpcAbility.cs", "Server/ArmorQuest.cs"],
    "job_skill": ["Server/Content.Spells.cs", "Server/Content.Csv.cs", "Server/Session.Spells.cs", "Server/Session.Combat.cs", "Server/NpcAbility.cs"],
    "map": ["Server/Content.Csv.cs", "Server/Content.Maps.cs", "Server/World.SpawnDirector.cs"],
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lines(p):
    return p.read_text(encoding="utf-8-sig").splitlines()


def csv_rows(p):
    """Respect comments and preserve physical CSV row positions, including multiline rows."""
    raw = lines(p)
    filtered = [(i, l) for i, l in enumerate(raw, 1) if l.strip() and not l.lstrip().startswith("#")]
    reader = csv.reader([l for _, l in filtered])
    header = next(reader)
    previous = reader.line_num
    for row in reader:
        start = filtered[previous][0]
        end = filtered[reader.line_num - 1][0]
        previous = reader.line_num
        if len(row) > len(header):
            raise ValueError(f"CSV width mismatch {p.name}:{start}: {len(row)} != {len(header)}")
        result = dict(zip(header, row))
        if len(row) < len(header):
            result["__parse_missing_columns__"] = header[len(row):]
        yield start, end, result


def balanced(text, start, opener="{", closer="}"):
    """Balanced literal span, honoring quoted strings and Lua line comments."""
    assert text[start] == opener
    depth = 0
    quote = None
    i = start
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif text.startswith("--", i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError("Unclosed literal")


def sql_rows(p):
    """Read only the explicit content whitelist. No SQL interpreter/database is involved."""
    text = p.read_text(encoding="utf-8")
    schemas = {}
    for m in re.finditer(r"CREATE TABLE `([^`]+)` \((.*?)\n\) ENGINE=", text, re.S):
        if m[1] in SQL_TABLES:
            schemas[m[1]] = re.findall(r"^  `([^`]+)`", m[2], re.M)
    counts = collections.Counter({t: 0 for t in sorted(schemas)})
    for m in re.finditer(r"^INSERT INTO `([^`]+)` VALUES ", text, re.M):
        table = m[1]
        if table not in SQL_TABLES:
            continue
        header = schemas[table]
        i = m.end()
        tuple_index = 0
        while text[i] == "(":
            start = i
            block = balanced(text, i, "(", ")")
            values, token, quote, escape, quoted_literal = [], [], False, False, False
            for c in block[1:-1] + ",":
                if escape:
                    token.append({"n": "\n", "r": "\r", "t": "\t", "0": "\0", "b": "\b", "Z": "\x1a"}.get(c, c))
                    escape = False
                elif quote and c == "\\":
                    escape = True
                elif c == "'":
                    quote = not quote
                    quoted_literal = True
                elif c == "," and not quote:
                    val = "".join(token)
                    values.append(None if val == "NULL" and not quoted_literal else val)
                    token = []
                    quoted_literal = False
                else:
                    token.append(c)
            if quote or escape or len(values) != len(header):
                raise ValueError(f"Unsupported SQL syntax {table} tuple {tuple_index}")
            tuple_index += 1
            counts[table] += 1
            yield table, text.count("\n", 0, start) + 1, start, tuple_index, dict(zip(header, values))
            i += len(block)
            if text[i] != ",":
                break
            i += 1
    return counts


def evidence(source, file, first, last=None):
    return {"source_id": source, "relative_path": file, "line_start": first, "line_end": last or first}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--metadata", type=Path, required=True)
    args = ap.parse_args()
    p = args.source_root / "Project1998-source"
    r = args.source_root / "RTK-Server-source"
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    manifests, csv_data, diagnostics = {}, {}, []
    records_by_domain = collections.defaultdict(list)

    def register(repo, path, purpose):
        root, commit, repo_name = (p, P_SHA, "project1998/Project1998") if repo == "P1998" else (r, R_SHA, "unkmc/RTK-Server")
        key = f"P15-NA-{repo}-" + hashlib.sha256(path.encode()).hexdigest()[:12]
        if key not in manifests:
            f = root / path
            if not f.is_file():
                raise FileNotFoundError(f)
            b = f.read_bytes()
            manifests[key] = {"source_id": key, "source_type": "SERVER_REIMPLEMENTATION_SOURCE", "source_family": "RTK_MITHIA_CLASSICTK" if repo == "RTK" else "PROJECT1998_DERIVED_RTK_MITHIA_CLASSICTK", "repository": repo_name, "commit": commit, "path": path, "source_path_or_url": f"https://github.com/{repo_name}/blob/{commit}/{path}", "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "git_blob_sha": hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest(), "game_region": "NA", "content_era": "2026 reconstruction of 2001 NA 4.95; mixed 7.x/2019 reference" if repo == "P1998" else "2020 fan-server/Mithia/ClassicTK2019 lineage; 7.x", "purpose": purpose, "historical_fact_status_for_KR": "UNKNOWN", "utilization_status": "IDENTIFIED", "selected_for_build": False}
        return key

    def record(repo, path, row_id, value, start, end=None, kind="source_row"):
        sid = register(repo, path, kind)
        value = dict(value)
        missing = value.pop("__parse_missing_columns__", [])
        if missing:
            diagnostics.append({"type": "MISSING_TRAILING_CSV_COLUMNS", "source_id": sid, "line": start, "missing_columns": missing, "action": "left_absent_without_default"})
        return {"record_id": f"NA-{repo}-{row_id}", "kind": kind, "source_id": sid, "source_location": {"line_start": start, "line_end": end or start}, "source_shape_missing_columns": missing, "original_value": value, "KR_selected_value": None, "reconstructed_value": None, "game_region": "NA", "fact_status": "UNKNOWN", "selected_for_build": False, "new_runtime_binding": "NOT_STARTED", "test_status": "NOT_RUN"}

    for domain, names in TABLES.items():
        for name in names.split():
            path = f"game-data/{name}.csv"
            rows = list(csv_rows(p / path))
            csv_data[name] = rows
            for first, last, value in rows:
                records_by_domain[domain].append(record("P1998", path, f"{name}-L{first}", value, first, last))
            counts[f"P1998.{name}"] = len(rows)
            sid = register("P1998", path, "CSV_CONTENT_TABLE")
            matches = []
            for consumer in CONSUMERS[domain] + ["Server/Content.Tables.cs", "Server/Content.cs"]:
                f = p / consumer
                if not f.is_file():
                    continue
                for n, line in enumerate(lines(f), 1):
                    if f"\"{name}.csv\"" in line or f"TableId.{name}" in line:
                        cid = register("P1998", consumer, "CONSUMER_CODE")
                        matches.append(evidence(cid, consumer, n))
            manifests[sid]["consumer_anchors"] = matches
            manifests[sid]["consumer_scope"] = "literal table declarations/load sites; runtime filtering and later consumers separately documented"
            manifests[sid]["rows_parsed"] = len(rows)

    # Full whitelisted SQL rows, preserving namespace and tuple offsets. Never touch account/save rows.
    sqlpath = "database/2020-09-02-21-55-01_RTK.sql.bak"
    sqlcounts = collections.Counter({name: 0 for name in SQL_TABLES})
    for table, line, offset, idx, value in sql_rows(r / sqlpath):
        row = record("RTK", sqlpath, f"SQL-{table}-O{offset}", value, line, kind=f"sql_content:{table}")
        row["source_location"].update({"character_offset": offset, "offset_unit": "unicode_codepoints_from_file_start", "tuple_index": idx})
        records_by_domain["rtk_sql"].append(row)
        sqlcounts[table] += 1
    counts.update({f"RTK.SQL.{k}": v for k, v in sqlcounts.items()})

    # Parse RTK's full literal drop table and preserve all duplicate item lines and source order.
    droppath = "rtklua/Accepted/Mobs/MobDrops.lua"
    droptext = (r / droppath).read_text()
    start = droptext.index("{", droptext.index("local _mobDropsTable"))
    body = balanced(droptext, start)
    drop_tables = {}
    for m in re.finditer(r'\["([a-zA-Z0-9_]+)"\]\s*=\s*\{', body):
        key = m[1]
        block = balanced(body, m.end() - 1)
        tables = {}
        for field in ["loot", "rareLoot"]:
            sub = re.search(r"\b" + field + r"\s*=\s*\{", block)
            if not sub:
                continue
            literal = balanced(block, sub.end() - 1)
            arrays = {}
            for name in ["items", "amounts", "rates"]:
                am = re.search(r"\b" + name + r"\s*=\s*\{([^}]*)\}", literal, re.S)
                arrays[name] = None if not am else [x.strip() for x in am[1].split(",") if x.strip()]
            items, amounts, rates = arrays["items"], arrays["amounts"], arrays["rates"]
            if items is None or rates is None or len(rates) < len(items) or (field == "loot" and (amounts is None or len(amounts) < len(items))):
                tables[field] = {"semantic_parse": "BLOCKED_SOURCE_ARRAY_LENGTH_MISMATCH", "raw_arrays": arrays}
                diagnostics.append({"type": "RTK_DROP_ARRAY_LENGTH_MISMATCH", "mob_key": key, "table": field, "lengths": {k: None if v is None else len(v) for k, v in arrays.items()}, "action": "retain_raw_arrays_without_defaults_or_probability_selection"})
                continue
            if len(rates) > len(items) or (amounts is not None and len(amounts) > len(items)):
                diagnostics.append({"type": "RTK_DROP_UNUSED_TRAILING_ARRAY_VALUES", "mob_key": key, "table": field, "raw_arrays": arrays, "action": "consumer_iterates_items_length_so_extra_amounts_or_rates_are_unused"})
            rolls = []
            for i, item in enumerate(items):
                gold = not item.startswith(('"', "'"))
                threshold = int((Decimal(rates[i]) * 1000).to_integral_value(rounding=ROUND_FLOOR))
                rolls.append({"sequence": i + 1, "item_key": None if gold else item[1:-1], "numeric_gold_token": item if gold else None, "rate_percent_literal": rates[i], "rng_integer_min": 1, "rng_integer_max": 100000, "pass_threshold": threshold, "amount_literal": "1" if field == "rareLoot" else amounts[i], "amount_semantics": "exact1" if field == "rareLoot" else ("fixed_gold_amount" if gold else "uniform_integer_1_to_max"), "selection_semantics": "independent_each_line" if field == "loot" else "roll_all_then_first_success_in_source_order", "nothing_possible": threshold < 100000})
            tables[field] = rolls
        line = droptext.count("\n", 0, start + m.start()) + 1
        value = {"mob_key": key, "tables": tables, "special_condition": "map-range-dependent mercenary table" if key.startswith("nagnag_armory_") else None, "requires_additional_global_drops": ["_handleMapFragmentLoot", "_handleDragonEssenceLoot"], "global_drop_conditions_not_flattened": True}
        records_by_domain["rtk_drops"].append(record("RTK", droppath, f"drop-{key}", value, line, kind="literal_drop_table"))
        drop_tables[key] = tables
    counts["RTK.literal_drop_tables"] = len(drop_tables)

    # Static call-site inventories, not a Lua interpreter or a branch-complete dialogue graph.
    script_groups = {"npc_calls": [r / "rtklua/Accepted/NPCs"], "craft_calls": [r / "rtklua/Accepted/Crafting", r / "rtklua/Accepted/Quests"], "spell_calls": [r / "rtklua/Accepted/Spells"]}
    call_pattern = re.compile(r"[:.]([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    relevant = re.compile(r"say|dialog|menu|input|buy|sell|repair|item|spell|warp|gold|money|exp|action|sound|animation|duration|aether|mana|health|vita|damage|heal", re.I)
    for domain, dirs in script_groups.items():
        files = sorted({f for d in dirs for f in d.rglob("*.lua")})
        for f in files:
            path = str(f.relative_to(r))
            calls = []
            branches = []
            for n, line in enumerate(lines(f), 1):
                stripped = line.strip()
                if stripped.startswith("--"):
                    continue
                names = [m[1] for m in call_pattern.finditer(line) if relevant.search(m[1])]
                if names:
                    calls.append({"line": n, "method_names": names, "source_text": stripped, "complete_statement": False, "literal_arguments_only": False})
                if re.match(r"(?:if|elseif|else\b|for\b|while\b)", stripped):
                    branches.append({"line": n, "source_text": stripped})
            value = {"path": path, "call_sites": calls, "branch_anchors": branches, "semantic_parse": "PARTIAL_LEXICAL_INDEX_ONLY", "dialogue_graph": "NOT_DECODED", "unsupported": ["multiline arguments", "computed table values", "interprocedural branch resolution", "runtime flags and callbacks"]}
            records_by_domain[domain].append(record("RTK", path, "script-" + hashlib.sha256(path.encode()).hexdigest()[:16], value, 1, len(lines(f)), kind="static_script_index"))
        counts[f"RTK.{domain}.files"] = len(files)
        counts[f"RTK.{domain}.call_sites"] = sum(len(x["original_value"]["call_sites"]) for x in records_by_domain[domain])
    # P1998's scripted dialogues get the same explicit partial-index status.
    path = "game-data/npc_dialog.lua"
    text = (p / path).read_text()
    npc_entries = list(re.finditer(r"^(?:function\s+)?(npcs(?:_say)?)\.([A-Za-z0-9_]+)(?:\s*=\s*function)?\s*\(", text, re.M))
    for idx, m in enumerate(npc_entries):
        end = npc_entries[idx + 1].start() if idx + 1 < len(npc_entries) else len(text)
        block = text[m.start():end]
        first = text.count("\n", 0, m.start()) + 1
        value = {"npc_identifier": m[2], "callback_kind": m[1], "calls": [{"line": first + n, "source_text": line.strip()} for n, line in enumerate(block.splitlines()) if re.search(r"ctx[:.]", line) and not line.lstrip().startswith("--")], "semantic_parse": "PARTIAL_LEXICAL_INDEX_ONLY", "dialogue_graph": "NOT_DECODED", "requires_consumer": "Server/NpcScript.cs"}
        records_by_domain["npc_dialogue"].append(record("P1998", path, f"dialog-{m[1]}-{m[2]}", value, first, text.count("\n", 0, end) + 1, kind="static_script_index"))
    counts["P1998.lua_dialogue_entrypoints"] = len(npc_entries)

    # Full dependency manifests, without restore/build/package installation.
    dependencies = []
    for f in sorted(p.rglob("*.csproj")):
        root = ET.fromstring(f.read_text(encoding="utf-8-sig"))
        dependencies.append({"path": str(f.relative_to(p)), "sha256": sha(f), "packages": [x.attrib for x in root.iter("PackageReference")], "project_references": [x.attrib for x in root.iter("ProjectReference")], "target_frameworks": [x.text for x in root.iter("TargetFramework")]})
    findings = [
        ("NPC_DIRECTION_OVERRIDE", "P1998", "Server/Content.Csv.cs", 547, 590, "Stored NpcSide is preserved in raw rows but LoadNpcs selects Dir=2; raw CSV is not proof that the runtime honors direction."),
        ("NPC_EQUIPMENT_UNBOUND", "P1998", "game-data/NPCEquipment.csv", 1, 2, "One equipment row exists; no reference to this table was found in the fixed Server source. File presence is not actual composite rendering."),
        ("REPAIR_STUB", "P1998", "Server/NpcAbility.cs", 529, 536, "RepairAbility exposes a stub dialogue; it does not repair durability or charge a repair price."),
        ("LOOT_INDEPENDENT", "RTK", "rtklua/Accepted/Mobs/MobDrops.lua", 3437, 3468, "Each loot line rolls integer1..100000 against rate*1000 independently. Duplicate item lines are separate rolls. Non-gold amount is uniform1..maximum; gold uses the fixed stored amount."),
        ("RARE_ORDERED_FIRST_SUCCESS", "RTK", "rtklua/Accepted/Mobs/MobDrops.lua", 3473, 3499, "All rare rows roll independently, then only the first successful source-order item drops. No-success is possible. Rates are not exclusive weights and must not be normalized."),
        ("DROP_GLOBAL_CONDITIONS", "RTK", "rtklua/Accepted/Mobs/MobDrops.lua", 3631, 3654, "HandleMobDrops requires a PC killer and also calls map-fragment and dragon-essence global handlers; literal per-monster tables alone are not the complete conditional drop system."),
        ("P1998_GOLD_DIVERGENCE", "P1998", "Server/Content.Mobs.cs", 442, 464, "P1998 rolls amount1..maximum before its gold branch, unlike RTK fixed gold. Same lineage does not mean identical behavior."),
        ("P1998_CALIBRATED_ADDED_RATES", "P1998", "re/extract_mob_drops.py", 34, 72, "Archive corrections include deliberately calibrated accessory drop rates; archive item presence does not establish those probabilities. Do not promote them as original KR rates."),
        ("RTK_RECIPE_EMPTY", "RTK", "database/2020-09-02-21-55-01_RTK.sql.bak", 1597, 1635, "Recipes has24 columns but zero INSERT rows. Crafting Lua16 files are separately indexed; an empty SQL recipe table does not prove no crafting exists."),
        ("RTK_RECIPE_CONSUMER", "RTK", "rtk/src/map/recipedb.c", 79, 109, "Recipe C loader expects RecSuccessRate/RecCraftTime/materials/critical fields; no recipe probabilities can be selected from the empty dump."),
        ("P1998_DIALOGUE_PRECEDENCE", "P1998", "game-data/npc_dialog.lua", 1, 18, "NA Lua dialogues override C# abilities where present.26 indexed click/speech callbacks are not380 complete NPC dialogue graphs or KR original words."),
        ("P1998_NPC_SERVICE_NARROWING", "P1998", "Server/NpcScripts.cs", 58, 84, "Explicit NpcAbilities compositions can narrow an ability by NPC ID/map; otherwise shop/repair/bank flags form fallback abilities. Repair fallback still targets the stub."),
        ("P1998_PATH99_SENTINEL", "P1998", "Server/Content.Spells.cs", 425, 465, "Path99 is a source-defined no-normal-class marker, not a missing fifth player class; GM/proc/dog-specific acquisition paths remain separate."),
        ("RTK_NPC_COMPOSITE_LOADER", "RTK", "rtk/src/map/npc.c", 230, 257, "C loader reads NPC look/palette/face/hair/skin/sex/direction and is-char independently. NA IDs are not identified with KR asset IDs."),
        ("RTK_REFERENCE_DB_SENSITIVE_ROWS", "RTK", "database/2020-09-02-21-55-01_RTK.sql.bak", 430, 523, "The upstream reference dump contains external character authentication-related hashes, internal IPs and game-state rows. Values are never emitted; all such tables are excluded from normalized outputs. This is not evidence of the user's credentials leaking."),
    ]
    semantic_findings = []
    for fid, repo, path, first, last, note in findings:
        sid = register(repo, path, "SEMANTIC_CODE_OBSERVATION")
        semantic_findings.append({"finding_id": fid, "evidence": evidence(sid, path, first, last), "finding": note, "scope": "STATIC_SOURCE_LOCAL_NA_ONLY", "KR_value_selected": False})
    full_sets = []
    for name, region_root in [("Project1998", p), ("RTK-Server", r)]:
        mf = args.source_root / (name + "-files.json")
        tf = args.source_root / (name + "-tree.json")
        inventory = json.loads(mf.read_text())
        tree = json.loads(tf.read_text())
        expected = {x["path"]: x for x in tree["tree"] if x["type"] == "blob"}
        if {x["path"] for x in inventory} != set(expected):
            raise ValueError("Full-source manifest/tree set mismatch")
        verified = 0
        for entry in inventory:
            raw = (region_root / entry["path"]).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if blob != expected[entry["path"]]["sha"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("Full-source manifest byte mismatch: " + entry["path"])
            verified += 1
        full_sets.append({"repository": name, "tree_manifest": tf.name, "tree_manifest_sha256": sha(tf), "byte_manifest": mf.name, "byte_manifest_sha256": sha(mf), "expected_files": len(expected), "files_read_and_git_blob_matched": verified, "bytes": sum(x["bytes"] for x in inventory), "submodules": [x["path"] for x in tree["tree"] if x["type"] == "commit"], "status": "STATIC_FULL_SOURCE_ACQUIRED", "build_restore_run": "NOT_RUN"})
    for domain, rows in records_by_domain.items():
        target = out / f"na_reference_{domain}.jsonl"
        with target.open("w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    # Metadata carries field semantics and all file hashes/consumer anchors once, rather than per value.
    metadata = {"task_id": "BARAM_REBUILD_P1_5_001", "scope": "FULL_PINNED_SOURCE_ACQUISITION_AND_BULK_NA_STATIC_EXTRACTION", "script_sha256": sha(Path(__file__)), "source_commits": {"Project1998": P_SHA, "RTK-Server": R_SHA}, "full_source_sets": full_sets, "counts": dict(sorted(counts.items())), "sources": list(manifests.values()), "dependencies": dependencies, "semantic_findings": semantic_findings, "outputs": [{"path": str(f.relative_to(out)), "sha256": sha(f), "bytes": f.stat().st_size, "records": sum(1 for _ in f.open())} for f in sorted(out.glob("na_reference_*.jsonl"))], "SQL_allowlist": sorted(SQL_TABLES), "SQL_sensitive_tables_excluded": True, "historical_KR_field_selections": 0, "new_game_binding": "NOT_STARTED", "runtime_tests": "NOT_RUN", "diagnostics": diagnostics, "limitations": ["P1998 and RTK are linked source families, never two independent KR sources", "CSV parsing confirms stored values, not that runtime loads/uses every row", "Lua indexes explicitly retain partial semantic decode, not a complete dialogue/craft/skill interpreter", "RTK original SQL is never executed and authentication/save tables are never emitted", "All timings and probability interpretations are source-local NA references, not KR original values"]}
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"counts": metadata["counts"], "outputs": metadata["outputs"], "source_files": len(manifests)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
