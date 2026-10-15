#!/usr/bin/env python3
"""Execute fail-closed validator cases in isolated copies, never original inputs."""
from __future__ import annotations
import argparse
import csv
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools/rebuild/step01/validate_step01.py"
spec = importlib.util.spec_from_file_location("static_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def fixture(base):
    base.mkdir()
    (base / "source.json").write_text('{"client_build":"KR-fixture-1","items":[1,2]}\n')
    (base / "source.csv").write_text('item_id,name\n1,fixture\n')
    with zipfile.ZipFile(base / "source.zip", "w") as z:
        z.writestr("folder/document.txt", "synthetic fixture bytes only")
    inputs = []
    for ext in ("json", "csv", "zip"):
        data = (base / ("source." + ext)).read_bytes()
        inputs.append({"input_id": "FIXTURE-" + ext.upper(), "path": "source." + ext, "sha256": gate.sha(data), "size_bytes": len(data), "format": ext, "require_format_validation": True})
    inputs[0]["expected_fields"] = {"client_build": "KR-fixture-1"}
    inputs[1]["required_columns"] = ["item_id", "name"]
    contract = {"schema_version": 2, "validator_version": gate.VERSION, "parser_version": gate.PARSER_VERSION,
                "validator_sha256": gate.sha(SCRIPT.read_bytes()), "config_sha256": gate.fingerprint(gate.CONFIG), "inputs": inputs}
    write_json(base / "contract.json", contract)
    return contract


def refreshed(base, contract, ext):
    data = (base / ("source." + ext)).read_bytes()
    row = next(x for x in contract["inputs"] if x["format"] == ext)
    row.update(sha256=gate.sha(data), size_bytes=len(data))


def run_case(base, name, expected, args, checks=None, expected_scope=None):
    result_file = base / "result.json"
    cmd = [sys.executable, str(SCRIPT)] + list(args) + ["--output", str(result_file)]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    observed = json.loads(result_file.read_text()) if result_file.is_file() else {}
    must = {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_RUN": 3}[expected]
    reasons = [c["check_id"] for c in observed.get("checks", []) if c["result"] in ("FAIL", "BLOCKED", "NOT_RUN")]
    assertions = {"overall_status": observed.get("result") == expected, "exit_propagation": proc.returncode == must == observed.get("exit_code"),
                  "no_runtime_claim": observed.get("runtime_tests") == "NOT_RUN" and observed.get("p2_tests") == "NOT_RUN"}
    if checks:
        assertions["required_check_evidence"] = set(checks) <= set(reasons)
    if expected_scope:
        assertions["scoped_vs_overall"] = observed.get("scoped_result", {}).get("result") == expected_scope
    return {"case_id": name, "input_origin": "SYNTHETIC_FIXTURE" if "--contract" in args else "ISOLATED_REPO_METADATA_COPY", "expected": expected,
            "observed": observed.get("result"), "exit_code": proc.returncode, "assertions": assertions, "result": "PASS" if all(assertions.values()) else "FAIL",
            "command": cmd, "summary_stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "non_pass_checks": reasons,
            "metadata_result": observed.get("metadata_result"), "checked": sum(x.get("read", False) for x in observed.get("inputs", [])),
            "failure_inputs": [{"input_id": x["input_id"], "result": x["result"], "reasons": x.get("reasons"), "reason": x.get("reason")} for x in observed.get("inputs", []) if x["result"] == "FAIL"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=ROOT / "docs/rebuild/p1_5/validator_regression.json")
    args = ap.parse_args()
    hist = ROOT / "docs/rebuild/step01/VALIDATION.json"
    historic_sha = gate.sha(hist.read_bytes())
    cases = []
    with tempfile.TemporaryDirectory(prefix="baram-validator-") as temp:
        work = Path(temp)
        names = ["normal_complete", "zero_available", "missing_one", "byte_tamper", "truncated_zip", "html_saved_as_zip", "malformed_json", "malformed_csv", "duplicate_input_id", "missing_input_id", "wrong_client_version", "wrong_parser", "wrong_config_fingerprint", "wrong_validator_code_fingerprint", "required_unsupported_format", "scope_cannot_hide_missing", "empty_required_set", "archive_path_escape"]
        for name in names:
            base = work / name
            contract = fixture(base)
            expected = "FAIL"; expected_scope = None
            if name == "normal_complete": expected = "PASS"
            elif name == "zero_available":
                for ext in ("json", "csv", "zip"): (base / ("source." + ext)).unlink()
                expected = "BLOCKED"
            elif name in ("missing_one", "scope_cannot_hide_missing"):
                (base / "source.zip").unlink(); expected = "BLOCKED"
                if name == "scope_cannot_hide_missing": expected_scope = "PASS"
            elif name == "byte_tamper":
                (base / "source.json").write_bytes((base / "source.json").read_bytes().replace(b"[1,2]", b"[1,3]"))
            elif name == "truncated_zip":
                (base / "source.zip").write_bytes((base / "source.zip").read_bytes()[:20])
                refreshed(base, contract, "zip")  # isolate format rejection even if producer hashes truncated bytes
            elif name == "html_saved_as_zip":
                (base / "source.zip").write_text("<!DOCTYPE html><html>Access denied</html>")
                refreshed(base, contract, "zip")
            elif name == "malformed_json":
                (base / "source.json").write_text('{"client_build":')
                refreshed(base, contract, "json")
            elif name == "malformed_csv":
                (base / "source.csv").write_text('item_id,name\n1,fixture,extra\n')
                refreshed(base, contract, "csv")
            elif name == "duplicate_input_id": contract["inputs"].append(dict(contract["inputs"][0]))
            elif name == "missing_input_id": contract["inputs"][0].pop("input_id")
            elif name == "wrong_client_version":
                (base / "source.json").write_text('{"client_build":"NA-other-version","items":[1,2]}')
                refreshed(base, contract, "json")
            elif name == "wrong_parser": contract["parser_version"] = "wrong-parser/0"
            elif name == "wrong_config_fingerprint": contract["config_sha256"] = "0" * 64
            elif name == "wrong_validator_code_fingerprint": contract["validator_sha256"] = "0" * 64
            elif name == "required_unsupported_format":
                contract["inputs"][2]["format"] = "unsupported-format"; expected = "NOT_RUN"
            elif name == "empty_required_set": contract["inputs"] = []
            elif name == "archive_path_escape":
                with zipfile.ZipFile(base / "source.zip", "w") as z: z.writestr("../escape.txt", "fixture")
                refreshed(base, contract, "zip")
            write_json(base / "contract.json", contract)
            argv = ["--contract", str(base / "contract.json")]
            if expected_scope: argv += ["--scope-input", "FIXTURE-JSON"]
            cases.append(run_case(base, name, expected, argv, expected_scope=expected_scope))
        # Real metadata structures copied; all original byte paths replaced with
        # nonexistent fixture paths. Mutations can only affect these copies.
        for name in ("duplicate_requirement_id", "broken_source_reference", "malformed_ledger_json", "missing_required_metadata", "missing_sources_ledger"):
            base = work / name; (base / "docs/rebuild").mkdir(parents=True)
            shutil.copytree(ROOT / "docs/rebuild/step01", base / "docs/rebuild/step01")
            shutil.copy(ROOT / "docs/rebuild/STATE.json", base / "docs/rebuild/STATE.json")
            shutil.copy(ROOT / "AGENTS.md", base / "AGENTS.md")
            out = base / "docs/rebuild/step01"
            local_gate = gate.Gate(); inputs, _ = gate.ledger_inputs(local_gate, out)
            mapping = {x["input_id"]: str(base / "missing" / str(i)) for i, x in enumerate(inputs)}
            write_json(base / "map.json", mapping)
            expected = "FAIL"; checks = None
            if name == "duplicate_requirement_id":
                path = out / "requirements.csv"
                rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
                rows.append(dict(rows[0]))
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
                checks = ["unique_requirements_ids"]
            elif name == "broken_source_reference":
                path = out / "field_bindings.jsonl"
                rows = [json.loads(x) for x in path.read_text().splitlines()]
                rows[0]["source_ids"].append("NONEXISTENT-FIXTURE-SOURCE")
                path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
                checks = ["all_source_requirement_member_refs"]
            elif name == "malformed_ledger_json":
                (out / "sources.jsonl").write_text('{not json}\n')
                # No byte set can be derived; unknown relocation keys would be a
                # separate FAIL, so do not use the map in this syntax test.
            elif name == "missing_required_metadata":
                (out / "requirements.csv").unlink(); expected = "BLOCKED"
                checks = ["required_deliverables", "metadata:requirements.csv"]
            elif name == "missing_sources_ledger":
                (out / "sources.jsonl").unlink(); expected = "BLOCKED"
                checks = ["required_deliverables", "metadata:sources.jsonl"]
            argv = ["--root", str(base)]
            if name not in ("malformed_ledger_json", "missing_sources_ledger"): argv += ["--input-map", str(base / "map.json")]
            cases.append(run_case(base, name, expected, argv, checks=checks))
        real = work / "actual_repo"; real.mkdir()
        actual_cmd = [sys.executable, str(SCRIPT), "--output", str(real / "result.json")]
        actual_proc = subprocess.run(actual_cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        actual = json.loads((real / "result.json").read_text())
        actual_summary = {"input_origin": "ACTUAL_REPOSITORY_METADATA_AND_ACCESSIBLE_LEDGER_PATHS", "result": actual["result"], "metadata_result": actual["metadata_result"],
                          "command": actual_cmd, "exit_code": actual_proc.returncode, "stdout": actual_proc.stdout.strip(), "non_pass_checks": [c for c in actual["checks"] if c["result"] != "PASS"],
                          "note": "This is not synthetic normal input validation. Missing originals remain BLOCKED; byte mismatches remain FAIL. No original is altered."}
    unchanged = historic_sha == gate.sha(hist.read_bytes())
    result = {"task_id": "BARAM_REBUILD_P1_5_001", "executed_at_utc": datetime.now(timezone.utc).isoformat(), "validator_version": gate.VERSION,
              "validator_sha256": gate.sha(SCRIPT.read_bytes()), "regression_tool_sha256": gate.sha(Path(__file__).read_bytes()),
              "result": "PASS" if unchanged and all(c["result"] == "PASS" for c in cases) else "FAIL", "cases_executed": len(cases),
              "case_result_counts": dict(__import__('collections').Counter(c["result"] for c in cases)), "cases": cases,
              "actual_repo_validation": actual_summary, "historical_validation_preserved": {"result": "PASS" if unchanged else "FAIL", "sha256_before": historic_sha, "sha256_after": gate.sha(hist.read_bytes())},
              "scope": "Validator behavior regression only; synthetic PASS is not original-data/history/gameplay PASS", "runtime_tests": "NOT_RUN", "p2_tests": "NOT_RUN"}
    args.output.parent.mkdir(parents=True, exist_ok=True); write_json(args.output, result)
    print(json.dumps({"result": result["result"], "cases": len(cases), "case_results": result["case_result_counts"], "actual_repo": actual["result"], "metadata": actual["metadata_result"], "historical_preserved": unchanged}))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__": sys.exit(main())
