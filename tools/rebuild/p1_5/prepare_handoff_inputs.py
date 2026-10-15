#!/usr/bin/env python3
"""Resolve private static handoff inputs by declared IDs and exact SHA-256.

Only the extracted package, explicitly supplied search roots and explicit map
paths are read. Historical absolute paths are hints, never implicit authority.
No downloaded code, SQL, installer, game or validator is executed. Needed ZIP
members are copied as inert bytes to a separate, content-addressed work cache.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

VERSION = "baram-p15-input-resolver/1.0"
MAX_FILE = 768 * 1024 * 1024
MAX_ZIP_TOTAL = 2 * 1024 * 1024 * 1024
HASH = re.compile(r"[a-f0-9]{64}\Z")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def relative(value):
    value = str(value)
    parts = PurePosixPath(value).parts
    if not value or "\\" in value or ":" in value or value.startswith("/") or ".." in parts:
        raise ValueError("Unsafe relative package/archive path")
    return Path(*parts)


def regular(path):
    """Reject links in every path component, including explicitly named files."""
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Symbolic-link input is not permitted")
    return path.is_file() and stat.S_ISREG(path.stat().st_mode)


def load(path):
    if not regular(path):
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8-sig"))


def lines(path):
    if not regular(path):
        raise FileNotFoundError(str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write(path, value):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("Linked output path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Resolver:
    def __init__(self, root, work):
        self.root, self.work = root, work
        self.required = {}
        self.by_hash = {}
        self.hashed_paths = {}
        self.failures = []
        self.blocked = []
        self.metadata = {}
        self.zip_materialized = 0
        self.files_hashed = 0
        self.sources = {}
        self.requested_hashes = set()
        self.ledger_ids = set()

    def issue(self, status, reason, **details):
        (self.failures if status == "FAIL" else self.blocked).append(dict(reason=reason, **details))

    def require(self, ident, h, size=None, **hints):
        if not isinstance(ident, str) or not ident or not isinstance(h, str) or not HASH.fullmatch(h):
            self.issue("FAIL", "INVALID_DECLARED_ID_OR_HASH", input_id=str(ident))
            return
        if size is not None and (not isinstance(size, int) or size < 0 or size > MAX_FILE):
            self.issue("FAIL", "INVALID_DECLARED_SIZE", input_id=ident)
            return
        old = self.required.get(ident)
        if old and (old["sha256"] != h or old.get("bytes") is not None and size is not None and old["bytes"] != size):
            self.issue("FAIL", "CONFLICTING_ID_DECLARATION", input_id=ident)
            return
        self.required[ident] = dict(old or {}, input_id=ident, sha256=h, bytes=size if size is not None else (old or {}).get("bytes"), **{k: v for k, v in hints.items() if v is not None})
        self.requested_hashes.add(h)

    def checked_file(self, path, expected=None, length=None, explicit=False):
        path = Path(os.path.abspath(path))
        if not path.exists():
            if explicit:
                self.issue("BLOCKED", "EXPLICIT_INPUT_NOT_ACCESSIBLE", path=str(path))
            return None
        if not regular(path):
            return None
        size = path.stat().st_size
        if size > MAX_FILE:
            if explicit:
                self.issue("BLOCKED", "INPUT_EXCEEDS_STATIC_SIZE_BOUND", path=str(path))
            return None
        h = self.hashed_paths.get(str(path))
        if h is None:
            h = digest(path)
            self.hashed_paths[str(path)] = h
            self.files_hashed += 1
        if expected is not None and (h != expected or length is not None and size != length):
            self.issue("FAIL", "DECLARED_INPUT_BYTES_MISMATCH", path=str(path), expected_sha256=expected, actual_sha256=h, expected_bytes=length, actual_bytes=size)
            return None
        if h in self.requested_hashes:
            self.by_hash.setdefault(h, path)
        return h

    def metadata_file(self, rel, expected=None, size=None):
        path = self.root / relative(rel)
        h = self.checked_file(path, expected, size, explicit=True)
        if h:
            self.metadata[str(rel)] = h
        return h

    def ingest(self):
        base = self.root / "docs/rebuild/p1_5"
        manifest = load(base / "INPUT_MANIFEST.json")
        self.manifest = manifest
        # Exact declared ledgers: this mirrors IDs accepted by validate_step01.
        sources = lines(self.root / "docs/rebuild/step01/sources.jsonl")
        for row in sources:
            sid = row.get("source_id")
            if row.get("sha256") and not row.get("files"):
                self.require(sid, row["sha256"], row.get("size_bytes"), source_type=row.get("source_type"), library_file_id=row.get("library_file_id"), location=row.get("source_path_or_url") or row.get("library_path"))
            for item in row.get("files", []):
                relative(item["path"])
                self.require(sid + "::" + item["path"], item.get("sha256"), item.get("actual_size", item.get("size")), location=item["path"], source_id=sid, repository=row.get("repository"), source_url=row.get("source_path_or_url"), historical_path_hint=item.get("local_path"))
        for row in lines(self.root / "docs/rebuild/step01/archive_members.jsonl"):
            # Archive lineage is a location hint; it never becomes a write path.
            for part in row["archive_member"].split("!"):
                relative(part)
            self.require(row.get("member_id"), row.get("sha256"), row.get("size_bytes"), source_id=row.get("source_id"), archive_member=row.get("archive_member"))
        self.ledger_ids = set(self.required)
        for row in manifest.get("originals", []):
            self.require(row.get("source_id"), row.get("sha256"), row.get("size_bytes"), library_file_id=row.get("library_file_id"), location=row.get("library_path"))
        for path in [self.root / "docs/rebuild/step01/sources.jsonl", base / "sources_delta.jsonl"]:
            for row in lines(path):
                if row.get("source_id"):
                    sid = row["source_id"]
                    old = self.sources.get(sid, {})
                    if old.get("sha256") and row.get("sha256") and old["sha256"] != row["sha256"]:
                        self.issue("FAIL", "CONFLICTING_SOURCE_HASH", input_id=sid)
                    self.sources[sid] = dict(old, **row)
        for path in sorted(base.glob("research_*.json")):
            obj = load(path)
            if not isinstance(obj, dict):
                raise ValueError("Research manifest must be an object")
            for key in ("sources", "web_pages", "web_images"):
                for row in obj.get(key, []):
                    if not row.get("source_id"):
                        continue
                    sid = row["source_id"]
                    old = self.sources.get(sid, {})
                    if old.get("sha256") and row.get("sha256") and old["sha256"] != row["sha256"]:
                        self.issue("FAIL", "CONFLICTING_SOURCE_HASH", input_id=sid)
                    self.sources[sid] = dict(old, **row)
            self.metadata_file(path.relative_to(self.root).as_posix())
        for sid, row in self.sources.items():
            if row.get("sha256") and not row.get("files"):
                size = next((row[k] for k in ("bytes", "size_bytes", "byte_length") if row.get(k) is not None), None)
                if row.get("path"):
                    relative(row["path"])
                self.require(sid, row["sha256"], size, source_type=row.get("source_type"), repository=row.get("repository"), location=row.get("source_path_or_url") or row.get("url") or row.get("original_url"), declared_path=row.get("path"), library_file_id=row.get("library_file_id"))
        for group in ("normalized_catalogs", "tools"):
            for item in manifest.get(group, []):
                rel = item["path"]
                if group == "normalized_catalogs":
                    rel = "docs/rebuild/p1_5/" + rel
                self.metadata_file(rel, item.get("sha256"), item.get("bytes"))
        # Preserve an independent fingerprint of the complete metadata generation.
        for rel in ["docs/rebuild/p1_5/INPUT_MANIFEST.json", "docs/rebuild/step01/sources.jsonl", "docs/rebuild/step01/archive_members.jsonl", "docs/rebuild/p1_5/sources_delta.jsonl"]:
            self.metadata_file(rel)
        wrapper = self.root / "PACKAGE_MANIFEST.json"
        if wrapper.is_file():
            for item in load(wrapper).get("files", []):
                self.metadata_file(item["path"], item["sha256"], item.get("bytes"))

    def scan(self, root):
        root = Path(os.path.abspath(root))
        if root.is_symlink() or any(p.is_symlink() for p in root.parents):
            raise ValueError("Linked search root")
        if root.is_file():
            self.checked_file(root, explicit=True)
            return
        if not root.is_dir():
            self.issue("BLOCKED", "SEARCH_ROOT_NOT_ACCESSIBLE", path=str(root))
            return
        for directory, names, files in os.walk(root, followlinks=False):
            names[:] = sorted(n for n in names if n not in (".git", "__pycache__") and not (Path(directory) / n).is_symlink() and Path(directory) / n != self.work)
            for name in sorted(files):
                path = Path(directory) / name
                if not path.is_symlink():
                    self.checked_file(path)

    def mapped(self, path):
        mapping = load(path)
        if not isinstance(mapping, dict):
            raise ValueError("Input map must be an object of ID:path strings")
        for ident, value in mapping.items():
            if not isinstance(value, str):
                raise ValueError("Input map path must be text")
            target = Path(value)
            if not target.is_absolute():
                target = path.parent / relative(value)
            required = self.required.get(ident)
            self.checked_file(target, required["sha256"] if required else None, required.get("bytes") if required else None, explicit=True)

    def reference_zip(self):
        item = self.manifest.get("reference_package")
        if not item:
            return
        path = self.root / relative(item["path"])
        if self.checked_file(path, item["sha256"], item.get("bytes"), explicit=True) is None:
            return
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate reference archive member")
            infos = {entry.filename: entry for entry in archive.infolist()}
            for name, info in infos.items():
                relative(name)
                if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1 or info.file_size > MAX_FILE:
                    raise ValueError("Unsafe reference archive entry")
            index = json.loads(archive.read("SOURCE_MANIFEST.json"))
            total = 0
            for entry in index.get("entries", []):
                name = entry["path"]
                relative(name)
                h = entry["sha256"]
                if h not in self.requested_hashes or h in self.by_hash:
                    continue
                info = infos.get(name)
                if not info or info.file_size != entry["bytes"]:
                    raise ValueError("Reference manifest/member size mismatch")
                total += info.file_size
                if total > MAX_ZIP_TOTAL:
                    raise ValueError("Reference extraction byte bound")
                data = archive.read(info)  # zipfile verifies member CRC as well.
                if hashlib.sha256(data).hexdigest() != h:
                    raise ValueError("Reference manifest/member hash mismatch")
                destination = self.work / "objects" / h
                if any(parent.is_symlink() for parent in destination.parents):
                    raise ValueError("Linked materialization directory")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    self.checked_file(destination, h, len(data), explicit=True)
                else:
                    with destination.open("xb") as output:
                        output.write(data)
                    self.checked_file(destination, h, len(data), explicit=True)
                    self.zip_materialized += 1

    def finish(self, output, report):
        mapping = {}
        missing = []
        for ident, row in sorted(self.required.items()):
            path = self.by_hash.get(row["sha256"])
            if path:
                # Recheck identities after discovery; no filename-only binding.
                if digest(path) != row["sha256"] or row.get("bytes") is not None and path.stat().st_size != row["bytes"]:
                    self.issue("FAIL", "RESOLVED_INPUT_CHANGED_DURING_READ", input_id=ident)
                else:
                    mapping[ident] = str(path)
            else:
                missing.append(row)
        if missing:
            self.issue("BLOCKED", "REQUIRED_INPUTS_NOT_RESOLVED", count=len(missing))
        result = "FAIL" if self.failures else "BLOCKED" if self.blocked else "PASS"
        importer = [sys.executable, str(self.root / "tools/rebuild/p1_5/import_dry_run.py"), "--repo", str(self.root), "--registry-dir", str(self.root / "docs/rebuild/p1_5"), "--content-dir", str(self.root / "docs/rebuild/p1_5/selected_content"), "--server-root", str(self.work / "references"), "--input-map", str(output), "--catalog-manifest", str(self.root / "docs/rebuild/p1_5/INPUT_MANIFEST.json"), "--output", str(self.work / "import_validation.json")]
        byte_map = self.work / "step01_input_map.json"
        receipt = {"schema": "baram.p1_5.resolved_inputs/1", "tool_version": VERSION, "tool_sha256": digest(Path(__file__)), "executed_at_utc": datetime.now(timezone.utc).isoformat(), "result": result, "required_ids": len(self.required), "resolved_ids": len(mapping), "resolved_unique_hashes": len(set(self.required[k]["sha256"] for k in mapping)), "files_hashed": self.files_hashed, "reference_members_materialized": self.zip_materialized, "failures": self.failures, "blocked": self.blocked, "missing_inputs": missing, "metadata_fingerprints": self.metadata, "import_input_map": str(output), "whole_byte_input_map": str(byte_map), "whole_byte_declared_ids": len(self.ledger_ids), "import_command": importer, "whole_byte_gate_command": [sys.executable, str(self.root / "tools/rebuild/step01/validate_step01.py"), "--root", str(self.root), "--input-map", str(byte_map), "--output", str(self.work / "step01_validation.json")], "missing_member_recovery": "Materialize listed Library file IDs and exact hashes; run recheck_archives.py per INPUT_MANIFEST.replay_commands.archives, then add its private-work output as --source-root. No network request or installer is executed by this resolver.", "source_files_modified": False, "source_code_execution": "NOT_RUN", "runtime_tests": "NOT_RUN", "codex_receiver_environment": "NOT_RUN", "scope": "Only exact bytes/declared identities and path restoration; an importer FAIL from known NA dangling references must remain visible."}
        write(output, mapping)
        write(byte_map, {key: value for key, value in mapping.items() if key in self.ledger_ids})
        write(report, receipt)
        print(json.dumps({k: receipt[k] for k in ("result", "required_ids", "resolved_ids", "files_hashed", "reference_members_materialized")}))
        return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result]


def self_test():
    """Small isolated identity, corruption, missing-input and traversal checks."""
    with tempfile.TemporaryDirectory(prefix="baram-input-resolver-test-") as temp:
        root = Path(temp)
        source = root / "renamed.bin"
        source.write_bytes(b"static test fixture")
        h = digest(source)
        resolver = Resolver(root, root / "work")
        resolver.require("FIXTURE-ID", h, len(source.read_bytes()))
        resolver.scan(root)
        assert resolver.by_hash[h] == source
        resolver.checked_file(source, "0" * 64, explicit=True)
        assert resolver.failures[-1]["reason"] == "DECLARED_INPUT_BYTES_MISMATCH"
        resolver.require("FIXTURE-MISSING", "1" * 64, 20)
        with contextlib.redirect_stdout(io.StringIO()):
            assert resolver.finish(root / "map.json", root / "report.json") == 1
        assert len(load(root / "report.json")["missing_inputs"]) == 1
        missing = Resolver(root, root / "work")
        missing.require("FIXTURE-MISSING", "1" * 64, 20)
        with contextlib.redirect_stdout(io.StringIO()):
            assert missing.finish(root / "missing-map.json", root / "missing-report.json") == 2
        for value in ("../escape", "/absolute", "C:/windows", "nested\\escape"):
            try:
                relative(value)
            except ValueError:
                continue
            raise AssertionError("Traversal/absolute path accepted")
        (root / "link").symlink_to(source)
        try:
            regular(root / "link")
        except ValueError:
            pass
        else:
            raise AssertionError("Symlink accepted")
        bad_zip = root / "traversal.zip"
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("../escape", b"fixture")
            archive.writestr("SOURCE_MANIFEST.json", '{"entries":[]}')
        resolver.manifest = {"reference_package": {"path": "traversal.zip", "sha256": digest(bad_zip), "bytes": bad_zip.stat().st_size}}
        try:
            resolver.reference_zip()
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe archive member accepted")
    print(json.dumps({"result": "PASS", "self_test": "exact identity despite rename; corruption and missing inputs; traversal and symlink rejection", "runtime_tests": "NOT_RUN"}))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package-root", type=Path)
    ap.add_argument("--source-root", action="append", type=Path, default=[])
    ap.add_argument("--input-map", type=Path, help="Explicit previous ID:path map; paths are rehashed, never accepted by name")
    ap.add_argument("--work-dir", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    for name in ("package_root", "work_dir", "output", "report"):
        if getattr(args, name) is None:
            ap.error("--" + name.replace("_", "-") + " is required")
    # Keep outputs and materializations outside the immutable source package.
    root, work = Path(os.path.abspath(args.package_root)), Path(os.path.abspath(args.work_dir))
    if work == root or root in work.parents:
        ap.error("--work-dir must be outside --package-root")
    output, report = Path(os.path.abspath(args.output)), Path(os.path.abspath(args.report))
    if output == report or root in output.parents or root in report.parents:
        ap.error("Map/report must be distinct files outside --package-root")
    resolver = Resolver(root, work)
    try:
        regular(root / "docs/rebuild/p1_5/INPUT_MANIFEST.json")
        if work.is_symlink() or any(p.is_symlink() for p in work.parents):
            raise ValueError("Linked work directory")
        resolver.ingest()
        if args.input_map:
            resolver.mapped(Path(os.path.abspath(args.input_map)))
        resolver.scan(root)
        resolver.reference_zip()
        for source in args.source_root:
            resolver.scan(source)
        return resolver.finish(output, report)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        status = "BLOCKED" if isinstance(error, FileNotFoundError) else "FAIL"
        resolver.issue(status, "INPUT_RESOLUTION_ABORTED", error_type=type(error).__name__, detail=str(error) if isinstance(error, FileNotFoundError) else "Malformed metadata, unsafe path, or inconsistent input; source values are not printed")
        return resolver.finish(output, report)


if __name__ == "__main__":
    sys.exit(main())

