#!/usr/bin/env python3
"""Read P1.5 catalogs, source bytes and references without running reference code.

All records are inspected; unknown semantics are BLOCKED/NOT_RUN, never defaults.
Outputs contain IDs/counts and bounded diagnostics, not source content or secrets.
"""
from __future__ import annotations
import argparse
import bisect
import collections
import csv
import functools
from decimal import Decimal, ROUND_FLOOR, InvalidOperation
import hashlib
import importlib.util
import io
import json
import re
import struct
import subprocess
import sys
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
VERSION = "baram-p15-static-import/1.0"
MAX_SOURCE = 768 * 1024 * 1024


def sha(data): return hashlib.sha256(data).hexdigest()
def jsonl(path): return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
def catalog_path(value):
    parts = PurePosixPath(str(value).replace("\\", "/")).parts
    if ".." in parts: raise ValueError("Unsafe catalog path")
    if "selected_content" in parts: parts = parts[parts.index("selected_content") + 1:]
    if not parts or parts[0] == "/": raise ValueError("Catalog path must be relative")
    return PurePosixPath(*parts).as_posix()
def result(values):
    values = set(values)
    return next((x for x in ("FAIL", "BLOCKED", "NOT_RUN") if x in values), "PASS")


class Checks:
    def __init__(self): self.groups = {}; self.fatal_rows = set()
    def add(self, name, status, rid=None, detail=None, axis="integrity"):
        g = self.groups.setdefault((axis, name), {"axis": axis, "check": name, "counts": collections.Counter(), "examples": []})
        g["counts"][status] += 1
        if status != "PASS" and sum(e["result"] == status for e in g["examples"]) < 8:
            g["examples"].append({"id": rid, "result": status, "detail": detail})
        if status == "FAIL" and rid: self.fatal_rows.add(rid)
    def export(self):
        return [dict(g, counts=dict(g["counts"])) for _, g in sorted(self.groups.items())]
    def status(self, axis):
        return result(s for (a, _), g in self.groups.items() if a == axis for s in g["counts"])


class Sources:
    def __init__(self, repo, registry, mapping, server_root, checks):
        self.checks = checks; self.rows = {}; self.cache = {}; self.by_hash = {}; self.member_names = collections.defaultdict(set)
        self.mapping = mapping; self.server_root = server_root
        self.manifests = {}; self.registered_source_ids = set(); self.verified_metadata = set(); self.registry_fingerprints = {}
        base = repo / "docs/rebuild/step01"
        for file in (base / "sources.jsonl", registry / "sources_delta.jsonl"):
            if file.is_file():
                self.registry_fingerprints[str(file)] = sha(file.read_bytes())
                for row in jsonl(file):
                    if row.get("source_id"): self.rows[row["source_id"]] = dict(self.rows.get(row["source_id"], {}), **row)
        for file in sorted(registry.glob("research_*.json")):
            self.registry_fingerprints[str(file)] = sha(file.read_bytes())
            try: obj = json.loads(file.read_text()); self.manifests[file.name] = obj
            except (ValueError, UnicodeError): checks.add("registry_json", "FAIL", file.name); continue
            for key in ("sources", "web_pages", "web_images"):
                for row in obj.get(key, []):
                    if not isinstance(row, dict) or not row.get("source_id"): continue
                    old = self.rows.get(row["source_id"], {})
                    if old.get("sha256") and row.get("sha256") and old["sha256"] != row["sha256"]:
                        checks.add("source_registry_hash_consistency", "FAIL", row["source_id"])
                    self.rows[row["source_id"]] = dict(old, **row)
                    self.registered_source_ids.add(row["source_id"])
        member_file = base / "archive_members.jsonl"
        if member_file.is_file():
            for row in jsonl(member_file):
                h = row.get("sha256"); p = mapping.get(row.get("member_id"))
                if p and h: self.by_hash[h] = Path(p)
                self.member_names[(row["source_id"], row["archive_member"].split("!")[-1])].add(h)
        for sid, p in mapping.items():
            row = self.rows.get(sid)
            if row and row.get("sha256"): self.by_hash[row["sha256"]] = Path(p)
        for sid, row in self.rows.items():
            p = self.path(sid)
            if p and row.get("sha256"): self.by_hash[row["sha256"]] = p

    def path(self, sid):
        row = self.rows.get(sid, {})
        p = self.mapping.get(sid) or row.get("local_private_path") or row.get("local_path") or row.get("local_materialization_path") or row.get("private_local_path")
        if p: return Path(p)
        if row.get("repository") in ("project1998/Project1998", "unkmc/RTK-Server") and row.get("path"):
            name = "Project1998-source" if row["repository"].startswith("project1998/") else "RTK-Server-source"
            return self.server_root / name / row["path"]
        return self.by_hash.get(row.get("sha256"))

    def data(self, h, rid=None):
        if not h or not re.fullmatch(r"[a-f0-9]{64}", str(h)):
            self.checks.add("source_hash_shape", "FAIL", rid); return None
        if h in self.cache: return self.cache[h]
        p = self.by_hash.get(h)
        if not p or not p.is_file():
            self.checks.add("source_bytes", "BLOCKED", rid, "No current exact-hash byte path"); self.cache[h] = None; return None
        if p.is_symlink() or p.stat().st_size > MAX_SOURCE:
            self.checks.add("source_bytes", "BLOCKED", rid, "Source safety bound/symlink"); self.cache[h] = None; return None
        b = p.read_bytes()
        self.checks.add("source_bytes", "PASS" if sha(b) == h else "FAIL", rid)
        self.cache[h] = b if sha(b) == h else None
        return self.cache[h]

    def member(self, sid, name, rid):
        hashes = self.member_names.get((sid, name), set())
        if len(hashes) != 1:
            self.checks.add("asset_member_reference", "BLOCKED", rid, "Missing/ambiguous namespaced member: " + name, axis="references"); return None
        return self.data(next(iter(hashes)), rid)

    def source(self, sid, rid):
        s = self.rows.get(sid)
        if not s:
            self.checks.add("source_id_reference", "FAIL", rid, sid); return None, None
        self.checks.add("source_id_reference", "PASS", rid)
        b = self.data(s.get("sha256"), sid) if s.get("sha256") else None
        if not s.get("sha256"): self.checks.add("source_bytes", "BLOCKED", rid, "Source byte hash not acquired")
        if b is not None and sid not in self.verified_metadata:
            self.verified_metadata.add(sid)
            length = s.get("bytes", s.get("size_bytes", s.get("byte_length")))
            self.checks.add("source_declared_length", "PASS" if length is None or length == len(b) else "FAIL", sid)
            if s.get("git_blob_sha"):
                actual = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
                self.checks.add("source_git_blob_identity", "PASS" if actual == s["git_blob_sha"] else "FAIL", sid)
        return s, b


@functools.lru_cache(maxsize=1024)
def decode(data):
    for enc in ("utf-8-sig", "cp949", "utf-16"):
        try: return data.decode(enc)
        except UnicodeError: continue
    raise UnicodeError("No supported strict encoding")


@functools.lru_cache(maxsize=1024)
def source_lines(data):
    return decode(data).splitlines()


def line_check(checks, data, loc, rid, name="source_locator"):
    if data is None: return
    try:
        n = len(source_lines(data))
        first = loc.get("line_start", loc.get("line")); last = loc.get("line_end", first)
        okay = isinstance(first, int) and isinstance(last, int) and 1 <= first <= last <= n
        checks.add(name, "PASS" if okay else "FAIL", rid, {"line_start": first, "line_end": last, "source_lines": n})
    except UnicodeError: checks.add(name, "BLOCKED", rid, "Source strict text decoding unavailable")


def csv_index(data):
    raw = source_lines(data); filtered = [(n, s) for n, s in enumerate(raw, 1) if s.strip() and not s.lstrip().startswith("#")]
    if not filtered: return {}
    reader = csv.reader([s for _, s in filtered], strict=True); head = next(reader); previous = reader.line_num; rows = {}
    for values in reader:
        first = filtered[previous][0]; last = filtered[reader.line_num - 1][0]; previous = reader.line_num
        if len(values) > len(head): raise ValueError("CSV width exceeds header")
        rows[first] = (last, dict(zip(head, values)), head[len(values):])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=ROOT)
    ap.add_argument("--registry-dir", type=Path)
    ap.add_argument("--content-dir", type=Path)
    ap.add_argument("--input-map", type=Path, required=True)
    ap.add_argument("--catalog-manifest", type=Path, help="Frozen manifest with normalized_catalogs:[path,sha256,bytes,records]")
    ap.add_argument("--server-root", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args(); repo = a.repo.resolve(); registry = a.registry_dir or repo / "docs/rebuild/p1_5"; content = a.content_dir or registry / "selected_content"
    server_root = a.server_root or repo.parent / "research/server"
    checks = Checks(); mapping = json.loads(a.input_map.read_text()); sources = Sources(repo, registry, mapping, server_root, checks)
    rows = []; files = []; ids = {}; csv_cache = {}; sql_newlines = {}; domains = collections.Counter(); source_usage = collections.Counter()
    output_expected = {}; frozen_catalogs = set()
    for manifest in sources.manifests.values():
        for item in manifest.get("outputs", []) + manifest.get("private_selected_content_files", []):
            if isinstance(item, dict) and item.get("path"): output_expected[catalog_path(item["path"])] = item
    if a.catalog_manifest:
        try:
            declared = json.loads(a.catalog_manifest.read_text()).get("normalized_catalogs")
            if not isinstance(declared, list) or not declared: checks.add("frozen_catalog_declaration", "FAIL", detail="Missing nonempty normalized_catalogs list")
            else:
                for item in declared:
                    if not isinstance(item, dict) or not item.get("path"): checks.add("frozen_catalog_declaration", "FAIL"); continue
                    name = catalog_path(item["path"]); output_expected[name] = item; frozen_catalogs.add(name)
        except OSError: checks.add("frozen_catalog_declaration", "BLOCKED", detail="Manifest not accessible")
    # Earlier reports declare record counts before their output-hash descriptors.
    # These named contracts remain mandatory rather than disappearing from scope.
    for report_name, file_name in (("research_korean.json", "kr_documented_fields.jsonl"), ("research_official_core.json", "kr_official_core.jsonl")):
        report = sources.manifests.get(report_name)
        if report and isinstance(report.get("records"), int): output_expected.setdefault(file_name, {"path": file_name, "records": report["records"]})
    if "research_server.json" in sources.manifests: output_expected.setdefault("save_contracts.json", {"path": "save_contracts.json"})
    selected_files = sorted(content.rglob("*.jsonl")) + sorted(content.rglob("*.json"))
    checks.add("content_input_set", "PASS" if selected_files else "BLOCKED", detail={"files": len(selected_files)})
    present_names = {p.relative_to(content).as_posix() for p in selected_files}
    for missing in sorted(set(output_expected) - present_names):
        checks.add("required_catalog_input", "BLOCKED", missing)
    for path in selected_files:
        try:
            data = path.read_bytes(); obj = jsonl(path) if path.suffix == ".jsonl" else json.loads(data)
        except (ValueError, UnicodeError, OSError) as e:
            checks.add("content_parse", "FAIL", path.name, type(e).__name__); continue
        if isinstance(obj, list): catalog = obj
        elif isinstance(obj, dict) and isinstance(obj.get("contracts"), list):
            catalog = obj["contracts"]
            for sid, ref in [(s["source_id"], s) for s in obj.get("source_refs", {}).values()]:
                source, b = sources.source(sid, path.name)
                checks.add("save_reference_hash", "PASS" if source and ref.get("sha256") == source.get("sha256") else "FAIL", sid)
            checks.add("save_runtime_contract", "NOT_RUN", path.name, "P2/native save, IME and real authentication not executed", axis="semantics")
        elif isinstance(obj, dict) and isinstance(obj.get("private_data_files"), list):
            catalog = []
            for item in obj["private_data_files"]:
                checks.add("catalog_private_payload", "PASS" if catalog_path(item["path"]) in present_names else "BLOCKED", item["path"], axis="references")
        elif isinstance(obj, dict) and (obj.get("private_file_id") or obj.get("library_file_id") or obj.get("private_path")):
            catalog = []; checks.add("catalog_private_payload", "BLOCKED", path.name, "Use --content-dir containing actual payload", axis="references")
        else:
            catalog = [obj] if isinstance(obj, dict) and any(k in obj for k in ("id", "record_id", "content_id")) else []
            if not catalog: checks.add("unknown_catalog_schema", "NOT_RUN", path.name, axis="references")
        meta = output_expected.get(path.relative_to(content).as_posix())
        if meta:
            checks.add("normalized_catalog_hash", "PASS" if (not meta.get("sha256") or meta["sha256"] == sha(data)) and meta.get("records", meta.get("rows", len(catalog))) == len(catalog) and meta.get("bytes", len(data)) == len(data) else "FAIL", path.name)
        files.append({"file": path.name, "rows": len(catalog), "sha256": sha(data), "bytes": len(data)})
        if a.catalog_manifest and (catalog or path.suffix == ".jsonl"):
            checks.add("frozen_catalog_set", "PASS" if path.relative_to(content).as_posix() in frozen_catalogs else "FAIL", path.relative_to(content).as_posix(), "All normalized row-bearing inputs must be declared")
        for row in catalog:
            if not isinstance(row, dict): checks.add("row_shape", "FAIL", path.name); continue
            rid = row.get("id") or row.get("record_id") or row.get("content_id")
            if not isinstance(rid, str) or not rid:
                checks.add("row_identity", "FAIL", path.name); continue
            checks.add("row_identity", "PASS" if rid not in ids else "FAIL", rid, "Duplicate stable record ID" if rid in ids else None)
            ids[rid] = row; rows.append((path.name, rid, row)); domains[path.stem] += 1
            fact = row.get("fact_status", row.get("historical_fact_status"))
            checks.add("row_provenance_axis", "PASS" if fact in ("ORIGINAL_VERIFIED", "CORROBORATED_RECONSTRUCTION", "INFERRED", "UNKNOWN") else "FAIL", rid)
            bindings = [row[k] for k in ("new_runtime_binding", "runtime_binding") if row.get(k) is not None]
            runtime_claims = [row[k] for k in ("test_status", "test_result", "game_output_test", "game_render_test", "runtime_test_status") if row.get(k) is not None]
            checks.add("no_unexecuted_runtime_promotion", "PASS" if all(v == "NOT_STARTED" for v in bindings) and all(v == "NOT_RUN" for v in runtime_claims) else "FAIL", rid)
            if row.get("game_region") == "NA":
                checks.add("no_NA_to_KR_selection", "PASS" if not row.get("selected_for_build") and row.get("KR_selected_value") is None else "FAIL", rid)
            if row.get("selected_for_build"):
                scoped = isinstance(row.get("build_profile_id"), str) and bool(row["build_profile_id"]) and row.get("require_profile_dispatch") is True and row.get("global_default_selected") is False and row.get("selected_original_value") is not None
                checks.add("selected_profile_dispatch_contract", "PASS" if scoped else "FAIL", rid)
            embedded = row.get("source") if isinstance(row.get("source"), dict) else None
            sids = row.get("source_ids") or ([row["source_id"]] if row.get("source_id") else [embedded.get("source_id")] if embedded else [])
            checks.add("row_source_set", "PASS" if sids and all(isinstance(s, str) for s in sids) else "FAIL", rid)
            if row.get("input_sha256"):
                checks.add("row_input_hash", "PASS" if any(sources.rows.get(sid, {}).get("sha256") == row["input_sha256"] for sid in sids) else "FAIL", rid)
            for sid in sids:
                source_usage[sid] += 1; source, source_data = sources.source(sid, rid)
                if not source: continue
                loc = row.get("source_location") or row.get("source_locator")
                if isinstance(loc, dict):
                    loc = dict(loc)
                    if loc.get("html_line_start") is not None: loc.setdefault("line_start", loc["html_line_start"])
                    if loc.get("archive_url"): loc.setdefault("url", loc["archive_url"])
                    if loc.get("final_response_url"): loc.setdefault("url", loc["final_response_url"])
                    if loc.get("service_table"): loc.setdefault("table", loc["service_table"])
                    if loc.get("screenshot_archive_url"): loc.setdefault("image_archive_url", loc["screenshot_archive_url"])
                    primary_locator_source = len(sids) == 1 or source.get("sha256") == row.get("input_sha256")
                    if primary_locator_source and (loc.get("line_start") is not None or loc.get("line") is not None):
                        line_check(checks, source_data, loc, rid)
                    if loc.get("url") and primary_locator_source:
                        checks.add("source_locator_url", "PASS" if loc["url"] in (source.get("url"), source.get("source_path_or_url"), source.get("final_response_url"), source.get("original_url")) else "FAIL", rid)
                    elif loc.get("table") and isinstance(loc["table"], dict):
                        # HTML table and its image are two independently hashed
                        # inputs; only the HTML source owns HTML line numbers.
                        table_loc = loc["table"]
                        urls = {source.get("url"), source.get("source_path_or_url"), source.get("final_response_url"), source.get("original_url")}
                        declared_urls = [table_loc[k] for k in ("final_response_url", "original_url") if table_loc.get(k)]
                        table_matches = any(url in urls for url in declared_urls)
                        if table_matches:
                            checks.add("table_source_url_locator", "PASS" if declared_urls and all(url in urls for url in declared_urls) else "FAIL", rid)
                            first = table_loc.get("html_line_start")
                            line_check(checks, source_data, {"line_start":first,"line_end":first}, rid, "table_image_html_locator")
                            if loc.get("image_html_line") is not None:
                                line_check(checks, source_data, {"line":loc["image_html_line"]}, rid, "table_image_html_locator")
                        image_url = loc.get("image_archive_url")
                        if image_url and not table_matches:
                            checks.add("table_image_url_locator", "PASS" if image_url in urls else "FAIL", rid)
                    elif loc.get("line_start") is None and loc.get("line") is None:
                        checks.add("source_locator_unsupported", "NOT_RUN", rid, "Locator has neither line nor URL", axis="references")
                if row.get("kind") == "source_row" and source_data is not None:
                    try:
                        if sid not in csv_cache: csv_cache[sid] = csv_index(source_data)
                        expected = csv_cache[sid].get((loc or {}).get("line_start"))
                        okay = expected is not None and expected[1] == row.get("original_value") and expected[2] == row.get("source_shape_missing_columns", [])
                        checks.add("csv_row_exact_original_and_absence", "PASS" if okay else "FAIL", rid)
                    except (ValueError, UnicodeError, csv.Error) as e: checks.add("csv_row_exact_original_and_absence", "FAIL", rid, type(e).__name__)
                if row.get("kind", "").startswith("sql_content:") and source_data is not None:
                    text = decode(source_data); offset = (loc or {}).get("character_offset")
                    if sid not in sql_newlines: sql_newlines[sid] = [i for i, c in enumerate(text) if c == "\n"]
                    okay = isinstance(offset, int) and 0 <= offset < len(text) and text[offset] == "(" and bisect.bisect_left(sql_newlines[sid], offset) + 1 == loc.get("line_start")
                    checks.add("sql_tuple_locator_bounds", "PASS" if okay else "FAIL", rid)
                for call in row.get("original_value", {}).get("call_sites", []) if isinstance(row.get("original_value"), dict) else []:
                    if source_data is not None:
                        lines = source_lines(source_data); ln = call.get("line")
                        checks.add("script_call_literal_anchor", "PASS" if isinstance(ln, int) and 1 <= ln <= len(lines) and call.get("source_text", "").strip() == lines[ln-1].strip() else "FAIL", rid)
            if embedded:
                if embedded.get("parser_sha256"):
                    parser_file = repo / "tools/rebuild/p1_5/inspect_kr_tables.py"
                    checks.add("asset_parser_code_fingerprint", "PASS" if parser_file.is_file() and sha(parser_file.read_bytes()) == embedded["parser_sha256"] else "FAIL", rid)
                if embedded.get("reader_sha256"): sources.data(embedded["reader_sha256"], rid)
                mb = sources.data(embedded.get("member_sha256"), rid); cb = sources.data(embedded.get("container_sha256"), rid)
                off = embedded.get("member_byte_offset")
                if mb is not None and cb is not None:
                    okay = isinstance(off, int) and 0 <= off <= len(cb) - len(mb) and cb[off:off+len(mb)] == mb
                    checks.add("asset_member_container_slice", "PASS" if okay else "FAIL", rid)
                if embedded.get("line") is not None: line_check(checks, mb, {"line": embedded["line"]}, rid, "asset_text_line_bounds")
                if embedded.get("dat_byte_offset") is not None:
                    relative = embedded.get("line_byte_offset")
                    okay = isinstance(off, int) and (embedded["dat_byte_offset"] == off if relative is None else embedded["dat_byte_offset"] == off + relative)
                    checks.add("asset_relative_absolute_offset", "PASS" if okay else "FAIL", rid)
            if row.get("kind") == "static_script_index": checks.add("script_command_semantics", "BLOCKED", rid, "Lexical calls/branch anchors are not a decoded executable dialogue/craft/spell graph", axis="semantics")
            if row.get("source_shape_missing_columns"): checks.add("source_absent_fields", "BLOCKED", rid, row["source_shape_missing_columns"], axis="semantics")
            if row.get("unknown_fields") or row.get("missing_information"): checks.add("declared_field_gaps", "BLOCKED", rid, "Preserved explicit unresolved fields", axis="semantics")
    checks.add("nonempty_catalog_records", "PASS" if rows else "BLOCKED", detail={"rows_read": len(rows)})
    # Every registered consuming-source anchor must exist and name real lines.
    for sid in sorted(sources.registered_source_ids):
        if sources.rows[sid].get("sha256"): sources.source(sid, sid)
    for sid in sorted(source_usage):
        source = sources.rows.get(sid, {})
        for anchor in source.get("consumer_anchors", []):
            target, b = sources.source(anchor.get("source_id"), sid)
            if target: line_check(checks, b, anchor, sid, "consumer_source_line_bounds")
    for manifest in sources.manifests.values():
        for finding in manifest.get("semantic_findings", []):
            anchor = finding.get("evidence", {})
            target, b = sources.source(anchor.get("source_id"), finding.get("finding_id"))
            if target: line_check(checks, b, anchor, finding.get("finding_id"), "consumer_semantic_evidence_bounds")
    table = collections.defaultdict(list)
    for file, rid, row in rows:
        source = sources.rows.get(row.get("source_id"), {}); ns = source.get("repository")
        if row.get("kind") == "source_row": name = Path(source.get("path", "")).stem
        elif row.get("kind", "").startswith("sql_content:"): name = row["kind"].split(":", 1)[1]
        else: continue
        table[(ns, name)].append((rid, row["original_value"]))
    def pool(ns, names, keys):
        return {value[k] for name in names for _, value in table[(ns, name)] for k in keys if k in value and value[k] is not None}
    def link(rid, value, target, relation, sentinels=()):
        if value in sentinels: checks.add(relation + ":documented_sentinel", "PASS", rid, axis="references")
        elif value is None or value == "": checks.add(relation, "BLOCKED", rid, "Absent source value preserved", axis="references")
        elif not target: checks.add(relation + ":target_pool_absent", "BLOCKED", rid, "Target pool not included in this source namespace; not proof of an invalid original ID", axis="references")
        else: checks.add(relation, "PASS" if value in target else "FAIL", rid, "FAIL_IN_SOURCE_REFERENCE_GRAPH; preserved source value is absent from known source-local target pool" if value not in target else None, axis="references")
    for ns in ("project1998/Project1998", "unkmc/RTK-Server"):
        mobs = pool(ns, ("mobs", "Mobs"), ("Identifier", "MobIdentifier")); mobids = pool(ns, ("mobs", "Mobs"), ("MobId",))
        items = pool(ns, ("Items",), ("ItmIdentifier",)); itemids = pool(ns, ("Items",), ("ItmId",))
        npcs = pool(ns, ("NPCs", "NPCs0"), ("NpcIdentifier",)); npcids = pool(ns, ("NPCs", "NPCs0"), ("NpcId",))
        spells = pool(ns, ("Spells",), ("SplIdentifier",)); paths = pool(ns, ("Paths",), ("PthId",)); maps = pool(ns, ("Maps",), ("MapId",))
        for (namespace, name), values in list(table.items()):
            if namespace != ns: continue
            for rid, v in values:
                if name in ("Spawns", "Spawns0", "Spawns1"):
                    link(rid, v.get("SpnMobId"), mobids, "spawn_to_monster")
                    link(rid, v.get("SpnMapId"), maps, "spawn_to_map")
                if name.startswith("AreaSpawns"): link(rid, v.get("MobId"), mobids, "area_spawn_to_monster")
                if name in ("NPCEquipment", "NPCEquipment0"): link(rid, v.get("NeqNpcId"), npcids, "equipment_to_npc")
                if name in ("NPCs", "NPCs0"): link(rid, v.get("NpcMapId"), maps, "npc_to_map")
                if name in ("NPCs", "NPCs0"):
                    checks.add("npc_graphic_dialogue_service_chain", "BLOCKED", rid, "Namespaced appearance IDs/flags exist; full render/dialogue/service semantics not executed", axis="semantics")
                if name == "Spells": link(rid, v.get("SplPthId"), paths, "skill_to_job", ("99",) if ns == "project1998/Project1998" else ())
                if name == "Warps":
                    for key in ("SourceMapId", "DestinationMapId"): link(rid, v.get(key), maps, "warp_to_map")
                if name in ("ShopStock", "ShopBuysFrom", "ShopCatalogues"):
                    link(rid, v.get("NpcIdentifier", v.get("NpcKey")), npcs, "shop_to_npc")
                    for item in v.get("ItemKeys", "").split("|"): link(rid, item, items, "shop_to_item", ("", "-"))
                if name == "SpellLearnCosts":
                    link(rid, v.get("key"), spells, "learning_to_skill"); link(rid, v.get("pathId"), paths, "learning_to_job")
                    for key in ("item1", "item2", "item3", "item4"): link(rid, v.get(key), items, "learning_to_item", (None, ""))
                if name == "ItemSets":
                    link(rid, v.get("ItmSetId"), itemids, "recipe_to_result")
                    for index in range(1, 6):
                        item, amount = v.get("ItmSetItem"+str(index)), v.get("ItmSetItem"+str(index)+"Amount")
                        if item == "0" and amount == "0": checks.add("recipe_explicit_empty_pair", "PASS", rid, axis="references")
                        else: link(rid, item, itemids, "recipe_to_material")
                    checks.add("recipe_to_npc_conditions", "BLOCKED", rid, "SQL item-set list alone lacks NPC/conditions/success/failure semantics", axis="semantics")
                if name == "MobDrops":
                    link(rid, v.get("MobKey"), mobs, "csv_drop_to_monster")
                    for key in ("Loot", "RareLoot"):
                        for literal in v.get(key, "").split("|"):
                            if not literal: continue
                            pieces = literal.split(":")
                            link(rid, pieces[0], items, "csv_drop_to_item", ("GOLD",))
                            try:
                                # Source Loot uses item:max:rate; RareLoot uses
                                # item:rate with source-defined exact-one output.
                                okay = (len(pieces) == 3 and key == "Loot" and 0 <= Decimal(pieces[2]) <= 100 and Decimal(pieces[1]) >= 0) or (len(pieces) == 2 and key == "RareLoot" and 0 <= Decimal(pieces[1]) <= 100)
                                checks.add("csv_drop_literal_bounds", "PASS" if okay else "FAIL", rid)
                            except InvalidOperation: checks.add("csv_drop_literal_bounds", "BLOCKED", rid, "Nonliteral source drop token", axis="semantics")
                if name == "Maps": checks.add("map_geometry_tile_object_chain", "BLOCKED", rid, "SQL map metadata is not source tile/object/collision decoding", axis="semantics")
        for file, rid, row in rows:
            source = sources.rows.get(row.get("source_id"), {})
            if source.get("repository") != ns or row.get("kind") != "literal_drop_table": continue
            ov = row["original_value"]
            # This exact pinned consumer also contains five computed loot pools.
            # Their keys are not mob foreign keys. Do not infer this convention
            # for another repository/version or exempt arbitrary missing IDs.
            pool_selector = (ns == "unkmc/RTK-Server"
                             and source.get("commit") == "e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6"
                             and source.get("path") == "rtklua/Accepted/Mobs/MobDrops.lua"
                             and source.get("sha256") == "95dcd0d2761b8507e2bf103d601ec76932a7025f0ec7496e120aab7fa80b965b"
                             and re.fullmatch(r"nagnag_armory_[0-4]", str(ov.get("mob_key")))
                             and sources.data(source["sha256"], rid) is not None)
            if pool_selector:
                checks.add("drop_pool_selector:consumer_proved", "PASS", rid,
                           {"source_id": row.get("source_id"), "sha256": source["sha256"],
                            "consumer_lines": [[3517, 3554], [3636, 3648]],
                            "meaning": "map-conditioned loot pool selected by _getNanagMercenaryLoot; not a mob ID"}, axis="references")
            else: link(rid, ov.get("mob_key"), mobs, "drop_to_monster")
            for group_name, group in ov.get("tables", {}).items():
                for entry in group:
                    if entry.get("item_key") is not None: link(rid, entry["item_key"], items, "drop_to_item")
                    try:
                        percent = Decimal(entry["rate_percent_literal"]); threshold = int((percent * 1000).to_integral_value(rounding=ROUND_FLOOR))
                        semantics = "roll_all_then_first_success_in_source_order" if group_name == "rareLoot" else "independent_each_line"
                        okay = 0 <= percent <= 100 and entry.get("rng_integer_min") == 1 and entry.get("rng_integer_max") == 100000 and entry.get("pass_threshold") == threshold and entry.get("selection_semantics") == semantics
                        checks.add("drop_probability_contract:" + semantics, "PASS" if okay else "FAIL", rid)
                    except (InvalidOperation, TypeError, KeyError): checks.add("drop_probability_contract", "BLOCKED", rid, "Unresolved literal probability", axis="semantics")
            if ov.get("global_drop_conditions_not_flattened"): checks.add("drop_global_conditions", "BLOCKED", rid, "Additional source-global drops remain separate", axis="semantics")
    # KR assets never resolve NA numeric effects by accidental ID equality.
    effect_frames = {row["original_value"]["frame_index"] for _, _, row in rows if row.get("kind") == "effect_frame_palette"}
    effect_pal = sources.member("LIB-010", "Effect.pal", "KR491:effect_palette") if effect_frames else None
    effect_palette_count = (1 if effect_pal.startswith(b"DLPalette") else struct.unpack_from("<I", effect_pal)[0]) if effect_pal else None
    soundids = {rid for _, rid, row in rows if row.get("kind") == "sound_metadata"}
    effect_helper = None
    if any(row.get("record_type") == "skill_effect" for _, _, row in rows):
        path = repo / "tools/rebuild/p1_5/extract_official_skill_effects.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location("p15_effect_source_locator", path)
            effect_helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(effect_helper)
    for file, rid, row in rows:
        ov = row.get("original_value"); embedded = row.get("source", {}); kind = row.get("kind")
        if isinstance(ov, dict):
            for key, value in ov.items():
                if (key.endswith("_record_id") or key.endswith("_row_id")) and isinstance(value, str) and value.startswith(("KRO-", "KRF-", "KR491:", "NA-")):
                    checks.add("normalized_record_reference", "PASS" if value in ids else "FAIL", rid, {"field": key}, axis="references")
            parent_id = row.get("parent_content_id")
            if parent_id: checks.add("normalized_parent_reference", "PASS" if parent_id in ids else "FAIL", rid, axis="references")
        if row.get("epf_member") and isinstance(ov, dict):
            epf = sources.member(embedded.get("source_id"), row["epf_member"], rid); pal = sources.member(embedded.get("source_id"), row["palette_member"], rid)
            if epf is not None and pal is not None:
                try:
                    count = struct.unpack_from("<h", epf)[0]; palettes = 1 if pal.startswith(b"DLPalette") else struct.unpack_from("<I", pal)[0]
                    frame = ov.get("Starting", ov.get("ID")); palette = ov.get("Palette")
                    checks.add("asset_frame_palette_bounds", "PASS" if isinstance(frame, int) and 0 <= frame < count and isinstance(palette, int) and 0 <= palette < palettes else "FAIL", rid)
                except struct.error: checks.add("asset_frame_palette_bounds", "FAIL", rid)
        if kind == "effect_sequence":
            for frame in row.get("front_frames", []) + row.get("back_frames", []):
                index = frame.get("frame_index"); palette = frame.get("palette_index")
                okay = index == -1 and palette is None or isinstance(index, int) and index in effect_frames and isinstance(palette, int) and effect_palette_count is not None and 0 <= palette < effect_palette_count
                checks.add("effect_frame_palette_reference", "PASS" if okay else "FAIL", rid)
                if frame.get("unsupported_semantics"): checks.add("effect_unsupported_row", "BLOCKED", rid, "Retained raw unsupported effect semantics", axis="semantics")
            for key in ("delay_unit", "alpha_interpretation", "light_interpretation", "repeat_sentinel_semantics"):
                if row.get(key) in (None, "UNKNOWN") or str(row.get(key)).startswith("UNKNOWN"): checks.add("effect_timing_layer_semantics", "BLOCKED", rid, key, axis="semantics")
            if row.get("spell_id") is None or row.get("sound_id") is None: checks.add("skill_effect_sound_chain", "BLOCKED", rid, "Korean skill/effect/sound binding absent", axis="semantics")
        if kind == "sound_metadata":
            b = sources.data(embedded.get("member_sha256"), rid)
            if b is not None:
                try:
                    with wave.open(io.BytesIO(b)) as wav:
                        actual = (wav.getnchannels(), wav.getframerate(), wav.getsampwidth(), wav.getnframes())
                        expected = (ov.get("channels"), ov.get("sample_rate_hz"), ov.get("sample_width_bytes"), ov.get("frame_count"))
                        checks.add("wav_metadata_exact", "PASS" if actual == expected else "FAIL", rid)
                except wave.Error: checks.add("wav_metadata_exact", "FAIL", rid)
            for target in row.get("same_wav_ids", []): link(rid, target, soundids, "sound_alias_id_preserved")
        if kind == "sprite_family":
            for error in row.get("decode_errors", []): checks.add("sprite_stencil_decode", "BLOCKED", rid, {"frame_index": error.get("frame_index"), "reason": error.get("reason")}, axis="semantics")
        if kind in ("draw_order", "monster_frame_group"):
            checks.add("motion_layer_direction_semantics", "BLOCKED", rid, "Raw order/counts do not identify runtime directions/timing/layers", axis="semantics")
        if kind == "guide_effect_bitmap_binding":
            image_id = ov.get("guide_image_source_id")
            image_source = sources.rows.get(image_id, {})
            checks.add("guide_image_input_hash", "PASS" if image_source.get("sha256") == ov.get("guide_image_sha256") and image_id in row.get("source_ids", []) else "FAIL", rid)
            guide_id = ov.get("guide_row_id")
            checks.add("guide_named_row_reference", "PASS" if guide_id in ids else "FAIL", rid)
            sequence_id = ov.get("effect_sequence_id")
            if sequence_id is not None:
                checks.add("guide_to_effect_sequence_reference", "PASS" if sequence_id in ids and ids[sequence_id].get("kind") == "effect_sequence" and ov.get("matched_full_sequence_count") == 1 else "FAIL", rid, axis="references")
            else:
                checks.add("guide_to_effect_sequence_reference", "BLOCKED", rid, "No unique exact full-sequence bitmap match", axis="references")
            checks.add("named_effect_sound_timing_chain", "BLOCKED", rid, "Bitmap identity does not establish invocation position, delay, sound or hit event", axis="semantics")
        if isinstance(ov, dict) and ov.get("image_source_id"):
            image_id = ov["image_source_id"]; image_source = sources.rows.get(image_id, {})
            checks.add("named_image_hash_binding", "PASS" if image_source.get("sha256") == ov.get("image_sha256") and image_id in row.get("source_ids", []) else "FAIL", rid)
            for key in ("item_record_id", "map_record_id"):
                if ov.get(key): checks.add("named_image_entity_reference", "PASS" if ov[key] in ids else "FAIL", rid)
        if isinstance(ov, dict) and ov.get("acquired_asset_source_id"):
            image_id = ov["acquired_asset_source_id"]; ref = sources.rows.get(image_id, {})
            checks.add("attachment_image_hash_binding", "PASS" if ref.get("sha256") == ov.get("byte_sha256") and image_id in row.get("source_ids", []) else "FAIL", rid)
        if row.get("record_type") == "official_full_map_image":
            archive = sources.data(row.get("input_sha256"), rid)
            if archive is not None:
                try:
                    with zipfile.ZipFile(io.BytesIO(archive)) as z:
                        info = z.getinfo(ov["archive_member_raw_cp437"])
                        if info.file_size > MAX_SOURCE: raise ValueError("Map member resource bound")
                        member = z.read(info)
                    checks.add("official_map_zip_member_hash_crc", "PASS" if len(member) == ov["archive_member_size_bytes"] and sha(member) == ov["archive_member_sha256"] else "FAIL", rid)
                except (zipfile.BadZipFile, KeyError, RuntimeError, ValueError): checks.add("official_map_zip_member_hash_crc", "FAIL", rid)
        if row.get("record_type") == "npc_appearance_reference":
            source_id = ov.get("screenshot_source_id"); ref = sources.rows.get(source_id, {})
            checks.add("npc_screenshot_hash_binding", "PASS" if ref.get("sha256") == ov.get("screenshot_sha256") and source_id in row.get("source_ids", []) else "FAIL", rid)
            bbox, dimensions = ov.get("npc_pixel_bbox_xyxy_exclusive"), ov.get("screenshot_dimensions")
            okay = isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(v, int) for v in bbox) and isinstance(dimensions, list) and len(dimensions) == 2 and 0 <= bbox[0] < bbox[2] <= dimensions[0] and 0 <= bbox[1] < bbox[3] <= dimensions[1]
            checks.add("npc_source_bbox_bounds", "PASS" if okay else "FAIL", rid)
        if row.get("record_type") == "skill_effect":
            helper_path = repo / "tools/rebuild/p1_5/extract_official_skill_effects.py"
            helper_match = effect_helper is not None and row.get("parser_sha256") == sha(helper_path.read_bytes())
            checks.add("skill_effect_parser_code_fingerprint", "PASS" if helper_match else "FAIL", rid)
            core_hashes = [f["sha256"] for f in files if f["file"] == "kr_official_core.jsonl"]
            checks.add("skill_effect_parent_corpus_fingerprint", "PASS" if len(core_hashes) == 1 and row.get("parent_core_sha256") == core_hashes[0] else "FAIL", rid)
            parent = ids.get(row.get("parent_content_id"))
            if helper_match and parent:
                try:
                    sid = row["source_ids"][0]; source = dict(sources.rows[sid], local_private_path=str(sources.path(sid)))
                    description, locator = effect_helper.get_description(parent, source)
                    checks.add("skill_effect_cell_identity", "PASS" if locator == row["source_locator"]["effect_cell"] and sha(description.encode()) == ov.get("source_description_sha256") else "FAIL", rid)
                    chosen = row.get("selected_original_value") or {}
                    published = {}
                    for fact in ov.get("published_effect_facts", []):
                        first, last = fact.get("description_char_start"), fact.get("description_char_end")
                        okay = isinstance(first, int) and isinstance(last, int) and 0 <= first < last <= len(description) and sha(description[first:last].encode()) == fact.get("evidence_fragment_sha256")
                        checks.add("skill_effect_published_fragment", "PASS" if okay else "FAIL", rid)
                        key = fact.get("field_path", "").removeprefix("skill.effect."); published[key] = fact.get("value")
                    checks.add("skill_effect_selected_field_contract", "PASS" if chosen == published else "FAIL", rid)
                except (ValueError, KeyError, TypeError, OSError) as e:
                    checks.add("skill_effect_cell_identity", "FAIL", rid, type(e).__name__)
        if row.get("record_type") in ("skills", "dialogue", "map_locations", "repair", "items", "shop", "creation", "jobs", "transport", "quest"):
            checks.add("korean_entity_and_chain_binding", "BLOCKED", rid, "Document names/functions are not complete stable entity/asset/NPC/map chains", axis="semantics")
    # Emit explicit whole-chain readiness without inventing targets or defaults.
    for name, expected_hash in sources.registry_fingerprints.items():
        path = Path(name)
        checks.add("registry_unchanged_during_read", "PASS" if path.is_file() and sha(path.read_bytes()) == expected_hash else "FAIL", path.name)
    chains = {"NPC→graphic/dialogue/service": "BLOCKED", "monster→spawn/drop/item": "BLOCKED", "recipe→materials/result/NPC": "BLOCKED", "skill→job/effect/sound": "BLOCKED", "map→tile/object/exits": "BLOCKED"}
    integrity = checks.status("integrity"); refs = checks.status("references"); semantics = checks.status("semantics")
    overall = result((integrity, refs, semantics))
    output = {"task_id": "BARAM_REBUILD_P1_5_001", "executed_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable]+sys.argv,
              "validator_version": VERSION, "validator_sha256": sha(Path(__file__).read_bytes()), "result": overall, "integrity_result": integrity, "source_reference_result": refs,
              "semantic_readiness_result": semantics, "files_read": len(files), "rows_read": len(rows), "unique_record_ids": len(ids), "sources_referenced": len(source_usage),
              "source_byte_hashes_read": sum(b is not None for b in sources.cache.values()), "records_by_file": dict(domains), "files": files, "checks": checks.export(), "korean_complete_chains": chains,
              "source_registry_fingerprints": {Path(path).name: h for path, h in sources.registry_fingerprints.items()},
              "historical_accuracy": "UNKNOWN", "runtime_tests": "NOT_RUN", "p2_tests": "NOT_RUN", "zero_defaults_inserted": 0,
              "scope": "ALL INPUT ROWS: STATIC SCHEMA/SOURCE-HASH/LOCATOR/DECLARED REFERENCE DRY-RUN; no reference/game code, SQL or Lua execution",
              "limitations": ["NA and KR numeric IDs never auto-joined", "Known-pool dangling source references FAIL; absent/unknown target pools remain BLOCKED", "Opaque scripts and unspecified field semantics are not execution support", "SQL typed values use fixed-parser extraction evidence plus exact normalized hashes and tuple locators; no SQL engine execution", "Whole Korean gameplay chains remain blocked independently from source-byte integrity"]}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:output[k] for k in ("result", "integrity_result", "source_reference_result", "semantic_readiness_result", "files_read", "rows_read", "unique_record_ids", "source_byte_hashes_read")}))
    return {"PASS":0,"FAIL":1,"BLOCKED":2,"NOT_RUN":3}[overall]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, OSError, struct.error) as error:
        # Invalid structured data must leave machine-readable evidence, not an
        # old successful report. Never echo source values from exception text.
        status = "BLOCKED" if isinstance(error, FileNotFoundError) else "FAIL"
        evidence = {"task_id":"BARAM_REBUILD_P1_5_001", "result":status, "integrity_result":status,
                    "error_type":type(error).__name__, "scope":"STRUCTURED_INPUT_LOAD_OR_SCHEMA_ERROR", "runtime_tests":"NOT_RUN", "p2_tests":"NOT_RUN", "zero_defaults_inserted":0}
        if "--output" in sys.argv:
            target = Path(sys.argv[sys.argv.index("--output")+1]); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(evidence, indent=2)+"\n")
        print(json.dumps(evidence)); sys.exit(2 if status == "BLOCKED" else 1)
