#!/usr/bin/env python3
"""Fetch one Work HEAD; consume only manifest-pinned content-work snapshots."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from baram_content import PackageStore, IntakeError, PROTOCOL, decode, encode, atomic_write, git_bytes, snapshot_package, sha, HEX40

ROOT = Path(__file__).resolve().parents[1]


def baseline(repo, private_assets=None):
    numeric = json.loads((repo / "game/data/numeric.json").read_text())
    result = {}
    for c in numeric["contents"]:
        result[c["id"]] = dict(id=c["id"], kind="skill" if c["category"] == "spell" else c["category"],
            data={k: v for k, v in c.items() if k not in ("id", "provenance")}, references=[], provenance_refs=[], source_mode="ORIGINAL")
    world_path = Path(private_assets) / "source_maps/world.json" if private_assets else repo / "game/data/world.json"
    world = json.loads(world_path.read_text())
    for m in world["maps"]:
        result[m["id"]] = dict(id=m["id"], kind="map", data=m, references=[], provenance_refs=[], source_mode="DERIVED")
    for q in world.get("generated_quests", []):
        result[q["id"]] = dict(id=q["id"], kind="quest", data=q, references=[], provenance_refs=[], source_mode="INFERRED")
    return result


def execute(args):
    repository = Path(args.repo).resolve()
    game_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    commit = args.work_commit
    if commit is None:
        lines = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/work/content-import"], cwd=repository, text=True).splitlines()
        if not lines:
            report = dict(protocol_id=PROTOCOL, input_status="WAITING_INPUT", reason="WORK_BRANCH_NOT_PRESENT", game_commit=game_commit)
            atomic_write(args.report, encode(report));print(report["input_status"]);return 0
        commit = lines[0].split()[0]
    if not HEX40.fullmatch(commit):
        raise ValueError("Full Work SHA required")
    if subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=repository, capture_output=True).returncode:
        subprocess.run(["git", "fetch", "origin", commit], cwd=repository, check=True)
    try:
        index_data = git_bytes(repository, commit, "content-work/HANDOFF_INDEX.json")
    except IntakeError as error:
        if error.detail["code"] != "UPSTREAM_FILE_MISSING":raise
        report = dict(protocol_id=PROTOCOL, work_head=commit, input_status="WAITING_INPUT", reason="HANDOFF_INDEX_NOT_PRESENT", game_commit=game_commit)
        atomic_write(args.report, encode(report));print(report["input_status"]);return 0
    # Protocol files are read, hashed and retained as evidence, never run.
    protocol = git_bytes(repository, commit, "content-work/PROTOCOL.md")
    index = decode(index_data, "content-work/HANDOFF_INDEX.json")
    if index.get("protocol_id") != PROTOCOL:
        raise ValueError("Work handoff protocol mismatch")
    capabilities = json.loads((repository / "integration/content-import/capabilities.json").read_text())["implemented"]
    def assignments(values):
        return dict(value.split('=',1) for value in values)
    selections={}
    for batch,path in assignments(args.selection).items():selections[batch]=json.loads(Path(path).read_text())
    store = PackageStore(args.runtime_root, baseline(repository, args.private_assets), capabilities,
                         bundles=assignments(args.bundle),member_dirs=assignments(args.members),selection=selections)
    receipts = []
    with tempfile.TemporaryDirectory(prefix="baram-work-snapshot-", dir=args.staging_root) as temp:
        for entry in index.get("packages", []):
            if entry.get("status") != "READY_FOR_CODEX":continue
            source = entry.get("source_commit", entry.get("package_commit", entry.get("commit")))
            path = entry.get("manifest_path")
            if not source or not path:
                receipts.append(dict(protocol_id=PROTOCOL, batch_id=entry.get("batch_id"), import_status="REJECTED",
                                     errors=[dict(code="HANDOFF_PIN_MISSING", field="source_commit/manifest_path")]))
                continue
            try:
                if subprocess.run(["git", "cat-file", "-e", source + "^{commit}"], cwd=repository, capture_output=True).returncode:
                    if not HEX40.fullmatch(source):raise ValueError("Invalid source commit")
                    subprocess.run(["git", "fetch", "origin", source], cwd=repository, check=True)
                destination = Path(temp) / sha((source + path).encode())
                package, schema_root = snapshot_package(repository, source, path, destination)
                if entry.get('manifest_sha256')!=sha((package/'manifest.json').read_bytes()):
                    raise IntakeError('CONFLICT','HANDOFF_MANIFEST_HASH','Index pin and fixed package manifest disagree',file=path,
                                      expected=entry.get('manifest_sha256'),current=sha((package/'manifest.json').read_bytes()))
                receipt = store.import_package(package, source, game_commit, schema_root=schema_root)
                receipt.update(work_head=commit, handoff_index_sha256=sha(index_data), protocol_document_sha256=sha(protocol))
            except IntakeError as error:
                receipt = dict(protocol_id=PROTOCOL, batch_id=entry.get("batch_id"), source_commit=source,
                               integration_commit=None, import_status=error.status, errors=[error.detail])
            receipts.append(receipt)
            name = sha(encode({"batch":receipt.get("batch_id"), "source":source, "manifest":receipt.get("manifest_sha256")}))
            atomic_write(Path(args.receipts) / (name + ".json"), encode(receipt))
    report = dict(protocol_id=PROTOCOL, work_head=commit, game_commit=game_commit, protocol_document_sha256=sha(protocol),
                  handoff_index_sha256=sha(index_data), input_status="RECEIVED" if receipts else "WAITING_INPUT", receipts=receipts,
                  active=store.pointer(), note="IMPORTED is data activation, not playback PASS. Bind integration_commit only AFTER creating the integration commit.")
    atomic_write(args.report, encode(report));print(report["input_status"], [(r.get("batch_id"),r["import_status"]) for r in receipts])
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=str(ROOT));p.add_argument("--work-commit")
    p.add_argument("--runtime-root", required=True);p.add_argument("--private-assets")
    p.add_argument('--bundle',action='append',default=[],help='bundle_id=verified ZIP path')
    p.add_argument('--members',action='append',default=[],help='bundle_id=private pinned-member rebuild directory')
    p.add_argument('--selection',action='append',default=[],help='batch_id=JSON list of exact selected effective IDs')
    p.add_argument("--staging-root", default="/tmp");p.add_argument("--receipts", default=str(ROOT / "integration/content-import/receipts"))
    p.add_argument("--report", required=True)
    raise SystemExit(execute(p.parse_args()))
