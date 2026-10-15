#!/usr/bin/env python3
"""Fail-closed static P0/P1 integrity gate. Never validates gameplay/history.

Default expected byte IDs come from the complete ledgers, NOT from paths that
happen to exist. Private relocation map: {input_id: local_path}. Historical
step01/VALIDATION.json is never overwritten. See --help for isolated contracts.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import stat
import struct
import sys
import wave
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VERSION = "baram-static-validation/2.0"
PARSER_VERSION = "baram-static-integrity-reader/2.0"
ROOT = Path(__file__).resolve().parents[3]
MAX_FILE = 768 * 1024 * 1024
MAX_ZIP_TOTAL = 2 * 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 100000
CONFIG = {"max_file_bytes": MAX_FILE, "max_zip_total_bytes": MAX_ZIP_TOTAL,
          "max_zip_entries": MAX_ZIP_ENTRIES, "archive_mode": "read_only_no_extract"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def aggregate(results):
    values = set(results)
    return next((s for s in ("FAIL", "BLOCKED", "NOT_RUN") if s in values), "PASS")


class Gate:
    def __init__(self):
        self.checks = []

    def add(self, check_id, result, observed, scope="STATIC_ARTIFACT_INTEGRITY_ONLY"):
        if isinstance(result, bool):
            result = "PASS" if result else "FAIL"
        self.checks.append({"check_id": check_id, "result": result, "scope": scope, "observed": observed})

    def read(self, path, kind):
        try:
            data = path.read_bytes()
        except OSError as e:
            self.add("metadata:" + path.name, "BLOCKED", {"reason": type(e).__name__})
            return None
        try:
            return parse(data, kind)
        except (ValueError, UnicodeError, csv.Error, TypeError) as e:
            self.add("metadata:" + path.name, "FAIL", {"reason": type(e).__name__})
            return None


def parse(data, kind, columns=None):
    text = data.decode("utf-8-sig")
    if kind == "json":
        return json.loads(text)
    if kind == "jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("JSONL row is not an object")
        return rows
    if kind == "csv":
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        names = reader.fieldnames
        if not names or len(names) != len(set(names)) or any(not x for x in names):
            raise ValueError("Missing/duplicate CSV header")
        if columns and not set(columns) <= set(names):
            raise ValueError("CSV required columns missing")
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError("CSV row width differs from header")
        return rows
    return text


def check_format(data, fmt, columns=None):
    """Bounded static checks; no extraction or launch of downloaded code."""
    if fmt in ("json", "jsonl", "csv"):
        parse(data, fmt, columns)
    elif fmt == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ZIP_ENTRIES or sum(x.file_size for x in infos) > MAX_ZIP_TOTAL:
                raise ValueError("ZIP resource limit exceeded")
            for item in infos:
                name = item.filename.replace("\\", "/")
                parts = PurePosixPath(name).parts
                if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name):
                    raise ValueError("ZIP unsafe path")
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("ZIP symbolic link")
                if item.file_size > MAX_FILE:
                    raise ValueError("ZIP member exceeds limit")
                with z.open(item) as member:
                    while member.read(1024 * 1024):
                        pass  # EOF consumes CRC validation without writing member bytes.
    elif fmt == "7z":
        if len(data) < 32 or data[:6] != b"7z\xbc\xaf\x27\x1c":
            raise ValueError("Not a complete 7z header")
        offset, size = struct.unpack_from("<QQ", data, 12)
        if 32 + offset + size > len(data):
            raise ValueError("Truncated 7z next header")
        # Full 7z decode is a separate inventory task, never claimed here.
    elif fmt == "exe":
        if len(data) < 64 or data[:2] != b"MZ":
            raise ValueError("Not an executable header")
        off = struct.unpack_from("<I", data, 60)[0]
        if off and (off + 2 > len(data) or data[off:off+2] not in (b"PE", b"NE", b"LE", b"LX")):
            raise ValueError("Truncated/invalid executable image header")
    elif fmt == "png":
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or b"IEND" not in data[-12:]:
            raise ValueError("Invalid/truncated PNG")
    elif fmt in ("jpg", "jpeg"):
        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise ValueError("Invalid/truncated JPEG")
    elif fmt == "wav":
        with wave.open(io.BytesIO(data)) as w:
            expected = w.getnframes() * w.getnchannels() * w.getsampwidth()
            if len(w.readframes(w.getnframes())) != expected:
                raise ValueError("Truncated WAV frames")
    elif fmt == "text":
        for encoding in ("utf-8-sig", "cp949", "utf-16"):
            try:
                data.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ValueError("Undecodable text")
    elif fmt == "bytes":
        pass
    else:
        return "NOT_RUN", "No format reader for this type; only byte identity is checked"
    detail = "Header/bounds only; full decode NOT_RUN" if fmt in ("7z", "exe") else "Static syntax/container checks"
    return "PASS", detail


def inferred_format(name):
    ext = Path(name).suffix.lower().lstrip(".")
    if ext in {"json", "jsonl", "csv", "zip", "7z", "exe", "png", "jpg", "jpeg", "wav"}:
        return ext
    if ext in {"txt", "md", "py", "cs", "gd", "c", "h", "cpp", "lua", "xml", "props", "csproj", "java", "js", "ts", "yml", "yaml"}:
        return "text"
    return "unknown"


def ledger_inputs(gate, out):
    sources = gate.read(out / "sources.jsonl", "jsonl")
    archives = gate.read(out / "archive_sources.jsonl", "jsonl")
    members = gate.read(out / "archive_members.jsonl", "jsonl")
    if sources is None or archives is None or members is None:
        return [], None
    inputs = []
    source_by_id = {s.get("source_id"): s for s in sources}
    for source in sources:
        sid = source["source_id"]
        files = source.get("files", [])
        if source.get("sha256") and not files:
            name = source.get("file_path") or source.get("original_id") or source.get("library_path") or source.get("source_path_or_url", "")
            inputs.append({"input_id": sid, "source_id": sid, "path": source.get("local_materialization_path") or source.get("private_local_path"),
                           "sha256": source["sha256"], "size_bytes": source.get("size_bytes"), "format": inferred_format(name),
                           "client_build": source.get("client_build"), "parser_version": source.get("parser_version"), "kind": "source"})
        for entry in files:
            inputs.append({"input_id": sid + "::" + entry["path"], "source_id": sid, "path": entry.get("local_path"),
                           "sha256": entry.get("sha256"), "size_bytes": entry.get("actual_size", entry.get("size")),
                           "format": inferred_format(entry["path"]), "kind": "source_file"})
    cross = []
    for arc in archives:
        other = source_by_id.get(arc.get("source_id"), {})
        for field in ("sha256", "size_bytes", "client_build", "parser_version"):
            if arc.get(field) != other.get(field):
                cross.append({"input_id": arc.get("source_id"), "field": field})
    gate.add("archive_source_ledger_consistency", not cross, {"mismatches": cross})
    for member in members:
        inputs.append({"input_id": member["member_id"], "source_id": member["source_id"], "path": member.get("local_path"),
                       "sha256": member.get("sha256"), "size_bytes": member.get("size_bytes"),
                       "format": inferred_format(member.get("archive_member", "")), "parser_version": member.get("parser_version"), "kind": "archive_member"})
    return inputs, (sources, members)


def metadata_checks(gate, root, out, ledgers):
    required = ["REPORT.md", "NEXT_P2.md", "requirements.csv", "sources.jsonl", "issues.csv", "field_bindings.jsonl", "archive_sources.jsonl", "archive_members.jsonl", "coverage_matrix.json", "RESTORATION_PROFILE.json"]
    absent = [name for name in required if not (out / name).is_file()]
    gate.add("required_deliverables", "BLOCKED" if absent else "PASS", {"expected": required, "missing": absent})
    reqs = gate.read(out / "requirements.csv", "csv")
    issues = gate.read(out / "issues.csv", "csv")
    bindings = gate.read(out / "field_bindings.jsonl", "jsonl")
    coverage = gate.read(out / "coverage_matrix.json", "json")
    profile = gate.read(out / "RESTORATION_PROFILE.json", "json")
    state = gate.read(root / "docs/rebuild/STATE.json", "json")
    if any(x is None for x in (reqs, issues, bindings, coverage, profile, state, ledgers)):
        gate.add("dependent_metadata_checks", "NOT_RUN", "At least one required metadata input did not load")
        return
    sources, members = ledgers
    groups = [("requirements", reqs, "requirement_id"), ("sources", sources, "source_id"), ("issues", issues, "issue_id"), ("bindings", bindings, "binding_id"), ("members", members, "member_id")]
    missing_keys = [(name, index, key) for name, rows, key in groups for index, row in enumerate(rows) if not isinstance(row, dict) or not row.get(key)]
    gate.add("identity_fields_present", not missing_keys, {"missing_keys": missing_keys})
    if missing_keys:
        return
    for name, rows, key in groups:
        gate.add("unique_" + name + "_ids", len(rows) == len({r[key] for r in rows}) and bool(rows), {"rows": len(rows), "unique": len({r[key] for r in rows})})
    R = {r["requirement_id"]: r for r in reqs}; S = {s["source_id"]: s for s in sources}; M = {m["member_id"]: m for m in members}
    needed = "requirement_id category canonical_requirement expected_behavior evidence_needed source_ids source_locator confirmed_information missing_information implementation_feature normal_test_id normal_test failure_test_id failure_test cancel_test_id cancel_test priority planned_phase fact_status use_status test_status".split()
    blank = [(r["requirement_id"], key) for r in reqs for key in needed if not r.get(key, "").strip()]
    gate.add("requirement_cells_complete", not blank, {"empty_cells": blank})
    refs = []
    for label, rows, ref_key, targets in [("requirements", reqs, "source_ids", S), ("issues", issues, "source_ids", S), ("issues", issues, "requirement_ids", R), ("bindings", bindings, "source_ids", S), ("bindings", bindings, "requirement_ids", R)]:
        for row in rows:
            values = row.get(ref_key, [])
            if isinstance(values, str): values = values.split("|")
            refs.extend((label, ref_key, value) for value in values if value not in targets)
    refs.extend(("members", "source_id", m.get("source_id")) for m in members if m.get("source_id") not in S)
    refs.extend((b["binding_id"], "member_id", m.get("member_id")) for b in bindings for m in b.get("original_member_candidates", []) if m.get("member_id") not in M)
    gate.add("all_source_requirement_member_refs", not refs, {"broken_refs": refs})
    testids = [r.get(k) for r in reqs for k in ("normal_test_id", "failure_test_id", "cancel_test_id")]
    gate.add("unique_normal_failure_cancel_tests", len(testids) == len(set(testids)) == 3 * len(reqs), {"designed": len(testids), "unique": len(set(testids))})
    gate.add("unexecuted_game_tests_not_pass", all(r.get("test_status") == "NOT_RUN" for r in reqs) and all(i.get("new_game_test_status") == "NOT_RUN" for i in issues) and all(b.get("test_status") == "NOT_RUN" for b in bindings), {"runtime_tests_executed": 0})
    gate.add("no_new_runtime_bound_claim", all(r.get("use_status") not in ("BOUND", "EXERCISED") for r in reqs) and all(not s.get("new_runtime_bound") for s in sources), {"new_runtime": "NOT_STARTED"})
    gate.add("canonical_provenance_axes", all(s.get("fact_status") in ("ORIGINAL_VERIFIED", "CORROBORATED_RECONSTRUCTION", "INFERRED", "UNKNOWN") and s.get("use_status") in ("DISCOVERED", "ACQUIRED", "DECODED", "IDENTIFIED", "BOUND", "EXERCISED") for s in sources), {"sources": len(sources)})
    badhash = [s["source_id"] for s in sources if (s.get("sha256") and not re.fullmatch(r"[a-f0-9]{64}", str(s["sha256"]))) or (not s.get("sha256") and not s.get("missing_hash_reason"))]
    badhash += [m["member_id"] for m in members if not re.fullmatch(r"[a-f0-9]{64}", str(m.get("sha256", "")))]
    gate.add("source_and_member_hashes_or_explicit_gap", not badhash, {"invalid_hash_ids": badhash})
    covrefs = [(kind, key, item) for kind in ("required_categories", "inherited_regressions") for key, values in coverage.get(kind, {}).items() for item in values if item not in R]
    gate.add("required_categories_and_inherited_failures", not covrefs and len(coverage.get("required_categories", {})) == 9 and len(coverage.get("inherited_regressions", {})) == 10 and {r.get("category") for r in reqs} == {"START", "UI", "WORLD", "GROWTH", "COMBAT", "LIFE", "AV", "SAVE", "OPS"}, {"broken_refs": covrefs})
    expected_reasons = {"접근 불가", "해독 실패", "ID 미식별", "버전 불일치", "지원 코드 없음", "패키징·캐시 결함", "의도적 미사용"}
    gate.add("seven_unused_reasons_have_actions", expected_reasons <= {i.get("unused_reason") for i in issues} and all(i.get("resolution_and_next_action") and i.get("blocking_for") and i.get("next_phase") for i in issues), {"issues": len(issues)})
    gate.add("stage_and_approval_boundary", state.get("implementation_status") == "NOT_STARTED" and state.get("p2_execution_authorized") is False and profile.get("runtime_binding") == "NOT_STARTED", {"implementation_status": state.get("implementation_status"), "p2_execution_authorized": state.get("p2_execution_authorized")})
    patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{40,}", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}", r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"]
    public = [p for base in (out, root / "tools/rebuild/step01") for p in base.rglob("*") if p.is_file() and p.name != "VALIDATION.json" and "__pycache__" not in p.parts and not p.name.endswith(".draft.csv")]
    public += [root / "AGENTS.md", root / "docs/rebuild/STATE.json"]
    badtypes = [str(p.relative_to(root)) for p in public if p.suffix not in (".md", ".json", ".jsonl", ".csv", ".py")]
    secrets = []; unreadable = []
    for p in public:
        if p.suffix == ".py": continue  # Detector literals are not secrets.
        try:
            text = p.read_text(encoding="utf-8-sig")
            if any(re.search(pattern, text) for pattern in patterns): secrets.append(str(p.relative_to(root)))
        except (OSError, UnicodeError):
            unreadable.append(str(p.relative_to(root)))
    gate.add("public_metadata_only_no_secret_patterns", "FAIL" if badtypes or secrets else "BLOCKED" if unreadable else "PASS", {"unexpected_file_types": badtypes, "secret_pattern_files": secrets, "unreadable": unreadable, "limitation": "Pattern scan is not complete credential or malware detection"})


def byte_checks(gate, inputs, mapping, scopes, base, declaration_missing=False):
    invalid = [index for index, row in enumerate(inputs) if not isinstance(row.get("input_id"), str) or not row.get("input_id")]
    gate.add("input_id_schema", not invalid, {"invalid_row_indices": invalid})
    inputs = [row for row in inputs if isinstance(row.get("input_id"), str) and row.get("input_id")]
    seen = Counter(row.get("input_id") for row in inputs)
    declaration_result = "BLOCKED" if not inputs and declaration_missing else bool(inputs) and all(v == 1 and k for k, v in seen.items())
    gate.add("declared_required_input_set", declaration_result, {"expected": len(inputs), "duplicate_ids": [k for k, v in seen.items() if v > 1]})
    unknown_map = set(mapping) - set(seen)
    gate.add("relocation_map_known_ids", not unknown_map, {"unknown_ids": sorted(unknown_map)})
    records = []
    for item in inputs:
        iid = item.get("input_id")
        row = {"input_id": iid, "source_id": item.get("source_id"), "kind": item.get("kind"), "result": "NOT_RUN", "read": False}
        records.append(row)
        path = mapping.get(iid, item.get("path"))
        if isinstance(path, dict): path = path.get("path")
        if not path:
            row.update(result="BLOCKED", reason="NO_CURRENT_PATH")
            continue
        if not isinstance(path, str):
            row.update(result="FAIL", reason="INVALID_PATH_TYPE")
            continue
        p = Path(path)
        if not p.is_absolute(): p = base / p
        try:
            if p.is_symlink():
                raise ValueError("Symbolic link input is not allowed")
            with p.open("rb") as f:
                data = f.read(MAX_FILE + 1)
        except OSError as e:
            row.update(result="BLOCKED", reason=type(e).__name__)
            continue
        except ValueError as e:
            row.update(result="FAIL", reason=str(e))
            continue
        row.update(read=True, size_bytes=len(data), actual_sha256=sha(data))
        failures = []
        if len(data) > MAX_FILE: failures.append("FILE_LIMIT_EXCEEDED")
        if not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))): failures.append("INVALID_EXPECTED_SHA256")
        elif row["actual_sha256"] != item["sha256"]: failures.append("SHA256_MISMATCH")
        if item.get("size_bytes") is not None and len(data) != item["size_bytes"]: failures.append("SIZE_MISMATCH")
        fmt = item.get("format", "unknown")
        try:
            status, detail = check_format(data, fmt, item.get("required_columns"))
            row.update(format=fmt, format_result=status, format_detail=detail)
            if status == "NOT_RUN" and item.get("require_format_validation"):
                row.update(result="NOT_RUN", reason="REQUIRED_FORMAT_READER_UNAVAILABLE")
        except (ValueError, UnicodeError, csv.Error, zipfile.BadZipFile, RuntimeError, EOFError, wave.Error, struct.error) as e:
            row.update(format=fmt, format_result="FAIL", format_detail=type(e).__name__)
            failures.append("FORMAT_MISMATCH_OR_TRUNCATION")
        if fmt == "json" and item.get("expected_fields"):
            try:
                document = parse(data, "json")
                for key, expected in item["expected_fields"].items():
                    value = document
                    for part in key.split("."): value = value[part]
                    if value != expected: failures.append("VERSION_OR_FIELD_MISMATCH:" + key)
            except (KeyError, TypeError, ValueError, UnicodeError):
                failures.append("EXPECTED_FIELD_UNREADABLE")
        if failures:
            row.update(result="FAIL", reasons=failures)
        elif row["result"] != "NOT_RUN" or row.get("reason") != "REQUIRED_FORMAT_READER_UNAVAILABLE":
            row["result"] = "PASS"
    missing = [r["input_id"] for r in records if not r["read"]]
    read = [r["input_id"] for r in records if r["read"]]
    gate.add("available_acquired_files_match_ledger", aggregate([r["result"] for r in records]) if records else "BLOCKED", {"expected_ids": sorted(seen), "checked_ids": sorted(read), "missing_ids": sorted(missing), "expected": len(seen), "checked": len(read), "matched": sum(r["result"] == "PASS" for r in records), "result_counts": dict(Counter(r["result"] for r in records))}, "FULL_DECLARED_BYTE_INPUT_SET")
    if scopes:
        unknown = set(scopes) - set(seen)
        selected = [r for r in records if r["input_id"] in scopes]
        scoped_result = "FAIL" if unknown else aggregate([r["result"] for r in selected]) if selected else "BLOCKED"
        scoped = {"result": scoped_result, "requested_ids": scopes, "unknown_ids": sorted(unknown), "checked": sum(r["read"] for r in selected), "scope_note": "Exact selected input IDs only; excluded IDs remain mandatory in overall result", "excluded_mandatory_ids": sorted(set(seen) - set(scopes))}
    else:
        scoped = {"result": "NOT_RUN", "reason": "No narrower scope requested"}
    return records, scoped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--artifact-dir", type=Path)
    ap.add_argument("--input-map", type=Path, help="JSON object input_id -> current private path; never changes expected IDs/hashes")
    ap.add_argument("--contract", type=Path, help="Explicit isolated static input contract; does not claim P0/P1 validation")
    ap.add_argument("--scope-input", action="append", default=[], help="Report exact narrower byte IDs without weakening overall result")
    ap.add_argument("--output", type=Path, help="New JSON evidence path; historical step01/VALIDATION.json is forbidden")
    args = ap.parse_args()
    root = args.root.resolve(); out = args.artifact_dir or root / "docs/rebuild/step01"
    gate = Gate(); contract = None; mapping = {}; ledgers = None
    if args.input_map:
        mapping = gate.read(args.input_map, "json")
        if not isinstance(mapping, dict):
            gate.add("relocation_map_shape", "FAIL", "Expected JSON object")
            mapping = {}
    if args.contract:
        contract = gate.read(args.contract, "json")
        if not isinstance(contract, dict):
            gate.add("contract_shape", "FAIL", "Expected JSON object")
            contract = {}
        expected = {"schema_version": 2, "validator_version": VERSION, "parser_version": PARSER_VERSION, "config_sha256": fingerprint(CONFIG)}
        mismatch = [key for key, value in expected.items() if contract.get(key) != value]
        gate.add("version_parser_config_fingerprint", not mismatch, {"mismatched_fields": mismatch, "actual": expected})
        if "validator_sha256" in contract:
            gate.add("validator_code_fingerprint", contract["validator_sha256"] == sha(Path(__file__).read_bytes()), {"actual_sha256": sha(Path(__file__).read_bytes())})
        inputs = contract.get("inputs", [])
        if not isinstance(inputs, list) or any(not isinstance(i, dict) for i in inputs):
            gate.add("contract_inputs_shape", "FAIL", "Expected list of objects")
            inputs = []
        base = args.contract.resolve().parent
    else:
        try:
            inputs, ledgers = ledger_inputs(gate, out)
            metadata_checks(gate, root, out, ledgers)
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            gate.add("metadata_schema_contract", "FAIL", {"reason": type(e).__name__})
            inputs = []
        base = root
    declaration_missing = not args.contract and any(c["result"] == "BLOCKED" for c in gate.checks)
    records, scoped = byte_checks(gate, inputs, mapping, args.scope_input, base, declaration_missing)
    result = aggregate(c["result"] for c in gate.checks)
    metadata = [c["result"] for c in gate.checks if c["scope"] == "STATIC_ARTIFACT_INTEGRITY_ONLY"]
    exit_code = {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 3}[result]
    output = {"task_id": "BARAM_REBUILD_P1_5_001", "executed_at_utc": datetime.now(timezone.utc).isoformat(), "command": [sys.executable] + sys.argv,
              "validator_version": VERSION, "validator_sha256": sha(Path(__file__).read_bytes()), "parser_version": PARSER_VERSION, "config_sha256": fingerprint(CONFIG),
              "input_mode": "EXPLICIT_ISOLATED_CONTRACT" if args.contract else "FULL_STEP01_LEDGERS", "result": result, "metadata_result": "NOT_RUN" if args.contract else aggregate(metadata), "scoped_result": scoped,
              "exit_code": exit_code, "scope": "STATIC INPUT INTEGRITY ONLY; NOT ORIGINAL SEMANTICS/HISTORY/MALWARE SAFETY/GAMEPLAY", "checks": gate.checks, "inputs": records,
              "runtime_tests": "NOT_RUN", "p2_tests": "NOT_RUN", "runtime_tests_executed": 0, "p2_executed": False,
              "format_limitations": "Unknown formats are marked NOT_RUN for decoding. EXE/7z only header/bounds; no binary execution or full semantic decode."}
    output["input_fingerprints"] = {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "VALIDATION.json" and "__pycache__" not in p.parts} if not args.contract else {"contract_sha256": sha(args.contract.read_bytes())}
    if args.output:
        target = args.output.resolve()
        if target == (root / "docs/rebuild/step01/VALIDATION.json").resolve() or target == (ROOT / "docs/rebuild/step01/VALIDATION.json").resolve():
            ap.error("Historical step01/VALIDATION.json must not be overwritten")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": result, "metadata_result": output["metadata_result"], "scoped_result": scoped["result"], "expected": len(records), "checked": sum(r["read"] for r in records), "input_results": dict(Counter(r["result"] for r in records)), "check_results": dict(Counter(c["result"] for c in gate.checks)), "exit_code": exit_code, "runtime_tests_executed": 0}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
