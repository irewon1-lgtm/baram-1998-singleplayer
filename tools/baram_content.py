"""Codex-owned BARAM_PARALLEL_V1 intake. Work files are read-only, never code.

An immutable release owns BOTH data and its import ledger. Only ACTIVE.json is
atomically switched, so a crash cannot report a different active batch version.
No timestamps, random IDs or directory order enter the generated release bytes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path, PurePosixPath

PROTOCOL = "BARAM_PARALLEL_V1"
TOOL_VERSION = "codex-import-1"
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_JSON = 32 * 1024 * 1024
MAX_INTEGER = 2**53 - 1  # exact through Godot JSON's numeric representation
KINDS = {"item", "monster", "npc", "map", "skill", "quest", "asset", "growth", "class", "advancement", "drop_group", "enhancement", "recipe", "economy", "shop", "drop", "enchantment"}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class IntakeError(Exception):
    def __init__(self, status, code, message, *, file=None, content_id=None, field=None, current=None, expected=None, proposed=None):
        super().__init__(message)
        self.status = status
        self.detail = dict(code=code, message=message, file=file, content_id=content_id, field=field,
                           current=current, expected=expected, proposed=proposed)


def fail(code, message, status="REJECTED", **detail):
    raise IntakeError(status, code, message, **detail)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def native(value):
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > MAX_INTEGER:
        fail("INTEGER_PRECISION", "Integer exceeds exact runtime JSON range")
    if isinstance(value, Decimal):
        if not value.is_finite():
            fail("NON_FINITE", "Non-finite number cannot enter runtime data")
        if value == value.to_integral():
            result = int(value)
            if abs(result) > MAX_INTEGER:
                fail("INTEGER_PRECISION", "Integer exceeds exact runtime JSON range")
            return result
        result = float(value)
        if result == 0 and value != 0:
            fail("DECIMAL_UNDERFLOW", "Value would silently become zero")
        return result
    if isinstance(value, dict):
        return {k: native(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [native(v) for v in value]
    return value


def encode(value):
    return (json.dumps(native(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(data, file="<json>"):
    if len(data) > MAX_JSON:
        fail("JSON_SIZE", "JSON exceeds bounded input size", file=file)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("DUPLICATE_JSON_KEY", "Duplicate JSON key", file=file, field=key)
            result[key] = value
        return result
    try:
        return json.loads(data, parse_float=Decimal, parse_constant=lambda s: fail("NON_FINITE", s, file=file), object_pairs_hook=unique)
    except (UnicodeError, ValueError, RecursionError) as error:
        fail("JSON_PARSE", str(error), file=file)


def safe_relative(path):
    if not isinstance(path, str) or not path or "\\" in path or ":" in path or "\x00" in path:
        fail("UNSAFE_PATH", "Expected a portable relative path", file=str(path))
    p = PurePosixPath(path)
    if p.is_absolute() or any(x in ("..", ".") for x in path.split("/")) or "//" in path:
        fail("UNSAFE_PATH", "Path escape/absolute path rejected", file=path)
    return p


def read_bounded(root, path, maximum=MAX_FILE):
    relative = safe_relative(path)
    root = Path(root).resolve()
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            fail("LINK_INPUT", "Links are not package inputs", file=path)
    if not current.is_file():
        fail("MISSING_FILE", "Declared input is not present", file=path)
    if current.stat().st_size > maximum:
        fail("FILE_SIZE", "Declared input exceeds size limit", file=path)
    return current.read_bytes()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def extract_zip(source, destination, maximum=MAX_TOTAL):
    """Bounded extraction, no links, traversal, Windows collisions or overwrite."""
    destination = Path(destination)
    if destination.exists():
        fail("EXTRACTION_DESTINATION", "Use a fresh staging directory")
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        total = 0
        seen = set()
        for entry in entries:
            path = entry.filename.rstrip("/")
            safe_relative(path)
            folded = path.casefold()
            if folded in seen:
                fail("ARCHIVE_DUPLICATE", "Duplicate/case-colliding ZIP path", file=path)
            seen.add(folded)
            mode = entry.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                fail("ARCHIVE_LINK", "Nonregular ZIP member", file=path)
            total += entry.file_size
            if entry.file_size > MAX_FILE or total > maximum:
                fail("ARCHIVE_EXPANSION", "Uncompressed bytes exceed declared safe bound", file=path)
        destination.mkdir(parents=True)
        for entry in entries:
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, target.open("xb") as dst:
                    count = 0
                    while block := src.read(1024 * 1024):
                        count += len(block)
                        if count > entry.file_size:
                            fail("ARCHIVE_EXPANSION", "Member exceeds header size", file=entry.filename)
                        dst.write(block)
                if count != entry.file_size:
                    fail("ARCHIVE_TRUNCATED", "Member shorter than declared", file=entry.filename)


def round_half_away(value):
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def probability_ratio(value):
    if isinstance(value, dict):
        n = value.get("numerator", value.get("num"))
        d = value.get("denominator", value.get("den"))
        if not isinstance(n, int) or isinstance(n, bool) or not isinstance(d, int) or isinstance(d, bool):
            fail("PROBABILITY_INTEGER", "Probability requires integer numerator/denominator")
        ratio = Fraction(n, d) if d > 0 else None
    else:
        ratio = Fraction(Decimal(str(value)))
    if ratio is None or not 0 <= ratio <= 1 or ratio.denominator > MAX_INTEGER:
        fail("PROBABILITY_RANGE_OR_PRECISION", "Probability must be exact, bounded and losslessly representable", current=value)
    # Preserve a provided denominator rather than automatically normalizing it.
    if isinstance(value, dict):
        if d > MAX_INTEGER:
            fail("PROBABILITY_RANGE_OR_PRECISION", "Denominator exceeds exact runtime range")
        return dict(numerator=n, denominator=d)
    denominator = 1_000_000
    if denominator % ratio.denominator:
        denominator = ratio.denominator
    return dict(numerator=ratio.numerator * (denominator // ratio.denominator), denominator=denominator)


def normalize_units(value, content_id, field="data"):
    if isinstance(value, list):
        return [normalize_units(v, content_id, f"{field}[{i}]") for i, v in enumerate(value)]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        location = field + "." + key
        if key in ("probability", "success_probability", "hit_probability") and item is not None:
            result[key] = item
            result[key + "_ratio"] = probability_ratio(item)
        elif key.endswith("_ms") and item is not None:
            if isinstance(item, bool) or Decimal(str(item)) != Decimal(str(item)).to_integral() or item < 0:
                fail("TIME_UNIT", "Milliseconds must be nonnegative integers", content_id=content_id, field=location, current=item)
            result[key] = int(item)
        else:
            result[key] = normalize_units(item, content_id, location)
    return result


def reference_ids(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for v in value for x in reference_ids(v)]
    if isinstance(value, dict):
        # A typed reference can have descriptive labels; they aren't IDs.
        for key in ("target_id", "content_id", "id", "target"):
            if key in value:
                return reference_ids(value[key])
        return [x for v in value.values() for x in reference_ids(v)]
    fail("REFERENCE_FORMAT", "Reference must carry an explicit ID", current=value)


def get_field(data, field):
    current = data
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            fail("PATCH_FIELD", "Target field is not present", field=field)
        current = current[part]
    return current


def set_field(data, field, value):
    parts = field.split(".")
    parent = data
    for part in parts[:-1]:
        if not isinstance(parent.get(part), dict):
            fail("PATCH_FIELD", "Target field parent is not present", field=field)
        parent = parent[part]
    parent[parts[-1]] = value


def empty_release():
    return dict(format="BARAM_RUNTIME_CONTENT", version=1, tool_version=TOOL_VERSION,
                records={}, id_map={}, imports={}, assets={}, owned_fields={}, generation=0)


class PackageStore:
    def __init__(self, root, baseline, capabilities=(), bundles=None):
        self.root = Path(root)
        self.baseline = copy.deepcopy(baseline)
        self.capabilities = set(capabilities)
        self.bundles = bundles or {}

    def pointer(self):
        path = self.root / "ACTIVE.json"
        return decode(path.read_bytes()) if path.exists() else None

    def load(self):
        pointer = self.pointer()
        if not pointer:
            return empty_release()
        release_id = pointer.get("release_id", "")
        if not HEX64.fullmatch(release_id):
            fail("ACTIVE_FORMAT", "Active release ID is invalid", status="CONFLICT")
        data = read_bounded(self.root, f"releases/{release_id}/release.json", MAX_JSON)
        if len(data) != pointer.get("bytes") or sha(data) != pointer.get("sha256") or sha(data) != release_id:
            fail("ACTIVE_INTEGRITY", "Active data and manifest disagree", status="CONFLICT")
        release = decode(data)
        if release.get("format") != "BARAM_RUNTIME_CONTENT" or release.get("version") != 1:
            fail("RUNTIME_VERSION", "Unsupported runtime format", status="CONFLICT")
        checked=set()
        for item in release["assets"].values():
            if item['stored_path'] in checked:continue
            checked.add(item['stored_path'])
            content = read_bounded(self.root, f"releases/{release_id}/files/" + item["stored_path"])
            if len(content) != item["bytes"] or sha(content) != item["sha256"]:
                fail("ACTIVE_ASSET_INTEGRITY", "Active asset bytes changed", status="CONFLICT", file=item["stored_path"])
        return release

    def recover_previous(self):
        pointer = self.pointer()
        if not pointer or not pointer.get("previous"):
            fail("NO_PREVIOUS", "No prior active pointer to recover", status="CONFLICT")
        previous = pointer["previous"]
        path = self.root / "releases" / previous["release_id"] / "release.json"
        data = path.read_bytes()
        if sha(data) != previous["sha256"]:
            fail("PREVIOUS_INTEGRITY", "Previous release is also invalid", status="CONFLICT")
        atomic_write(self.root / "ACTIVE.json", encode(previous))
        return self.load()

    def import_package(self, package, source_commit, game_commit, *, schema_root=None, fixture=False, interrupt=None):
        receipt = dict(protocol_id=PROTOCOL, batch_id=None, source_commit=source_commit,
                       manifest_sha256=None, base_game_commit=None, applied_before_game_commit=game_commit,
                       integration_commit=None, tool_version=TOOL_VERSION, import_status="REJECTED",
                       applied_ids=[], held_ids=[], unmet_required_capabilities=[], errors=[], work_fix_requests=[],
                       save_compatibility="STABLE_IDS_RETAINED_MIGRATION_REQUIRED_FOR_RUNTIME_STATE",
                       fixture=fixture, playback_status="NOT_RUN")
        try:
            return self._import(package, source_commit, game_commit, receipt, schema_root, fixture, interrupt)
        except IntakeError as error:
            receipt["import_status"] = error.status
            receipt["errors"].append(native(error.detail))
            if error.status in ("REJECTED", "CONFLICT"):
                receipt["work_fix_requests"].append(native(error.detail))
            return receipt

    def _import(self, package, source_commit, game_commit, receipt, schema_root, fixture, interrupt):
        package = Path(package)
        manifest_data = read_bounded(package, "manifest.json", MAX_JSON)
        manifest = decode(manifest_data, "manifest.json")
        if not isinstance(manifest, dict):
            fail("MANIFEST_FORMAT", "Manifest must be an object")
        receipt.update(batch_id=manifest.get("batch_id"), manifest_sha256=sha(manifest_data),
                       base_game_commit=manifest.get("base_game_commit"), schema_version=manifest.get("schema_version"))
        if manifest.get("protocol_id") != PROTOCOL or manifest.get("schema_id") != "BARAM_CONTENT_PACKAGE" or manifest.get("schema_version") != 1:
            fail("PROTOCOL_VERSION", "Unsupported protocol/schema version", file="manifest.json")
        if manifest.get("producer") != ("CodexTest" if fixture else "Work"):
            fail("PRODUCER", "Wrong package producer", file="manifest.json")
        if not isinstance(manifest.get("batch_id"), str) or not manifest["batch_id"]:
            fail("BATCH_ID", "Missing explicit batch identity")
        if not HEX40.fullmatch(source_commit) or not HEX40.fullmatch(str(manifest.get("base_game_commit", ""))):
            fail("COMMIT_PIN", "Full source/base SHA is required")
        release = self.load()
        prior = release["imports"].get(manifest["batch_id"])
        # Verify all files even on re-import: a damaged transfer is not a valid
        # repeated input just because its original manifest was imported.
        entries = manifest.get("files")
        if not isinstance(entries, list) or not entries:
            fail("FILE_LIST", "Manifest must enumerate package files")
        verified = {}
        total = 0
        folded = set()
        for entry in entries:
            path = str(safe_relative(entry.get("path")))
            if path.casefold() in folded:
                fail("FILE_DUPLICATE", "Repeated/case-colliding manifest path", file=path)
            folded.add(path.casefold())
            size = entry.get("size_bytes", entry.get("bytes", entry.get("size")))
            expected = entry.get("sha256", "")
            if not isinstance(size, int) or isinstance(size, bool) or not HEX64.fullmatch(expected):
                fail("FILE_PIN", "Explicit size and SHA256 required", file=path)
            total += size
            if total > MAX_TOTAL or size < 0:
                fail("PACKAGE_SIZE", "Package exceeds bounded size")
            data = read_bounded(package, path)
            if len(data) != size or sha(data) != expected:
                fail("FILE_HASH", "Transferred bytes differ from manifest", file=path, expected=expected, current=sha(data))
            verified[path] = (entry, data)
        if "validation.json" not in verified:
            fail("VALIDATION_MISSING", "Work validation.json must be pinned")
        validation = decode(verified["validation.json"][1], "validation.json")
        if isinstance(validation, dict) and validation.get("status") in ("FAIL", "REJECTED"):
            fail("UPSTREAM_VALIDATION_FAILED", "Work marked validation as failed")
        schemas = self._schemas(manifest, verified, schema_root)
        if "manifest.json" in schemas:
            self._schema_validate(manifest, schemas["manifest.json"], "manifest.json", schemas)
        if prior:
            if prior["manifest_sha256"] != receipt["manifest_sha256"]:
                fail("BATCH_MUTATED", "Same batch ID has different manifest bytes", "CONFLICT",
                     expected=prior["manifest_sha256"], current=receipt["manifest_sha256"])
            receipt.update(import_status="ALREADY_IMPORTED", applied_ids=prior["applied_ids"], release_id=self.pointer()["release_id"])
            return receipt
        for dependency in manifest.get("dependencies", []):
            if not isinstance(dependency, dict) or not dependency.get("batch_id"):
                fail("DEPENDENCY_FORMAT", "Dependencies must identify a fixed batch/hash or commit")
            pin = dependency.get("manifest_sha256")
            commit = dependency.get("source_commit", dependency.get("commit"))
            if not pin and not commit:
                fail("DEPENDENCY_PIN", "Moving/unpinned dependency rejected")
            got = release["imports"].get(dependency["batch_id"])
            if not got or (pin and pin != got["manifest_sha256"]) or (commit and commit != got["source_commit"]):
                fail("DEPENDENCY_UNAVAILABLE", "Exact dependency not active", "WAITING_DEPENDENCY", current=dependency)
        required = manifest.get("required_capabilities", [])
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
            fail("CAPABILITY_FORMAT", "Capabilities must carry explicit names")
        missing = sorted(set(required) - self.capabilities)
        receipt["unmet_required_capabilities"] = missing
        incoming = []
        provenance_ids=set()
        if 'provenance.json' in verified:
            provenance=decode(verified['provenance.json'][1],'provenance.json')
            catalog=provenance if isinstance(provenance,list) else provenance.get('records',provenance.get('sources',[]))
            provenance_ids={r['id'] for r in catalog if isinstance(r,dict) and 'id' in r}
        record_schema = next((s for s in schemas.values() if s.get("$id") == "urn:baram:content:1"), None)
        for path, (entry, data) in verified.items():
            if path.endswith(".jsonl"):
                for line_number, line in enumerate(data.splitlines(), 1):
                    if not line.strip():continue
                    record = decode(line, f"{path}:{line_number}")
                    if record_schema:
                        self._schema_validate(record, record_schema, f"{path}:{line_number}", schemas)
                        for key in record_schema.get("kind_required_data", {}).get(record.get("kind"), []):
                            if key not in record.get("data", {}):
                                fail("KIND_REQUIRED_DATA", "Field required by published Work schema", file=f"{path}:{line_number}", content_id=record.get("id"), field="data."+key)
                    incoming.append((f"{path}:{line_number}", record))
                continue
            if not path.endswith(".json") or path in ("validation.json","provenance.json","acquisition.json") or entry.get("kind") in ("schema", "provenance"):
                continue
            document = decode(data, path)
            if entry.get("schema"):
                schema = schemas.get(entry["schema"])
                if schema is None:
                    fail("SCHEMA_MISSING", "Declared schema cannot be read", file=entry["schema"])
                self._schema_validate(document, schema, path, schemas)
            records = document if isinstance(document, list) else document.get("contents", document.get("records")) if isinstance(document, dict) else None
            if records is None:
                continue  # pinned metadata is preserved, not mistaken for content
            if not isinstance(records, list):
                fail("CONTENT_LIST", "Structured content must be a list", file=path)
            incoming.extend((path, record) for record in records)
        if not incoming:
            fail("EMPTY_CONTENT", "No structured content records found")
        ids = set()
        for file, record in incoming:
            if not isinstance(record, dict) or not record.get("id") or record.get("kind") not in KINDS:
                fail("CONTENT_ID_KIND", "Explicit supported id/kind required", file=file)
            rid, kind = record["id"], record["kind"]
            prefix = "test." if fixture else "wk."
            supported_namespace = rid.startswith(prefix + kind + ".") if isinstance(rid, str) else False
            if not fixture and record_schema and isinstance(rid, str):
                supported_namespace = bool(re.fullmatch(r"wk\.[a-z_]+\.[a-zA-Z0-9_.-]+", rid))
            if not supported_namespace:
                fail("CONTENT_NAMESPACE", "Content ID has wrong permanent namespace", file=file, content_id=rid)
            if rid in ids:
                fail("CONTENT_ID_DUPLICATE", "Repeated content ID", file=file, content_id=rid)
            ids.add(rid)
            if record.get("operation") not in ("add", "propose_patch") or not isinstance(record.get("data"), dict):
                fail("CONTENT_OPERATION", "Explicit declarative operation/data required", file=file, content_id=rid)
            if record.get("source_mode") not in ("ORIGINAL", "AVERAGED", "INFERRED", "DERIVED"):
                fail("SOURCE_MODE", "Source confidence classification missing", file=file, content_id=rid)
            for key in ("references", "provenance_refs"):
                if key not in record:
                    fail("CONTENT_PROVENANCE_REFERENCE", "Common field absent", file=file, content_id=rid, field=key)
            if provenance_ids:
                for ref in record['provenance_refs']:
                    if ref not in provenance_ids:fail('PROVENANCE_MISSING','Pinned provenance target missing',file=file,content_id=rid,current=ref)
        count = {}
        for _, record in incoming:
            count[record["kind"]] = count.get(record["kind"], 0) + 1
        declared = manifest.get("content_counts", manifest.get("counts"))
        if declared is not None and {k: v for k, v in declared.items() if v} != count:
            fail("CONTENT_COUNTS", "Declared counts differ from parsed IDs", expected=declared, current=count)
        receipt['validated_counts']=count
        # Work's schema uses a proposal ID and target_id as the effective ID.
        effective_ids={r.get('target_id',r['id']) for _,r in incoming}
        available_preview=set(self.baseline)|set(release['records'])|effective_ids
        for file,record in incoming:
            for ref in reference_ids(record['references']):
                if ref not in available_preview:
                    fail('REFERENCE_MISSING','Unresolved effective/target ID',file=file,content_id=record['id'],current=ref)
        if missing:
            receipt['held_ids']=sorted(r.get('target_id',r['id']) for _,r in incoming)
            fail("CAPABILITY_MISSING", "Required execution handlers not available", "PENDING_CAPABILITY", current=missing)
        candidate = copy.deepcopy(release)
        supersedes = manifest.get("supersedes", [])
        if isinstance(supersedes, str):
            supersedes = [supersedes]
        superseded = {x.get("batch_id") if isinstance(x, dict) else x for x in supersedes}
        for old in superseded:
            if old not in release["imports"]:
                fail("SUPERSEDES_MISSING", "Replacement relation points to unknown imported batch", "WAITING_DEPENDENCY", current=old)
        # Whole ID space before resolving any forward reference.
        available = set(self.baseline) | set(candidate["records"]) | ids
        external = manifest.get("external_references", manifest.get("external_refs", []))
        for ref in reference_ids(external):
            if ref not in set(self.baseline) | set(release["records"]):
                fail("EXTERNAL_REFERENCE", "Existing referenced ID unavailable", "CONFLICT", content_id=ref)
        applied = []
        for file, record in incoming:
            rid = record["id"]
            for ref in reference_ids(record["references"]):
                if ref not in available:
                    fail("REFERENCE_MISSING", "Unresolved forward/external reference", file=file, content_id=rid, field="references", current=ref)
            if record["operation"] == "add":
                existing = candidate["records"].get(rid)
                if rid in self.baseline or (existing and existing["batch_id"] not in superseded):
                    fail("ID_COLLISION", "Permanent ID already owned", "CONFLICT", file=file, content_id=rid)
                if existing and any(key.startswith(rid + "/") for key in candidate["owned_fields"]):
                    fail("OWNED_FIELD", "Codex owns an overridden field; explicit conditional patch required", "CONFLICT", file=file, content_id=rid)
                converted = copy.deepcopy(record)
                converted["data"] = normalize_units(converted["data"], rid)
                converted.update(batch_id=manifest["batch_id"], source_commit=source_commit, source_file=file)
                candidate["records"][rid] = converted
                candidate["id_map"][rid] = candidate["id_map"].get(rid, rid)
                applied.append(rid)
            else:
                target = record.get("target_id")
                target_record = candidate["records"].get(target, self.baseline.get(target))
                if target_record is None:
                    fail("PATCH_TARGET", "Patch target ID does not exist", "CONFLICT", file=file, content_id=rid)
                target_record = copy.deepcopy(target_record)
                published_changes=record.get('changes')
                changes = {c['path']:c['after'] for c in published_changes} if published_changes else record["data"]
                conditions = {c['path']:c['before'] for c in published_changes} if published_changes else record.get("preconditions", record.get("expected_before"))
                expected_hash = record.get("expected_sha256")
                if not conditions and not expected_hash:
                    fail("PATCH_PRECONDITION", "Patch requires expected fields or data hash", file=file, content_id=rid)
                if expected_hash and sha(encode(target_record["data"])) != expected_hash:
                    fail("PATCH_HASH_CONFLICT", "Target changed since proposal", "CONFLICT", file=file, content_id=target, current=sha(encode(target_record["data"])), expected=expected_hash)
                for field, proposed in changes.items():
                    try:current = get_field(target_record["data"], field);exists=True
                    except IntakeError:current=None;exists=False
                    guard=conditions.get(field) if conditions else None
                    matched=(guard.get('exists')==exists and (not exists or native(current)==native(guard.get('value')))) if published_changes and isinstance(guard,dict) else field in conditions and native(current)==native(guard)
                    if not expected_hash and not matched:
                        fail("PATCH_VALUE_CONFLICT", "Changed field differs from old proposal", "CONFLICT", file=file, content_id=target,
                             field=field, current=current, expected=conditions.get(field), proposed=proposed)
                    if target + "/" + field in candidate["owned_fields"]:
                        fail("OWNED_FIELD", "Patch would overwrite a Codex-owned field", "CONFLICT", file=file, content_id=target, field=field, current=current, proposed=proposed)
                    if not exists and '.' not in field:target_record['data'][field]=proposed
                    else:set_field(target_record["data"], field, proposed)
                if published_changes:
                    # Keep complete proposed runtime definition separate from
                    # original numeric values; never replace the base record.
                    target_record['runtime_definition']=copy.deepcopy(record['data'])
                target_record["data"] = normalize_units(target_record["data"], target)
                target_record.setdefault("patch_history", []).append(dict(batch_id=manifest["batch_id"], source_commit=source_commit,
                                                                            proposal_id=rid, provenance_refs=record["provenance_refs"], source_mode=record["source_mode"]))
                target_record.setdefault("batch_id", manifest["batch_id"])
                candidate["records"][target] = target_record
                candidate["id_map"][rid] = target
                applied.append(target)
        # Referencing deleted IDs remains impossible: no delete operation exists.
        for rid, record in candidate["records"].items():
            for ref in reference_ids(record.get("references", [])):
                if ref not in set(candidate["records"]) | set(self.baseline):
                    fail("ACTIVE_REFERENCE", "Candidate breaks previous active reference", content_id=rid, current=ref)
        asset_bytes = {}
        bundle_inputs={}
        if 'acquisition.json' in verified:
            acquisition=decode(verified['acquisition.json'][1],'acquisition.json')
            if acquisition.get('bundle_id'):
                bundle_id=acquisition['bundle_id'];supplied=self.bundles.get(bundle_id)
                if supplied:
                    supplied=Path(supplied);size=acquisition.get('size_bytes');digest=acquisition.get('sha256')
                    if not supplied.is_file() or supplied.stat().st_size!=size or sha(supplied.read_bytes())!=digest:
                        fail('BUNDLE_HASH','Recipient bytes do not match fixed private-bundle pin',file=str(supplied))
                    staging=self.root/'.acquired'/digest
                    if not staging.exists():extract_zip(supplied,staging)
                    bundle_inputs[bundle_id]=staging
        for rid, record in candidate["records"].items():
            if record["kind"] != "asset" or record.get("batch_id") != manifest["batch_id"]:
                continue
            path = record["data"].get("path")
            acquisition=record['data'].get('acquisition',{})
            if not path and acquisition.get('bundle_id'):
                bundle=acquisition['bundle_id'];member=acquisition.get('member')
                if bundle not in bundle_inputs:
                    fail('REQUIRED_ASSET_UNAVAILABLE','Authenticated Library/bundle has not been materialized and hash verified by Codex','WAITING_DEPENDENCY',content_id=rid,file=member,current=acquisition)
                data=read_bounded(bundle_inputs[bundle],member)
                if sha(data)!=acquisition.get('sha256'):fail('BUNDLE_MEMBER_HASH','Acquired member differs from asset definition',file=member,content_id=rid)
                members={member: data}
                meta=record['data'].get('metadata',{})
                for page in meta.get('pages',[]):
                    pixel=read_bounded(bundle_inputs[bundle],page['path'])
                    if len(pixel)!=page.get('size_bytes') or sha(pixel)!=page['sha256']:fail('BUNDLE_PAGE_HASH','Pinned PNG differs',file=page['path'],content_id=rid)
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(pixel)) as image:
                        if image.width*image.height>16777216:fail('PAGE_PIXEL_BOUND','Decoded image exceeds pixel bound',file=page['path'])
                        image.verify()
                    members[page['path']]=pixel
                if meta.get('atlas_member'):
                    pixel=read_bounded(bundle_inputs[bundle],meta['atlas_member'])
                    if sha(pixel)!=meta.get('sha256'):fail('BUNDLE_PAGE_HASH','Pinned reused atlas differs',file=meta['atlas_member'],content_id=rid)
                    members[meta['atlas_member']]=pixel
                for name,content in members.items():
                    stored_path=sha(content)+'/'+PurePosixPath(name).name
                    info=dict(stored_path=stored_path,sha256=sha(content),bytes=len(content))
                    candidate['assets']['bundle_file:'+bundle+':'+name]=info
                    asset_bytes[stored_path]=content
                    if name==member:candidate['assets'][rid]=info
                continue
            if not path or path not in verified:
                fail("REQUIRED_ASSET_UNAVAILABLE", "Asset is not transferred/pinned; local filename or chat attachment is not delivery", "WAITING_DEPENDENCY", content_id=rid, file=path)
            entry, data = verified[path]
            stored_path = sha(data) + "/" + PurePosixPath(path).name
            candidate["assets"][rid] = dict(stored_path=stored_path, sha256=sha(data), bytes=len(data))
            asset_bytes[stored_path] = data
        candidate["generation"] += 1
        candidate["imports"][manifest["batch_id"]] = dict(manifest_sha256=receipt["manifest_sha256"], source_commit=source_commit,
            base_game_commit=manifest["base_game_commit"], applied_before_game_commit=game_commit,
            applied_ids=sorted(set(applied)), tool_version=TOOL_VERSION, supersedes=supersedes, status="IMPORTED", fixture=fixture)
        payload = encode(candidate)
        release_id = sha(payload)
        directory = self.root / "releases" / release_id
        directory.mkdir(parents=True, exist_ok=True)
        previous = self.pointer()
        for rid, info in candidate["assets"].items():
            content = asset_bytes.get(info["stored_path"])
            if content is None:
                content = read_bounded(self.root, f"releases/{previous['release_id']}/files/" + info["stored_path"])
            atomic_write(directory / "files" / info["stored_path"], content)
        atomic_write(directory / "release.json", payload)
        if interrupt in ("after_release", "before_activate"):
            fail("INTERRUPTED_BEFORE_ACTIVATE", "Injected interruption; prior active data/ledger preserved", "VALIDATED_NOT_APPLIED")
        previous_summary={k:v for k,v in previous.items() if k!='previous'} if previous else None
        pointer = dict(format="BARAM_ACTIVE_CONTENT", version=1, release_id=release_id, sha256=release_id,
                       bytes=len(payload), generation=candidate["generation"], previous=previous_summary)
        atomic_write(self.root / "ACTIVE.json", encode(pointer))
        self.load()  # record only the actual validated active version
        receipt.update(import_status="IMPORTED", applied_ids=sorted(set(applied)), applied_counts=count,
                       release_id=release_id, active_generation=candidate["generation"], fixture=fixture)
        if interrupt == "after_activate":
            receipt["receipt_recovery"] = "ACTIVE_OWNS_IMPORT_LEDGER_REIMPORT_RECONSTRUCTS_RECEIPT"
        return receipt

    def _schemas(self, manifest, verified, schema_root):
        schemas = {}
        pins = manifest.get("schema_hashes", manifest.get("schemas", {}))
        if isinstance(pins, list):
            pins = {x["path"]: x["sha256"] for x in pins}
        if not isinstance(pins, dict):
            fail("SCHEMA_PINS", "Schema hashes require pinned paths")
        for path, expected in pins.items():
            if isinstance(expected, dict):
                expected = expected.get("sha256")
            safe_relative(path)
            data = verified[path][1] if path in verified else read_bounded(schema_root, path, MAX_JSON) if schema_root else None
            if data is None or sha(data) != expected:
                fail("SCHEMA_HASH", "Schema hash is unavailable/mismatched", file=path)
            schemas[path] = decode(data, path)
        return schemas

    @staticmethod
    def _schema_validate(document, schema, file, schemas):
        try:
            import jsonschema
            from referencing import Registry, Resource
            resources = []
            for path, value in schemas.items():
                uri = value.get("$id", "urn:baram:schema:" + path)
                resources.append((uri, Resource.from_contents(native(value), default_specification=__import__("referencing.jsonschema", fromlist=["DRAFT202012"]).DRAFT202012)))
            registry = Registry().with_resources(resources)
            validator = jsonschema.validators.validator_for(native(schema))
            validator.check_schema(native(schema))
            errors = sorted(validator(native(schema), registry=registry).iter_errors(native(document)), key=lambda x: str(x.path))
            if errors:
                e = errors[0]
                fail("SCHEMA_VALIDATION", e.message, file=file, field=".".join(map(str, e.path)))
        except ImportError:
            fail("SCHEMA_ENGINE_UNAVAILABLE", "jsonschema is required for published schemas", "PENDING_CAPABILITY")
        except IntakeError:
            raise
        except Exception as error:
            fail("SCHEMA_RESOLUTION", "Schema/ref cannot be resolved locally: " + str(error), file=file)


def git_bytes(repo, commit, path, maximum=MAX_FILE):
    if not HEX40.fullmatch(commit):
        fail("COMMIT_PIN", "Git inputs require full immutable commit SHA")
    safe_relative(path)
    if not path.startswith("content-work/"):
        fail("UPSTREAM_SCOPE", "Only content-work/** may be read as Work input", file=path)
    result = subprocess.run(["git", "ls-tree", commit, "--", path], cwd=repo, capture_output=True, text=True, check=True)
    if not result.stdout:
        fail("UPSTREAM_FILE_MISSING", "Pinned upstream file absent", file=path)
    mode, kind, object_id = result.stdout.split("\t", 1)[0].split()
    if mode not in ("100644", "100755") or kind != "blob":
        fail("UPSTREAM_LINK", "Work input must be a regular blob", file=path)
    size = int(subprocess.check_output(["git", "cat-file", "-s", object_id], cwd=repo))
    if size > maximum:
        fail("UPSTREAM_SIZE", "Git blob exceeds bounded size", file=path)
    return subprocess.check_output(["git", "cat-file", "blob", object_id], cwd=repo)


def snapshot_package(repo, commit, manifest_path, destination):
    path = safe_relative(manifest_path)
    if not manifest_path.startswith("content-work/packages/") or path.name != "manifest.json":
        fail("HANDOFF_PACKAGE_PATH", "Handoff must point inside allowed package path")
    data = git_bytes(repo, commit, manifest_path)
    manifest = decode(data, manifest_path)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    atomic_write(destination / "manifest.json", data)
    schema_root = destination / "upstream-schemas"
    total = len(data)
    for item in manifest.get("files", []):
        relative = safe_relative(item["path"])
        data = git_bytes(repo, commit, str(path.parent / relative))
        total += len(data)
        if total > MAX_TOTAL:
            fail("SNAPSHOT_SIZE", "Pinned package snapshot too large")
        atomic_write(destination / relative, data)
    pins = manifest.get("schema_hashes", manifest.get("schemas", {}))
    paths = [x["path"] for x in pins] if isinstance(pins, list) else pins
    for schema_path in paths:
        if any(x.get('path')==schema_path for x in manifest.get('files',[])):
            continue  # package-local frozen schema, already copied and pinned
        relative = safe_relative(schema_path)
        upstream = schema_path if schema_path.startswith("content-work/schemas/") else "content-work/schemas/" + schema_path
        atomic_write(schema_root / relative, git_bytes(repo, commit, upstream, MAX_JSON))
    return destination, schema_root
