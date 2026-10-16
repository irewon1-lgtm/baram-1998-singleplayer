"""Read-only Work batch review. Never extract, import, or execute batch content.

The caller supplies explicit paths and independently pinned expectations. Metadata
review is not receipt of private bytes, adoption, historical accuracy, or P2 PASS.
Exit 0 = RECEIVED (not adopted), 1 = REJECTED, 2 = DEFERRED.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import zipfile


class Rejected(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 8 * 1024 * 1024
    total_bytes: int = 64 * 1024 * 1024
    archive_bytes: int = 32 * 1024 * 1024
    entries: int = 256
    path_depth: int = 8
    json_depth: int = 32
    ratio: int = 1000
    seconds: float = 10.0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise Rejected(message)


def safe_name(name: str, limits: Limits) -> str:
    require(isinstance(name, str) and 0 < len(name) <= 240, "invalid path length/type")
    require(not any(ord(c) < 32 for c in name), "control byte in path")
    require(not any(c in name for c in "\\:*?\"<>|"), "Windows-unsafe path")
    parts = name.split("/")
    require(len(parts) <= limits.path_depth, "path depth limit")
    for part in parts:
        require(part not in {"", ".", ".."} and not part.endswith((".", " ")), "unsafe path component")
        require(not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part), "reserved path")
    return name


def regular_bytes(path: Path, maximum: int) -> bytes:
    """No directory traversal, symlinks, special files, or unbounded reads."""
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        require(not item.is_symlink(), "symlink in explicit input path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), "input is not a regular file")
        require(info.st_size <= maximum, "input size limit")
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, "input grew past size limit")
    return data


def strict_json(data: bytes, limits: Limits):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, "duplicate JSON key")
            obj[key] = value
        return obj

    def constant(_):
        raise Rejected("nonfinite JSON constant")

    obj = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    pending = [(obj, 0)]
    while pending:
        value, depth = pending.pop()
        require(depth <= limits.json_depth, "JSON depth limit")
        if isinstance(value, dict):
            pending.extend((x, depth + 1) for x in value.values())
        elif isinstance(value, list):
            pending.extend((x, depth + 1) for x in value)
    return obj


def records(data: bytes, limits: Limits):
    return [strict_json(line, limits) for line in data.splitlines() if line.strip()]


def identity(data: bytes):
    return {"bytes": len(data), "sha256": sha256(data)}


def parse_ready(data: bytes):
    text = data.decode("utf-8")
    fields = {}
    for key, pattern in {
        "bytes": r"^길이:\s*(\d+)(?:\s+bytes)?\s*$",
        "sha256": r"^SHA256:\s*([a-f0-9]{64})\s*$",
        "library_file_id": r"^지속 파일 ID:\s*(libfile_[a-f0-9]+)\s*$",
        "file_id": r"^파일 ID:\s*(file_[a-f0-9]+)\s*$",
        "version": r"^버전:\s*(\d+)\s*$",
    }.items():
        matches = re.findall(pattern, text, re.MULTILINE)
        require(len(matches) == 1, "READY missing/duplicate " + key)
        fields[key] = int(matches[0]) if key in {"bytes", "version"} else matches[0]
    return fields


def file_table(manifest, limits):
    rows = manifest.get("files")
    require(isinstance(rows, list) and 0 < len(rows) <= limits.entries, "empty/oversize file set")
    table, folded = {}, set()
    for row in rows:
        name = safe_name(row["path"], limits)
        require(Path(name).suffix.lower() not in {".ttf", ".otf", ".woff", ".woff2", ".pfx", ".jks", ".keystore", ".pem", ".sql", ".bak"},
                "excluded sensitive/font/database payload type")
        require(name.casefold() not in folded, "duplicate/case-alias manifest path")
        require(name not in {"MANIFEST.json", "VALIDATION.json"}, "recursive manifest/validation entry")
        require(type(row.get("bytes")) is int and 0 <= row["bytes"] <= limits.file_bytes, "file size limit")
        require(re.fullmatch("[a-f0-9]{64}", row.get("sha256", "")), "invalid SHA256")
        table[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
        folded.add(name.casefold())
    require(sum(row["bytes"] for row in table.values()) <= limits.total_bytes, "total size limit")
    require({"FIELD_CANDIDATES.jsonl", "SOURCES.jsonl", "README.md"} <= table.keys(), "required payload metadata missing")
    for name in table:
        require(not any(name.startswith(other + "/") for other in table), "file/directory prefix collision")
    return table


def inspect_zip(path, expected_identity, table, manifest_bytes, validation_bytes, limits):
    """Bounded ZIP validation in memory. No batch files are written or invoked."""
    import io

    start = time.monotonic()
    data = regular_bytes(path, limits.archive_bytes)
    require(identity(data) == expected_identity, "ZIP length/hash mismatch")
    expected = dict(table)
    expected.update({"MANIFEST.json": identity(manifest_bytes), "VALIDATION.json": identity(validation_bytes)})
    payload, seen = {}, set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= limits.entries, "ZIP entry count limit")
        require(len(infos) == len(expected), "ZIP exact file-set mismatch")
        require(sum(info.file_size for info in infos) <= limits.total_bytes, "ZIP total size limit")
        for info in infos:
            require(time.monotonic() - start <= limits.seconds, "ZIP time limit")
            name = safe_name(info.filename, limits)
            require(info.orig_filename == info.filename, "ZIP NUL-truncated name")
            require(name.casefold() not in seen, "duplicate/case-alias ZIP member")
            seen.add(name.casefold())
            require(name in expected, "unexpected ZIP member")
            mode = info.external_attr >> 16
            require(stat.S_IFMT(mode) in {0, stat.S_IFREG}, "ZIP nonregular/symlink member")
            require(not info.flag_bits & 1, "encrypted ZIP member")
            require(info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, "unsupported ZIP compression")
            require(info.file_size == expected[name]["bytes"] and info.file_size <= limits.file_bytes, "ZIP member length mismatch")
            require(info.file_size <= max(info.compress_size, 1) * limits.ratio, "ZIP ratio limit")
            chunks, total = [], 0
            with archive.open(info) as stream:
                while chunk := stream.read(64 * 1024):
                    total += len(chunk)
                    require(total <= expected[name]["bytes"], "ZIP stream size limit")
                    require(time.monotonic() - start <= limits.seconds, "ZIP time limit")
                    chunks.append(chunk)
            content = b"".join(chunks)
            require(identity(content) == expected[name], "ZIP member hash mismatch")
            if name.endswith(".json"):
                strict_json(content, limits)
            elif name.endswith(".jsonl"):
                records(content, limits)
            payload[name] = content
    require(set(payload) == set(expected), "ZIP missing required members")
    return payload


def review_candidate_metadata(result, *, manifest, candidates, table, raw, ready, policy, zip_path, limits):
    """Review heterogeneous public proposals without accepting their contracts.

    This mode is deliberately unable to return RECEIVED. B002 introduces other
    candidate shapes; checking shared metadata does not establish their private
    record/value/reference semantics or silently adapt them to the B001 importer.
    """
    unknown_records, schemas, contract_issues, summaries = set(), {}, [], []
    expected_paths = policy.get("expected_hashes_by_path", {})
    for row in candidates:
        cid = row["candidate_id"]
        schema = row.get("schema") or "UNDECLARED"
        schemas[schema] = schemas.get(schema, 0) + 1
        require(row.get("selected_for_build") is False, "candidate already marked adopted")
        require(row.get("global_default_selected", False) is False, "candidate selects global profile")
        require(row.get("profile_id") in policy["profiles"], "candidate profile mismatch")
        require(bool(row.get("codex_tests")) and bool(row.get("field")), "candidate observations/field missing")
        require(bool(row.get("binding_ids")) and set(row["binding_ids"]) <= set(policy["valid_binding_ids"]), "candidate unknown binding")
        require(bool(row.get("requirement_ids")) and set(row["requirement_ids"]) <= set(policy["valid_requirement_ids"]), "candidate unknown requirement")
        for key in ("base_p1_5_sha", "baseline_p1_5_sha"):
            if key in row:
                require(row[key] == policy["base_p1_5_sha"], "candidate baseline conflict")
        if "baseline_input_manifest_sha256" in row:
            require(row["baseline_input_manifest_sha256"] == policy["input_manifest_sha256"], "candidate manifest conflict")
        if "task_id" in row:
            require(row["task_id"] == manifest["task_id"], "candidate task conflict")
        refs = row.get("existing_record_ids")
        require(isinstance(refs, list) and len(refs) == len(set(refs)), "missing/duplicate original record reference list")
        unknown_records |= set(refs) - set(policy.get("verified_record_ids", []))
        require(isinstance(row.get("payload_refs"), list) and set(row["payload_refs"]) <= table.keys(), "candidate missing payload reference")
        for evidence in row.get("evidence_refs", []):
            name = evidence["path"]
            require(name in table and {k: evidence[k] for k in ("bytes", "sha256")} == table[name], "candidate evidence identity conflict")
        if "private_value" in row:
            value = row["private_value"]
            require(value["path"] in table and value["candidate_id"] == cid, "candidate private record locator conflict")
            require(re.fullmatch("[a-f0-9]{64}", value["record_canonical_sha256"]), "candidate private record hash invalid")
        if "private_record_locator" in row:
            name, _, record = row["private_record_locator"].partition("#")
            require(name in table and record == cid, "candidate semantic record locator conflict")
            require(row["private_semantic_file_sha256"] == table[name]["sha256"], "candidate semantic identity conflict")
        old = row.get("old_value_or_hash")
        if isinstance(old, dict):
            if "base_manifest_sha256" in old:
                require(old["base_manifest_sha256"] == policy["input_manifest_sha256"], "candidate prior manifest conflict")
            for name, expected in old.get("expected_input_hashes", {}).items():
                require(name in expected_paths and expected == expected_paths[name], "candidate prior input hash conflict")
        else:
            contract_issues.append({"candidate_id": cid, "issue": "expected existing value/hash contract is absent"})
        summaries.append({"candidate_id": cid, "field": row["field"], "profile_id": row["profile_id"],
                          "original_record_references": len(refs), "status": "DEFERRED"})
    result.update({"review_mode": "METADATA_ONLY_NO_RECEIPT", "metadata_result": "PASS",
                   "candidate_metadata_result": "PASS_SHARED_FIELDS_AND_DECLARED_LOCATORS_ONLY",
                   "candidate_reference_contract_result": "NOT_RUN_HETEROGENEOUS_PRIVATE_REFERENCE_CONTRACTS",
                   "candidate_schema_counts": schemas, "candidate_contract_issues": contract_issues,
                   "candidate_checks": summaries, "zip_identity": ready, "payload_manifest_files": len(table),
                   "accessible_payload_files": ["FIELD_CANDIDATES.jsonl"],
                   "unverified_original_record_ids": sorted(unknown_records)})
    if zip_path is None or not Path(zip_path).exists():
        result["private_payload_result"] = "NOT_RUN_MISSING_BYTES"
        result["missing_private_files"] = [name for name in table if name != "FIELD_CANDIDATES.jsonl"]
        result["blockers"].append("Original private batch ZIP is not available at an explicit local path; Library ID is not bytes.")
    else:
        inspect_zip(zip_path, {k: ready[k] for k in ("bytes", "sha256")}, table, raw["manifest"], raw["validation"], limits)
        result["private_payload_result"] = "PASS_BYTES_AND_FORMATS_ONLY"
        result["accessible_payload_files"] = list(table)
    result["blockers"].append("Metadata-only review cannot establish receipt; heterogeneous private record/value/source dependency contracts need a separate complete validation.")
    if unknown_records:
        result["blockers"].append("Original selected record bytes are required to validate the reference closure.")
    if manifest["dependencies"] != policy.get("verified_dependencies", []):
        result["blockers"].append("Frozen dependency private bytes/G0 scope are not verified in this receiver.")
    result["status"] = "DEFERRED"
    return result


def review(*, manifest_path, ready_path, validation_path, candidates_path, policy, zip_path=None, limits=Limits()):
    result = {"schema": "baram.p2.work_batch_review/1", "status": "REJECTED",
              "metadata_result": "NOT_RUN", "private_payload_result": "NOT_RUN",
              "adoption": "NOT_STARTED", "adopted_fields": [], "exercised_fields": [],
              "errors": [], "blockers": [], "batch_id": policy.get("batch_id"),
              "work_commit": policy.get("work_commit"), "historical_accuracy": "NOT_ASSESSED",
              "runtime": "NOT_RUN"}
    try:
        raw = {name: regular_bytes(path, limits.file_bytes) for name, path in {
            "manifest": manifest_path, "ready": ready_path,
            "validation": validation_path, "candidates": candidates_path}.items()}
        require(set(policy["snapshot_files"]) == set(raw), "metadata pin set mismatch")
        result["metadata_files"] = {name: identity(data) for name, data in raw.items()}
        for name, data in raw.items():
            require(identity(data) == policy["snapshot_files"][name], "metadata length/hash mismatch: " + name)
        manifest = strict_json(raw["manifest"], limits)
        validation = strict_json(raw["validation"], limits)
        candidates = records(raw["candidates"], limits)
        ready = parse_ready(raw["ready"])
        require(re.fullmatch("[a-f0-9]{40}", policy["work_commit"]), "unpinned Work commit")
        for key, expected in {
            "schema": "baram.work_source_delta.batch/1", "batch_id": policy["batch_id"],
            "task_id": "BARAM_REBUILD_WORK_SOURCE_DELTA_001",
            "base_p1_5_sha": policy["base_p1_5_sha"],
            "input_manifest_sha256": policy["input_manifest_sha256"],
            "profiles": policy["profiles"], "dependencies": policy["dependencies"],
            "supersedes": policy["supersedes"],
            "profile_dispatch_required": True, "default_build_profile_id": None,
        }.items():
            require(manifest.get(key) == expected, "manifest pin/profile/dependency conflict: " + key)
        require(ready == policy["zip"], "READY identity differs from independent pin")
        table = file_table(manifest, limits)
        require(identity(raw["candidates"]) == table["FIELD_CANDIDATES.jsonl"], "public candidate bytes differ from batch")
        require(validation.get("schema") == "baram.work_source_delta.validation/1", "validation schema")
        require(validation.get("result") == "PASS" and not validation.get("errors"), "Work validation failure")
        require(validation.get("files_checked") == len(table), "Work file count differs from manifest")
        require(set(manifest["valid_binding_ids"]) == set(policy["valid_binding_ids"]), "binding ledger mismatch")
        require(set(manifest["affected_bindings"]) <= set(policy["valid_binding_ids"]), "unknown affected binding")
        require(len({r["candidate_id"] for r in candidates}) == len(candidates) > 0, "empty/duplicate candidates")
        require({r["candidate_id"] for r in candidates} == set(manifest["candidate_ids"]), "candidate ID set mismatch")
        mode = policy.get("review_mode", "full_receipt")
        require(mode in {"full_receipt", "metadata_only"}, "unknown review mode")
        if mode == "metadata_only":
            return review_candidate_metadata(result, manifest=manifest, candidates=candidates, table=table,
                                             raw=raw, ready=ready, policy=policy, zip_path=zip_path, limits=limits)
        unknown_records, unknown_hashes, summaries = set(), set(), []
        for row in candidates:
            cid = row["candidate_id"]
            require(row.get("schema") == "baram-work-field-candidate-v1", "candidate schema")
            require(row.get("task_id") == manifest["task_id"] and row.get("base_p1_5_sha") == policy["base_p1_5_sha"], "candidate baseline")
            require(row.get("profile_id") in policy["profiles"], "candidate profile mismatch")
            require(row.get("selected_for_build") is False, "candidate already marked adopted")
            require(bool(row.get("codex_tests")), "candidate missing required observations")
            require(bool(row.get("binding_ids")) and set(row["binding_ids"]) <= set(policy["valid_binding_ids"]), "candidate unknown binding")
            require(bool(row.get("requirement_ids")) and set(row["requirement_ids"]) <= set(policy["valid_requirement_ids"]), "candidate unknown requirement")
            require(bool(row.get("payload_refs")) and set(row["payload_refs"]) <= table.keys(), "candidate missing payload reference")
            source = row["source_locator"]["private_file"]
            require(source["relative_private_path"] in row["payload_refs"], "candidate locator not referenced")
            require({k: source[k] for k in ("bytes", "sha256")} == table[source["relative_private_path"]], "candidate source identity conflict")
            current = row.get("old_value_or_hash")
            require(isinstance(current, dict) and "old_value" in current, "candidate lacks expected existing value")
            prior_hashes = {value for key, value in current.items() if key.endswith("sha256")}
            require(bool(prior_hashes) and prior_hashes <= set(policy["declared_prior_hashes"]), "prior input hash conflict")
            unknown_hashes |= prior_hashes - set(policy.get("verified_prior_hashes", []))
            refs = row.get("existing_record_ids", [])
            require(bool(refs) and len(refs) == len(set(refs)), "missing/duplicate original record references")
            unknown_records |= set(refs) - set(policy.get("verified_record_ids", []))
            summaries.append({"candidate_id": cid, "field": row["field"], "profile_id": row["profile_id"],
                              "original_record_references": len(refs), "status": "DEFERRED"})
        result["candidate_checks"] = summaries
        result["zip_identity"] = ready
        result["metadata_result"] = "PASS"
        result["payload_manifest_files"] = len(table)
        result["accessible_payload_files"] = ["FIELD_CANDIDATES.jsonl"]
        if zip_path is None or not Path(zip_path).exists():
            result["private_payload_result"] = "NOT_RUN_MISSING_BYTES"
            result["blockers"].append("Original private batch ZIP is not available at an explicit local path; Library ID is not bytes.")
            result["missing_private_files"] = [name for name in table if name != "FIELD_CANDIDATES.jsonl"]
        else:
            payload = inspect_zip(zip_path, {k: ready[k] for k in ("bytes", "sha256")}, table, raw["manifest"], raw["validation"], limits)
            require(payload["FIELD_CANDIDATES.jsonl"] == raw["candidates"], "archive candidate identity differs")
            sources = records(payload["SOURCES.jsonl"], limits)
            require(bool(sources), "empty source records")
            require(len({source["source_id"] for source in sources}) == len(sources), "duplicate source IDs")
            for source in sources:
                locator = source["private_file"]
                name = locator["relative_private_path"]
                require(name in table and {k: locator[k] for k in ("bytes", "sha256")} == table[name], "source payload locator conflict")
                hashes = source["input_source_sha256"]
                require(isinstance(hashes, dict) and bool(hashes), "source input identities missing")
                require(set(hashes.values()) <= set(policy["declared_prior_hashes"]), "source prior input hash conflict")
                unknown_hashes |= set(hashes.values()) - set(policy.get("verified_prior_hashes", []))
            result["private_payload_result"] = "PASS_BYTES_AND_FORMATS"
            result["accessible_payload_files"] = list(table)
        if unknown_records:
            result["unverified_original_record_ids"] = sorted(unknown_records)
            result["blockers"].append("Original selected record bytes are required to validate the reference closure.")
        if unknown_hashes:
            result["unverified_prior_hashes"] = sorted(unknown_hashes)
            result["blockers"].append("Catalog/prior-report hash declarations match, but required old input bytes are not verified.")
        if manifest["dependencies"] != policy.get("verified_dependencies", []):
            result["blockers"].append("Frozen dependency private bytes/G0 scope are not verified in this receiver.")
        result["status"] = "DEFERRED" if result["blockers"] else "RECEIVED"
        for summary in summaries:
            summary["status"] = result["status"]
    except (Rejected, OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError, zipfile.BadZipFile, RuntimeError) as exc:
        result["errors"].append(str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "ready", "validation", "candidates", "policy"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--zip", type=Path, help="Explicit existing private ZIP; never downloaded or searched")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    policy = strict_json(regular_bytes(args.policy, Limits().file_bytes), Limits())
    result = review(manifest_path=args.manifest, ready_path=args.ready, validation_path=args.validation,
                    candidates_path=args.candidates, policy=policy, zip_path=args.zip)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return {"RECEIVED": 0, "REJECTED": 1, "DEFERRED": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
