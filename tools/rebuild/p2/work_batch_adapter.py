#!/usr/bin/env python3
"""Read immutable Work B001/B002 bytes into a new, private observation generation.

This adapter does not patch game data. It accepts heterogeneous published shapes,
checks their actual normalized/source references, and may select named *guards*
for an inspection run. Selection never establishes historical/runtime completion.
The old Codex receiver and its DEFERRED records remain unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from receive_work_batch import (Limits, Rejected, file_table, identity, inspect_zip,
                                records, regular_bytes, require, strict_json)

P1_SHA = "590bd626b63cebf6d858c8e9c1c9ce822ea0ec94"
P1_MANIFEST = "124573e4a57d7ff759501315bf9a101fcd8a3959944f25006120b3e14c02a1d5"
CORE = {"bytes": 28665916, "sha256": "f9fa57ea09f2755d5038cb7208258e3c5b44f6dddea77ebf66dfd6129ef8233c"}
PINS = {
    "B001": {"bytes": 19352, "sha256": "b61c169c899853c0a90849f81174d76c8503e6827ef3244ca489aff2b721e6af"},
    "B002": {"bytes": 613492, "sha256": "dc87687e7260ee4f0c3777bbb46559a67be64f7050195baf6650a29d1c068aee"},
}
GUARDS = {"WD-MS-001", "WD-MS-002", "WD-MS-003", "WD-MS-004", "WD-MS-005", "WD-MN-001"}
LIMITS = Limits()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def row_id(row):
    return row.get("candidate_id", row.get("record_id", row.get("id", row.get("content_id"))))


def row_index(data, name):
    value = records(data, LIMITS) if name.endswith(".jsonl") else strict_json(data, LIMITS)
    rows = value.get("records", []) if isinstance(value, dict) else value
    require(isinstance(rows, list), "record container must be a list: " + name)
    result = {}
    for row in rows:
        if isinstance(row, dict) and row_id(row):
            require(row_id(row) not in result, "duplicate record identity: " + name)
            result[row_id(row)] = row
    return result


def sha_strings(value):
    if isinstance(value, str):
        return [value]
    return value if isinstance(value, list) else []


class Core:
    """Only explicit, pinned core ZIP members are opened; no cached path trust."""
    def __init__(self, path):
        raw = regular_bytes(path, 32 * 1024 * 1024)
        require(identity(raw) == CORE, "P1.5 core v1 length/hash mismatch")
        self.archive = zipfile.ZipFile(io.BytesIO(raw))
        self.table = {row["path"]: row for row in strict_json(self.archive.read("PACKAGE_MANIFEST.json"), LIMITS)["files"]}
        self.by_hash = {row["sha256"]: path for path, row in self.table.items()}
        self.cache = {}
        baseline = self.read("docs/rebuild/p1_5/INPUT_MANIFEST.json")
        require(identity(baseline)["sha256"] == P1_MANIFEST, "P1.5 INPUT_MANIFEST mismatch")
        self.bindings = {row["binding_id"] for row in records(self.read("docs/rebuild/p1_5/field_bindings.jsonl"), LIMITS)}
        self.requirements = {row["requirement_id"] for row in csv.DictReader(io.StringIO(self.read("docs/rebuild/p1_5/requirements_delta.csv").decode("utf-8-sig")))}
        self.known = {}
        self.normalized_hashes = {}
        catalog = strict_json(self.read("docs/rebuild/p1_5/selected_content/catalog.json"), LIMITS)
        for entry in catalog["normalized_catalogs"]:
            name = "docs/rebuild/p1_5/selected_content/" + Path(entry["path"]).name
            data = self.read(name)
            require(identity(data) == {k: entry[k] for k in ("bytes", "sha256")}, "normalized catalog mismatch: " + name)
            self.normalized_hashes[Path(name).name] = entry["sha256"]
            if name.endswith(".jsonl"):
                for key, value in row_index(data, name).items():
                    require(key not in self.known, "duplicate normalized ID: " + key)
                    self.known[key] = value

    def read(self, name):
        if name not in self.cache:
            require(name in self.table, "core member absent from pinned manifest: " + name)
            declared = self.table[name]
            require(declared["bytes"] <= 64 * 1024 * 1024, "core member read limit")
            data = self.archive.read(name)
            require(identity(data) == {k: declared[k] for k in ("bytes", "sha256")}, "core member length/hash mismatch: " + name)
            self.cache[name] = data
        return self.cache[name]

    def by_sha(self, digest):
        if digest not in self.by_hash:
            return None
        return self.read(self.by_hash[digest])


def shape(row):
    if "private_value" in row:
        return "private_candidate_record_v1"
    if "private_record_locator" in row:
        return "private_semantic_locator_v1"
    if row.get("schema") == "baram-work-field-candidate-v1":
        return "motion_private_record_locator_v1"
    if row.get("profile_id") == "NA_REFERENCE_ONLY":
        return "na_reference_observation_v1"
    return "inline_document_observation_v1"


def adapt(path, core, selected):
    raw = regular_bytes(path, LIMITS.archive_bytes)
    # Reject an unpinned compressed stream before opening even its manifest.
    # The fixed byte identity bounds all later decompression to reviewed inputs.
    require(identity(raw) in PINS.values(), "batch ZIP fixed identity mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest_bytes = archive.read("MANIFEST.json")
        validation_bytes = archive.read("VALIDATION.json")
    manifest = strict_json(manifest_bytes, LIMITS)
    batch_id = manifest["batch_id"]
    require(batch_id in PINS and identity(raw) == PINS[batch_id], "batch ZIP fixed identity mismatch")
    require(manifest["base_p1_5_sha"] == P1_SHA and manifest["input_manifest_sha256"] == P1_MANIFEST, "batch baseline mismatch")
    require(manifest["dependencies"] == [{"kind": "frozen_P1_5", "sha": P1_SHA,
            "core_library_id": "libfile_5625c3d22e548191bb3c06296c42bf6c", "core_version": 1,
            "core_sha256": CORE["sha256"]}], "batch frozen core dependency mismatch")
    require(manifest["profile_dispatch_required"] is True and manifest["default_build_profile_id"] is None, "global profile selection forbidden")
    validation = strict_json(validation_bytes, LIMITS)
    require(validation["result"] == "PASS" and not validation["errors"], "published batch validation failed")
    table = file_table(manifest, LIMITS)
    payload = inspect_zip(path, PINS[batch_id], table, manifest_bytes, validation_bytes, LIMITS)
    candidates = records(payload["FIELD_CANDIDATES.jsonl"], LIMITS)
    require(len(candidates) > 0 and len({row["candidate_id"] for row in candidates}) == len(candidates), "empty/duplicate candidates")
    require({row["candidate_id"] for row in candidates} == set(manifest["candidate_ids"]), "candidate set mismatch")
    sources = records(payload["SOURCES.jsonl"], LIMITS)
    require(sources and len({row["source_id"] for row in sources}) == len(sources), "empty/duplicate source IDs")
    payload_by_hash = {identity(data)["sha256"]: data for data in payload.values()}
    parsed = {}
    ledgers, observations = [], []

    # SOURCES describes both original bytes and derived analyses. Validate the
    # bytes it names, without treating a derivative as a second primary source.
    for source in sources:
        for digest in source.get("input_source_sha256", {}).values():
            require(digest in payload_by_hash or core.by_sha(digest) is not None,
                    "source record prior bytes unavailable: " + source["source_id"])
        if "private_file" in source:
            loc = source["private_file"]
            require(identity(payload[loc["relative_private_path"]]) == {k: loc[k] for k in ("bytes", "sha256")},
                    "source record private identity mismatch: " + source["source_id"])
        elif source.get("sha256"):
            data = payload_by_hash.get(source["sha256"])
            if data is None:
                data = core.by_sha(source["sha256"])
            require(data is not None, "source record bytes unavailable: " + source["source_id"])
            if "bytes" in source:
                require(len(data) == source["bytes"], "source record length mismatch: " + source["source_id"])

    def get_rows(name):
        require(name in payload, "missing private record payload: " + name)
        if name not in parsed:
            parsed[name] = row_index(payload[name], name)
        return parsed[name]

    def require_source(digest):
        return digest in payload_by_hash or core.by_sha(digest) is not None

    for row in candidates:
        cid = row["candidate_id"]
        require(row["selected_for_build"] is False and not row.get("global_default_selected", False), "issued candidate already mutates active profile")
        require(row["profile_id"] in manifest["profiles"], "profile not declared: " + cid)
        require(bool(row["binding_ids"]) and set(row["binding_ids"]) <= core.bindings, "unknown binding: " + cid)
        require(bool(row["requirement_ids"]) and set(row["requirement_ids"]) <= core.requirements, "unknown requirement: " + cid)
        require(bool(row.get("codex_tests")), "required observations absent: " + cid)
        require(set(row.get("payload_refs", [])) <= set(payload), "payload reference missing: " + cid)
        refs = row.get("existing_record_ids", [])
        require(len(refs) == len(set(refs)) and set(refs) <= core.known.keys(), "unknown/duplicate original normalized reference: " + cid)
        private = None
        if "private_value" in row:
            loc = row["private_value"]
            private = get_rows(loc["path"])[loc["candidate_id"]]
            require(loc["candidate_id"] == cid and canonical_hash(private) == loc["record_canonical_sha256"], "private candidate record mismatch: " + cid)
        if "private_record_locator" in row:
            name, rid = row["private_record_locator"].split("#", 1)
            require(identity(payload[name])["sha256"] == row["private_semantic_file_sha256"], "semantic payload hash mismatch: " + cid)
            private = get_rows(name)[rid]
            require(rid == cid, "semantic record ID mismatch: " + cid)
        loc = row.get("source_locator", {})
        if isinstance(loc, dict) and "private_file" in loc:
            source = loc["private_file"]
            name = source["relative_private_path"]
            require(identity(payload[name]) == {k: source[k] for k in ("bytes", "sha256")}, "private source length/hash mismatch: " + cid)
            needed = loc.get("records", [loc["record_id"]] if "record_id" in loc else [])
            require(bool(needed) and set(needed) <= get_rows(name).keys(), "private source record missing: " + cid)
        for evidence in row.get("evidence_refs", []):
            require(identity(payload[evidence["path"]]) == {k: evidence[k] for k in ("bytes", "sha256")}, "evidence mismatch: " + cid)
        for evidence in row.get("source_evidence", []):
            normalized = evidence.get("normalized_locator")
            if normalized:
                name = "docs/rebuild/p1_5/" + normalized["path"]
                data = core.read(name)
                require(identity(data)["sha256"] == normalized["file_sha256"], "normalized source file mismatch: " + cid)
                source_row = strict_json(data.splitlines()[normalized["line"] - 1], LIMITS)
                require(row_id(source_row) == evidence["content_id"] and canonical_hash(source_row) == normalized["record_canonical_sha256"], "normalized source row mismatch: " + cid)
        old = row.get("old_value_or_hash")
        if row.get("expected_existing_record_sha256"):
            require(canonical_hash(core.known[row["content_id"]]) == row["expected_existing_record_sha256"], "existing record changed: " + cid)
        prior_hashes = []
        if isinstance(old, dict):
            if "base_manifest_sha256" in old:
                require(old["base_manifest_sha256"] == P1_MANIFEST, "prior baseline changed: " + cid)
            for name, digest in old.get("expected_input_hashes", {}).items():
                require(core.normalized_hashes.get(Path(name).name) == digest, "prior normalized input changed: " + cid)
            prior_hashes = [v for k, v in old.items() if k.endswith("sha256") and isinstance(v, str) and k not in {"record_canonical_sha256", "base_manifest_sha256"}]
            require(all(require_source(digest) for digest in prior_hashes), "prior source bytes unavailable: " + cid)
        source_hashes = sha_strings(row.get("source_sha256"))
        missing_sources = [digest for digest in source_hashes if not require_source(digest)]
        chosen = cid in selected
        require(not chosen or cid in GUARDS, "this adapter only selects explicit inspection guards")
        require(not chosen or not missing_sources, "selected guard has missing source bytes: " + cid)
        reasons = []
        if not isinstance(old, dict):
            reasons.append("MISSING_EXPECTED_OLD_CONTRACT_OBSERVATION_ONLY")
        if row["profile_id"] == "NA_REFERENCE_ONLY":
            reasons.append("NA_REFERENCE_ONLY_PRESERVE_SOURCE_FAIL154")
        if row.get("certainty") == "LOCATION_INFERENCE":
            reasons.append("NPC_LOCATION_HYPOTHESIS_NOT_NATIVE_ROLE")
        if missing_sources:
            reasons.append("DECLARED_SOURCE_BYTES_NOT_IN_CORE_OR_BATCH")
        result = {"schema": "baram.work.p2.batch_adoption/1", "generation": "WORK-P2-BATCH-OBSERVATIONS-v1", "batch_id": batch_id,
                  "candidate_id": cid, "field": row["field"], "profile_id": row["profile_id"],
                  "source_shape": shape(row), "issued_schema": row.get("schema", "UNDECLARED"),
                  "zip_sha256": PINS[batch_id]["sha256"], "received": True,
                  "bytes_and_declared_record_validation": "PASS", "source_closure": "PASS_DECLARED_TOP_LEVEL" if not missing_sources else "PARTIAL",
                  "recursive_runtime_dependency_closure": "NOT_ASSESSED_BY_ADAPTER",
                  "normalized_record_references_verified": len(refs), "P2_selection": "INSPECTION_GUARD" if chosen else "OBSERVATION_REFERENCE_ONLY",
                  "runtime_consumption": "NOT_RUN", "data_patch_applied": False,
                  "historical_default_selected": False, "historical_accuracy": "NOT_ESTABLISHED",
                  "deferred_reasons": reasons, "missing_source_hashes": missing_sources}
        ledgers.append(result)
        observations.append({**result, "candidate_value": row.get("candidate_value", private.get("candidate_value") if private else None),
                             "confirmed_scope": row.get("confirmed_scope"), "remaining_unknowns": row.get("remaining_unknowns"),
                             "private_record": private, "required_observations": row["codex_tests"]})
    return ledgers, observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-zip", type=Path, required=True)
    parser.add_argument("--batch-zip", type=Path, action="append", required=True)
    parser.add_argument("--select-guard", action="append", default=[])
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    require(not args.private_output.exists() and not args.ledger.exists(), "new generation outputs must not overwrite prior results")
    require(not args.private_output.resolve().is_relative_to(Path(__file__).resolve().parents[3]),
            "private observations must stay outside the public source checkout")
    core = Core(args.core_zip)
    ledgers, observations = [], []
    for path in args.batch_zip:
        ledger, observation = adapt(path, core, set(args.select_guard))
        ledgers += ledger
        observations += observation
    require(set(args.select_guard) <= {row["candidate_id"] for row in ledgers}, "selected guard absent")
    require(len(ledgers) == len({row["candidate_id"] for row in ledgers}), "duplicate batch input")
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps({"schema": "baram.work.p2.private_batch_observations/1", "source_p1_5_manifest_sha256": P1_MANIFEST,
                                               "adapter_sha256": identity(Path(__file__).read_bytes())["sha256"], "observations": observations}, ensure_ascii=False, indent=2) + "\n")
    args.private_output.chmod(0o600)
    args.ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledgers))
    print(json.dumps({"received_candidates": len(ledgers), "selected_guards": args.select_guard,
                      "source_closure_partial": sum(row["source_closure"] == "PARTIAL" for row in ledgers),
                      "runtime_exercised": 0, "data_patches": 0, "ledger_sha256": identity(args.ledger.read_bytes())["sha256"]}))


if __name__ == "__main__":
    try:
        main()
    except (Rejected, OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc)}))
        raise SystemExit(1)
