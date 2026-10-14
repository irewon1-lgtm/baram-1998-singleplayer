#!/usr/bin/env python3
"""Import a pinned private Baram tile-atlas bundle for local Codex/Godot work.

Never commits or uploads copyrighted assets. Runs using only the standard library.
"""
import argparse
import hashlib
import json
import math
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

EXPECTED_BUNDLE_SHA256 = "18581f104aa725eb615a205d428a10b46bd670b956876b99fa92ce32ebdc1514"
COUNTS = {"A": 4897, "B": 2973, "C": 6965}
EXPECTED_NAMES = {"MANIFEST.json", "README.txt"}
for _letter in COUNTS:
    EXPECTED_NAMES.add(f"Tile{_letter}_palette0_atlas.png")
    EXPECTED_NAMES.add(f"Tile{_letter}_frame_map.json")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def verify_bundle(bundle):
    if sha256_file(bundle) != EXPECTED_BUNDLE_SHA256:
        raise ValueError("ZIP hash differs from verified private atlas bundle")
    with ZipFile(bundle) as archive:
        if set(archive.namelist()) != EXPECTED_NAMES or len(archive.namelist()) != len(EXPECTED_NAMES):
            raise ValueError("ZIP contains missing, duplicate, or unexpected names")
        for item in archive.infolist():
            if item.file_size > 32_000_000:
                raise ValueError(f"ZIP member too large: {item.filename}")
        manifest = json.loads(archive.read("MANIFEST.json"))
        groups = manifest.get("groups", [])
        if manifest.get("total_ok") != 14835 or manifest.get("total_failed") != 0:
            raise ValueError("Unexpected summary in atlas manifest")
        if {item.get("group") for item in groups} != set(COUNTS) or len(groups) != 3:
            raise ValueError("Unexpected group list")
        for group in groups:
            c = group["group"]
            if group.get("frames_decoded") != COUNTS[c] or group.get("count") != COUNTS[c]:
                raise ValueError(f"Unexpected frame count for Tile{c}")
            for name_key, hash_key in (("atlas_name", "atlas_sha256"), ("map_name", "map_sha256")):
                name = group[name_key]
                if name not in EXPECTED_NAMES or sha256_bytes(archive.read(name)) != group[hash_key]:
                    raise ValueError(f"SHA-256 mismatch: {name}")
            mapping = json.loads(archive.read(group["map_name"]))
            entries = mapping.get("frames", [])
            if mapping.get("group") != c or mapping.get("tile_px") != 24 or mapping.get("columns") != 128:
                raise ValueError(f"Unexpected tile mapping schema for Tile{c}")
            if mapping.get("count") != COUNTS[c] or len(entries) != COUNTS[c]:
                raise ValueError(f"Unexpected frame table size for Tile{c}")
            for i, entry in enumerate(entries):
                if (entry.get("i") != i or entry.get("x") != (i % 128) * 24
                        or entry.get("y") != (i // 128) * 24):
                    raise ValueError(f"Frame coordinate mismatch in Tile{c} at {i}")
            png = archive.read(group["atlas_name"])
            if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"Bad PNG signature: {group['atlas_name']}")
            width, height = struct.unpack(">II", png[16:24])
            if (width, height) != (128 * 24, math.ceil(COUNTS[c] / 128) * 24):
                raise ValueError(f"PNG size mismatch in Tile{c}")
        return manifest


def install(bundle, out):
    manifest = verify_bundle(bundle)
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if not out.is_dir():
            raise ValueError("Output path exists and is not a directory")
        with ZipFile(bundle) as archive:
            if any(not (out / n).is_file() or sha256_file(out / n) != sha256_bytes(archive.read(n))
                   for n in EXPECTED_NAMES):
                raise ValueError("Output directory already exists with different or incomplete files")
        print(json.dumps({"status": "PASS_ALREADY_INSTALLED", "frames": 14835, "directory": str(out)}))
        return
    with tempfile.TemporaryDirectory(prefix="baram-private-stage-", dir=out.parent) as temporary:
        staging = Path(temporary)
        with ZipFile(bundle) as archive:
            for name in sorted(EXPECTED_NAMES):
                with archive.open(name) as reader, (staging / name).open("wb") as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
        staging.rename(out)
    print(json.dumps({"status": "PASS_PRIVATE_ATLAS_INSTALLED", "frames": manifest["total_ok"],
                      "groups": COUNTS, "directory": str(out)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="Private atlas ZIP exported from this chat")
    parser.add_argument("--out", type=Path, default=Path("private_assets/baram_tiles"))
    args = parser.parse_args()
    try:
        install(args.bundle, args.out)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())