#!/usr/bin/env python3
"""Read-only publication/package audit. Reports locations/types, never secret values.

No extraction to member-selected paths, imports of packaged code, or execution of
EXE/SQL/Lua/native libraries. This is an integrity/exclusion scan, not malware QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile

VERSION = "p1.5-handoff-security/1.1"
CHUNK = 1024 * 1024
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 3 * 1024 * 1024 * 1024
MAX_ENTRIES = 100000
MAX_DEPTH = 2
PATTERNS = {
    "private_key_marker": re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9_]{30,220}|github_pat_[A-Za-z0-9_]{40,220})\b"),
    "openai_token": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,220}\b"),
    "aws_access_id": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "literal_bearer_token": re.compile(rb"(?i)bearer[ \t]{1,20}[A-Za-z0-9._~-]{30,220}"),
    "signed_download_url": re.compile(rb"(?i)(?:[?&]|\\u0026)(?:X-Amz-Signature|sig)=[A-Za-z0-9%/_+~.-]{20,220}"),
    "literal_transfer_completion_token": re.compile(rb'"completion_token"\s*:\s*"[^"\r\n]{20,220}"'),
}


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def path_reasons(name, public=False):
    normalized = name.replace("\\", "/")
    p = PurePosixPath(normalized)
    parts = p.parts
    lower = normalized.casefold()
    reasons = []
    if "\0" in name or p.is_absolute() or ".." in parts or any(":" in x for x in parts):
        reasons.append("UNSAFE_MEMBER_PATH")
    if any(x.casefold() in {".git", "__pycache__", "private-intake"} for x in parts):
        reasons.append("EXCLUDED_INTERNAL_DIRECTORY")
    if lower.endswith((".pyc", ".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".sav", ".save", ".sqlite", ".sqlite3", ".db")) or p.name.casefold() in {"id_rsa", "id_ed25519", ".env"}:
        reasons.append("PRIVATE_KEY_CACHE_OR_ENV_FILENAME")
    if p.name.casefold() in {"save.json", "savegame.json", "user_save.json", "profile.json", "credentials.json", "tokens.json", "token.json"}:
        reasons.append("USER_SAVE_OR_CREDENTIAL_FILENAME")
    if re.search(r"(?:^|/)(?:rtk-server|rtk-server-source)/database(?:/|$)", lower):
        reasons.append("EXCLUDED_RAW_RTK_DATABASE")
    if p.name.casefold() in {"docker-compose.yml", "docker-compose.yaml", "god_tools.lua"}:
        reasons.append("EXCLUDED_REFERENCE_DEFAULT_CREDENTIAL_SOURCE")
    if public and "/selected_content/" in "/" + lower and lower.endswith(".jsonl"):
        reasons.append("PRIVATE_SELECTED_VALUES_IN_PUBLIC_SET")
    return reasons


def scan_stream(stream, location, findings, copy_to=None):
    h = hashlib.sha256()
    size = 0
    tail = b""
    counts = {}
    while True:
        b = stream.read(CHUNK)
        if not b:
            break
        size += len(b)
        if size > MAX_FILE:
            raise ValueError("MEMBER_ACTUAL_SIZE_LIMIT")
        h.update(b)
        if copy_to is not None:
            copy_to.write(b)
        data, previous = tail + b, len(tail)
        for kind, pattern in PATTERNS.items():
            for m in pattern.finditer(data):
                if m.end() > previous:
                    counts[kind] = counts.get(kind, 0) + 1
        tail = data[-512:]
    for kind, count in counts.items():
        findings.append({"location": location, "type": kind, "count": count})
    return {"sha256": h.hexdigest(), "bytes": size}


def public_paths(repo):
    paths = [repo / "AGENTS.md", repo / "docs/rebuild/STATE.json", repo / "tools/rebuild/step01/validate_step01.py"]
    for folder in ["tools/rebuild/p1_5", "docs/rebuild/p1_5"]:
        paths.extend(p for p in (repo / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return sorted({p for p in paths if not (p.suffix.casefold() == ".jsonl" and "selected_content" in p.parts)})


def audit_public(repo, file_list=None):
    result = {"scope": "CURRENT_AUTHORIZED_PUBLIC_P1_5_FILE_SET", "findings": [], "errors": [], "files": [], "secret_values_printed": False}
    paths = public_paths(repo) if file_list is None else [repo / x for x in file_list.read_text().splitlines() if x.strip()]
    for p in paths:
        try:
            relative = p.relative_to(repo).as_posix()
            if p.is_symlink():
                result["errors"].append({"location": relative, "type": "PUBLIC_SYMLINK"})
                continue
            if not p.is_file():
                result["errors"].append({"location": relative, "type": "MISSING_PUBLIC_FILE"})
                continue
            reasons = path_reasons(relative, public=True)
            for why in reasons:
                result["errors"].append({"location": relative, "type": why})
            if "UNSAFE_MEMBER_PATH" in reasons:
                continue
            if p.stat().st_size > MAX_FILE:
                raise ValueError("PUBLIC_FILE_SIZE_LIMIT")
            with p.open("rb") as stream:
                identity = scan_stream(stream, relative, result["findings"])
            result["files"].append({"path": relative, **identity})
        except (OSError, ValueError) as e:
            result["errors"].append({"location": str(p.name), "type": type(e).__name__})
    result["files_checked"] = len(result["files"])
    if not paths:
        result["errors"].append({"type": "EMPTY_PUBLIC_FILE_SET"})
    result["result"] = "FAIL" if result["findings"] or result["errors"] else "PASS"
    return result


def audit_outer_manifest(z, identities, result, label):
    """Check the complete package and the catalog-declared normalized inputs."""
    manifest_name = "PACKAGE_MANIFEST.json"
    if manifest_name not in identities:
        result["errors"].append({"type": "MISSING_PACKAGE_MANIFEST"})
        return
    manifest = json.loads(z.read(manifest_name))
    entries = manifest["files"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("EMPTY_OR_INVALID_PACKAGE_MANIFEST")
    expected = {e["path"]: e for e in entries}
    if len(expected) != len(entries):
        result["errors"].append({"type": "DUPLICATE_PACKAGE_MANIFEST_PATH"})
    actual = set(identities) - {manifest_name}
    missing, extra = set(expected) - actual, actual - set(expected)
    for rel in sorted(missing | extra):
        result["errors"].append({"location": label + "!" + rel, "type": "PACKAGE_MANIFEST_MEMBER_SET_MISMATCH"})
    mismatched = 0
    for rel in sorted(set(expected) & actual):
        if identities[rel]["sha256"] != expected[rel]["sha256"] or identities[rel]["bytes"] != expected[rel]["bytes"]:
            mismatched += 1
            result["errors"].append({"location": label + "!" + rel, "type": "PACKAGE_MANIFEST_BYTE_MISMATCH"})
    result["package_manifest"] = {"entries_expected": len(entries), "entries_read": len(actual), "missing": len(missing), "extra": len(extra), "mismatched": mismatched}

    prefix = "docs/rebuild/p1_5/"
    catalog_name = prefix + "selected_content/catalog.json"
    if catalog_name not in identities:
        result["errors"].append({"type": "MISSING_NORMALIZED_CATALOG"})
        return
    catalog = json.loads(z.read(catalog_name))["normalized_catalogs"]
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("EMPTY_OR_INVALID_NORMALIZED_CATALOG")
    declared = {}
    for entry in catalog:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("INVALID_NORMALIZED_CATALOG_ENTRY")
        rel = entry["path"]
        if not rel.startswith("selected_content/") or path_reasons(rel):
            raise ValueError("UNSAFE_NORMALIZED_CATALOG_PATH")
        name = prefix + rel
        if name in declared:
            result["errors"].append({"location": label + "!" + name, "type": "DUPLICATE_NORMALIZED_CATALOG_PATH"})
        declared[name] = entry
    expected_jsonl = {name for name in declared if name.casefold().endswith(".jsonl")}
    actual_jsonl = {name for name in identities if "/selected_content/" in "/" + name.casefold() and name.casefold().endswith(".jsonl")}
    if not expected_jsonl:
        result["errors"].append({"type": "EMPTY_PRIVATE_NORMALIZED_JSONL_SET"})
    for rel in sorted(expected_jsonl ^ actual_jsonl):
        result["errors"].append({"location": label + "!" + rel, "type": "PRIVATE_SELECTED_JSONL_SET_MISMATCH"})
    normalized_mismatches = 0
    for rel, entry in sorted(declared.items()):
        if rel not in identities:
            result["errors"].append({"location": label + "!" + rel, "type": "NORMALIZED_CATALOG_MEMBER_MISSING"})
        elif identities[rel]["sha256"] != entry["sha256"] or identities[rel]["bytes"] != entry["bytes"]:
            normalized_mismatches += 1
            result["errors"].append({"location": label + "!" + rel, "type": "NORMALIZED_CATALOG_BYTE_MISMATCH"})
    result["normalized_catalog"] = {"files_expected": len(declared), "private_jsonl_expected": len(expected_jsonl), "private_jsonl_read": len(actual_jsonl), "missing_jsonl": len(expected_jsonl - actual_jsonl), "extra_jsonl": len(actual_jsonl - expected_jsonl), "mismatched": normalized_mismatches}


def audit_zip(path, label, reference=False, depth=0, budget=None, outer=False):
    if budget is None:
        budget = {"bytes": 0}
    result = {"location": label, "findings": [], "errors": [], "members_checked": 0, "bytes_read": 0, "nested": [], "private_selected_jsonl_count": 0, "secret_values_printed": False}
    if depth > MAX_DEPTH:
        result["errors"].append({"type": "NESTING_LIMIT"})
        result["result"] = "FAIL"
        return result
    identities = {}
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if not infos:
                raise ValueError("EMPTY_ZIP_INPUT")
            if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL:
                raise ValueError("ZIP_DECLARED_BUDGET_LIMIT")
            names = set()
            for info in infos:
                if info.is_dir():
                    continue
                location = label + "!" + info.filename
                normalized = info.filename.replace("\\", "/")
                if normalized in names:
                    result["errors"].append({"location": location, "type": "DUPLICATE_MEMBER_PATH"})
                names.add(normalized)
                for why in path_reasons(info.filename):
                    result["errors"].append({"location": location, "type": why})
                if stat.S_ISLNK(info.external_attr >> 16):
                    result["errors"].append({"location": location, "type": "ARCHIVE_SYMLINK"})
                if info.file_size > MAX_FILE or info.flag_bits & 1:
                    result["errors"].append({"location": location, "type": "ENCRYPTED_OR_OVERSIZED_MEMBER"})
                    continue
                if "/selected_content/" in "/" + normalized.casefold() and normalized.casefold().endswith(".jsonl"):
                    result["private_selected_jsonl_count"] += 1
                if normalized.casefold().endswith(".zip"):
                    with tempfile.TemporaryFile() as temp:
                        with z.open(info) as stream:
                            identity = scan_stream(stream, location, result["findings"], temp)
                        temp.seek(0)
                        child = audit_zip(temp, location, reference=PurePosixPath(normalized).name == "reference_sources.zip", depth=depth + 1, budget=budget)
                        child["archive_identity"] = identity
                        result["nested"].append(child)
                else:
                    with z.open(info) as stream:
                        identity = scan_stream(stream, location, result["findings"])
                identities[normalized] = identity
                result["members_checked"] += 1
                result["bytes_read"] += identity["bytes"]
                budget["bytes"] += identity["bytes"]
                if budget["bytes"] > MAX_TOTAL:
                    raise ValueError("ZIP_ACTUAL_CUMULATIVE_BUDGET_LIMIT")
                if identity["bytes"] != info.file_size:
                    result["errors"].append({"location": location, "type": "ACTUAL_DECLARED_LENGTH_MISMATCH"})
            if reference:
                if "SOURCE_MANIFEST.json" not in names:
                    result["errors"].append({"type": "MISSING_REFERENCE_SOURCE_MANIFEST"})
                else:
                    manifest = json.loads(z.read("SOURCE_MANIFEST.json"))
                    entries = manifest["entries"]
                    expected = {e["path"]: e for e in entries}
                    if len(expected) != len(entries):
                        result["errors"].append({"type": "DUPLICATE_REFERENCE_MANIFEST_PATH"})
                    actual = set(identities) - {"SOURCE_MANIFEST.json"}
                    missing, extra = set(expected) - actual, actual - set(expected)
                    for rel in sorted(missing | extra):
                        result["errors"].append({"location": label + "!" + rel, "type": "REFERENCE_MANIFEST_MEMBER_SET_MISMATCH"})
                    mismatched = 0
                    for rel in set(expected) & actual:
                        if identities[rel]["sha256"] != expected[rel]["sha256"] or identities[rel]["bytes"] != expected[rel]["bytes"]:
                            mismatched += 1
                            result["errors"].append({"location": label + "!" + rel, "type": "REFERENCE_MANIFEST_BYTE_MISMATCH"})
                    excluded = {e["path"] for e in manifest.get("excluded", [])}
                    leaked = excluded & actual
                    for rel in sorted(leaked):
                        result["errors"].append({"location": label + "!" + rel, "type": "DECLARED_EXCLUSION_PRESENT"})
                    result["reference_manifest"] = {"entries_expected": len(entries), "entries_read": len(actual), "missing": len(missing), "extra": len(extra), "mismatched": mismatched, "declared_exclusions": len(excluded), "declared_exclusions_present": len(leaked)}
            if outer:
                audit_outer_manifest(z, identities, result, label)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as e:
        result["errors"].append({"location": label, "type": type(e).__name__, "details_redacted": True})
    result["result"] = "FAIL" if result["findings"] or result["errors"] or any(x["result"] != "PASS" for x in result["nested"]) else "PASS"
    return result


def guard_regression():
    """Small adversarial archives are generated in an isolated temporary folder."""
    cases = []
    with tempfile.TemporaryDirectory(prefix="baram-package-security-") as folder:
        root = Path(folder)
        for name in ["normal", "empty", "traversal", "symlink", "private_receipt", "synthetic_token", "manifest_missing", "manifest_mismatch", "crc_tamper"]:
            p = root / (name + ".zip")
            payload = b"known nonsecret source fixture\n"
            manifest = {"entries": [{"path": "source/example.txt", "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}], "excluded": []}
            with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_STORED) as z:
                if name != "empty":
                    z.writestr("source/example.txt", payload)
                    if name == "manifest_mismatch":
                        manifest["entries"][0]["sha256"] = "0" * 64
                    if name != "manifest_missing":
                        z.writestr("SOURCE_MANIFEST.json", json.dumps(manifest))
                if name == "traversal":
                    z.writestr("../outside.txt", b"fixture")
                elif name == "symlink":
                    info = zipfile.ZipInfo("source/link")
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    z.writestr(info, b"../outside.txt")
                elif name == "private_receipt":
                    z.writestr("private-intake/receipt.json", b"{}")
                elif name == "synthetic_token":
                    z.writestr("source/synthetic.txt", ("gh" + "p_" + "A" * 40).encode())
            if name == "crc_tamper":
                raw = p.read_bytes()
                raw = raw.replace(payload, b"X" + payload[1:], 1)
                p.write_bytes(raw)
            result = audit_zip(p, p.name, reference=True)
            expected = "PASS" if name == "normal" else "FAIL"
            cases.append({"case": name, "expected": expected, "actual": result["result"], "result": "PASS" if result["result"] == expected else "FAIL", "reported_types": sorted({x["type"] for x in result["errors"] + result["findings"]})})
        outer_cases = {
            "outer_normal": None,
            "outer_manifest_missing": "MISSING_PACKAGE_MANIFEST",
            "outer_member_missing": "PACKAGE_MANIFEST_MEMBER_SET_MISMATCH",
            "outer_member_extra": "PACKAGE_MANIFEST_MEMBER_SET_MISMATCH",
            "outer_hash_tamper": "PACKAGE_MANIFEST_BYTE_MISMATCH",
            "outer_length_tamper": "PACKAGE_MANIFEST_BYTE_MISMATCH",
            "outer_manifest_duplicate": "DUPLICATE_PACKAGE_MANIFEST_PATH",
            "outer_jsonl_missing": "PRIVATE_SELECTED_JSONL_SET_MISMATCH",
            "outer_jsonl_extra": "PRIVATE_SELECTED_JSONL_SET_MISMATCH",
            "outer_jsonl_same_count_wrong_name": "PRIVATE_SELECTED_JSONL_SET_MISMATCH",
            "outer_normalized_hash_tamper": "NORMALIZED_CATALOG_BYTE_MISMATCH",
        }
        prefix = "docs/rebuild/p1_5/selected_content/"
        for name, required_type in outer_cases.items():
            p = root / (name + ".zip")
            normalized = {prefix + "example.jsonl": b'{"id":"fixture"}\n', prefix + "save_contracts.json": b'{"contracts":[]}\n'}
            catalog = {"normalized_catalogs": [{"path": "selected_content/" + PurePosixPath(rel).name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for rel, data in normalized.items()]}
            if name == "outer_normalized_hash_tamper":
                catalog["normalized_catalogs"][0]["sha256"] = "0" * 64
            members = dict(normalized)
            members[prefix + "catalog.json"] = json.dumps(catalog).encode()
            members["READ_FIRST.md"] = b"synthetic static handoff fixture\n"
            if name == "outer_jsonl_missing":
                del members[prefix + "example.jsonl"]
            elif name == "outer_jsonl_extra":
                members[prefix + "undeclared.jsonl"] = b'{}\n'
            elif name == "outer_jsonl_same_count_wrong_name":
                members[prefix + "wrong-name.jsonl"] = members.pop(prefix + "example.jsonl")
            entries = [{"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for rel, data in members.items()]
            if name == "outer_hash_tamper":
                entries[0]["sha256"] = "0" * 64
            elif name == "outer_length_tamper":
                entries[0]["bytes"] += 1
            elif name == "outer_manifest_duplicate":
                entries.append(dict(entries[0]))
            if name == "outer_member_missing":
                del members["READ_FIRST.md"]
            elif name == "outer_member_extra":
                members["undeclared.txt"] = b"fixture\n"
            if name != "outer_manifest_missing":
                members["PACKAGE_MANIFEST.json"] = json.dumps({"files": entries}).encode()
            with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_STORED) as z:
                for rel, data in members.items():
                    z.writestr(rel, data)
            result = audit_zip(p, p.name, outer=True)
            expected = "PASS" if required_type is None else "FAIL"
            reported_types = sorted({x["type"] for x in result["errors"] + result["findings"]})
            passed = result["result"] == expected and (required_type is None or required_type in reported_types)
            cases.append({"case": name, "expected": expected, "actual": result["result"], "required_error_type": required_type, "result": "PASS" if passed else "FAIL", "reported_types": reported_types})
    return {"result": "PASS" if all(x["result"] == "PASS" for x in cases) else "FAIL", "scope": "isolated reference and outer-package adversarial ZIP fixtures; originals unchanged", "cases_executed": len(cases), "cases": cases}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument("--public-file-list", type=Path)
    ap.add_argument("--package", type=Path)
    ap.add_argument("--reference-zip", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    public = audit_public(args.repo.resolve(), args.public_file_list)
    package = audit_zip(args.package, args.package.name, outer=True) if args.package else {"result": "NOT_RUN", "reason": "FINAL_OUTER_PACKAGE_NOT_PROVIDED"}
    if args.package:
        references = [x for x in package["nested"] if x["location"].endswith("!inputs/reference_sources.zip")]
        if len(references) != 1:
            package["errors"].append({"type": "REQUIRED_NESTED_REFERENCE_INPUT_MISSING_OR_DUPLICATE", "expected": 1, "actual": len(references)})
        if package["errors"]:
            package["result"] = "FAIL"
    reference = audit_zip(args.reference_zip, args.reference_zip.name, reference=True) if args.reference_zip else {"result": "NOT_RUN", "reason": "NO_STANDALONE_REFERENCE_ZIP_REQUESTED"}
    if args.reference_zip:
        reference["archive_identity"] = {"sha256": sha_file(args.reference_zip), "bytes": args.reference_zip.stat().st_size}
    results = [public["result"], package["result"]] + ([reference["result"]] if args.reference_zip else [])
    status = "FAIL" if "FAIL" in results else "PARTIAL" if "NOT_RUN" in results else "PASS"
    regression = guard_regression() if args.self_test else {"result": "NOT_RUN"}
    if regression["result"] == "FAIL":
        status = "FAIL"
    report = {"task_id": "BARAM_REBUILD_P1_5_001", "tool_version": VERSION, "tool_sha256": sha_file(Path(__file__)), "scope_result": status, "public": public, "outer_package": package, "standalone_reference": reference, "guard_regression": regression, "package_identity": {"file_name": args.package.name, "sha256": sha_file(args.package), "bytes": args.package.stat().st_size} if args.package else None, "source_executable_execution": "NOT_RUN", "malware_absence": "UNKNOWN", "historical_accuracy": "NOT_EVALUATED", "secret_values_printed": False, "limitations": ["Pattern checks are heuristic; no comprehensive Git history or obfuscated-secret review", "Archive identity and exclusions do not establish malware absence", "Public file-set snapshot precedes creation of this result file; final commit and Library delivery are separate checks"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"scope_result": status, "public_files_checked": public["files_checked"], "public_result": public["result"], "outer_package_result": package["result"], "reference_result": reference["result"], "secret_values_printed": False}))
    return 1 if status == "FAIL" else 2 if status == "PARTIAL" else 0


if __name__ == "__main__":
    sys.exit(main())
