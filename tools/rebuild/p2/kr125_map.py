#!/usr/bin/env python3
"""Consume KR1.25 MAP/DAT bytes into a private inspection-only map package.

The 4.x EPF tile atlas is deliberately not a dependency. KR1.25 uses raw
24x24 indexed bitmaps and a u16/u32 offset-table SOBJECT.OTB. The original
executable's static instructions provide an independent reference for tile
numbering, chunk size, transparency and directional collision. This is not
an assertion that the client is the selected 1998-2001 city revision.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

from PIL import Image

SCHEMA = "kr125-map-runtime-v1"
CLIENT_SHA256 = "62642ca3ef492f58947abb2c17cbae5b5a60d5f96fd146704b7d99d1aad3bcef"
TILE_PX = 24
CHUNK_SIZE = 64
CHUNK_BYTES = CHUNK_SIZE * CHUNK_SIZE * 4
DIRS = {"north": (0, -1, 1, 4), "east": (1, 0, 2, 8),
        "south": (0, 1, 4, 1), "west": (-1, 0, 8, 2)}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def original_exe_evidence(exe: bytes) -> list[dict]:
    """Require the measured reference instructions; do not silently guess."""
    # File offsets follow this PE's .text and .data section mapping.
    spans = [
        ("64x64 disk chunks copied into a 128x128 sliding memory window",
         0x40DFCC, 0x40DFE9, b"\x68\x00\x01\x00\x00"),
        ("ground graphics: 24px, B base1024, A extension2048..2175",
         0x40F0C9, 0x40F13C, b"\x3d\x00\x04\x00\x00"),
        ("A prepends one zero tile; B uses no prefix; C prepends one zero tile",
         0x428401, 0x428476, b"\x8d\x85\x40\x02\x00\x00"),
        ("object stack draws native tile words upward from base row",
         0x40F738, 0x40F7A6, b"\x83\xee\x18"),
        ("SOTP raw bytes have one zero byte prepended for null object",
         0x40DE04, 0x40DE1D, b"\x6a\x01"),
        ("movement target and source edge checks; B terrain blocked",
         0x412D73, 0x412E4A, b"\x81\xf9\x00\x04\x00\x00"),
        ("index0 is transparent for object blit", 0x429CD3, 0x429CE1,
         b"\xac\x0a\xc0\x75\x03"),
    ]
    result = []
    for meaning, start, end, anchor in spans:
        offset = start - 0x401000 + 0x400
        data = exe[offset:offset + end - start]
        if len(data) != end - start or anchor not in data:
            raise ValueError(f"Original executable evidence missing: {meaning}")
        result.append({"meaning": meaning, "start_va": hex(start), "end_va_exclusive": hex(end),
                       "file_offset": offset, "length": len(data), "sha256": sha(data)})
    deltas = exe[0x326F0:0x326F8]
    if deltas != b"\x00\x01\x00\xff\xff\x00\x01\x00":
        raise ValueError("Original direction delta table mismatch")
    result.append({"meaning": "N/E/S/W dx then dy table", "start_va": "0x4342f0",
                   "file_offset": 0x326F0, "length": 8, "sha256": sha(deltas),
                   "dx": [0, 1, 0, -1], "dy": [-1, 0, 1, 0]})
    return result


def decode_otb(data: bytes, tile_count: int) -> list[tuple[int, ...]]:
    if len(data) < 2:
        raise ValueError("OTB missing count")
    count, = struct.unpack_from("<H", data)
    if not 1 <= count <= 10000 or len(data) < 2 + 4 * count:
        raise ValueError("OTB offset table outside file")
    offsets = struct.unpack_from(f"<{count}I", data, 2)
    base = 2 + 4 * count
    if offsets[0] != 0 or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("OTB offsets not strictly increasing from zero")
    objects = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < count else len(data) - base
        record = data[base + start:base + end]
        if end <= start or base + end > len(data) or not record:
            raise ValueError(f"OTB object{index} payload bounds")
        height = record[0]
        if len(record) != 1 + height * 2:
            raise ValueError(f"OTB object{index} height mismatch")
        words = struct.unpack_from(f"<{height}H", record, 1)
        if any(word > tile_count for word in words):
            raise ValueError(f"OTB object{index} missing C tile")
        objects.append(words)
    if objects[0]:
        raise ValueError("OTB null object is not empty")
    return objects


def ground_tile(word: int, counts: dict[str, int]) -> tuple[str, int] | None:
    if word == 0:
        return None
    if 0 < word < 1024:
        group, index = "A", word - 1
    elif 1024 <= word < 2048:
        group, index = "B", word - 1024
    elif 2048 <= word <= 2175:
        group, index = "A", word - 1024 - 1
    else:
        raise ValueError(f"Unsupported ground word {word}")
    if not 0 <= index < counts[group]:
        raise ValueError(f"Ground {word} references missing {group}:{index}")
    return group, index


def decode_map(data: bytes, counts: dict[str, int], object_count: int) -> tuple[list[int], list[int]]:
    # Multi-chunk maps need independent width/height metadata from the server.
    # Odd trailers are retained and rejected, never truncated to a happy size.
    if len(data) != CHUNK_BYTES:
        raise ValueError(f"Map size {len(data)} is not one exact 64x64 storage chunk")
    words = struct.unpack(f"<{CHUNK_SIZE * CHUNK_SIZE * 2}H", data)
    ground, objects = list(words[0::2]), list(words[1::2])
    for cell, (word, obj) in enumerate(zip(ground, objects)):
        try:
            ground_tile(word, counts)
        except ValueError as exc:
            raise ValueError(f"Cell{cell}: {exc}") from exc
        if not 0 <= obj < object_count:
            raise ValueError(f"Cell{cell} object {obj} out of OTB bounds")
    return ground, objects


def can_step(ground: list[int], masks: list[int], x: int, y: int, direction: str) -> bool:
    dx, dy, source_bit, target_bit = DIRS[direction]
    tx, ty = x + dx, y + dy
    if not (0 <= x < 64 and 0 <= y < 64 and 0 <= tx < 64 and 0 <= ty < 64):
        return False
    src, dst = y * 64 + x, ty * 64 + tx
    return not (masks[src] & source_bit or masks[dst] & target_bit or 1024 <= ground[dst] < 2048)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-zip", required=True, type=Path)
    parser.add_argument("--parser-dir", required=True, type=Path,
                        help="Private restored legacy_assets.py directory")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maps", default="1,99,100")
    args = parser.parse_args()
    output = args.output.resolve()
    repo = Path(__file__).resolve().parents[3]
    if output == repo or repo in output.parents:
        raise ValueError("Decoded originals must stay outside the public checkout")
    client = args.client_zip.read_bytes()
    if sha(client) != CLIENT_SHA256:
        raise ValueError("KR1.25 ZIP SHA256 mismatch")
    parser_path = args.parser_dir / "legacy_assets.py"
    sys.path.insert(0, str(args.parser_dir))
    import legacy_assets as legacy
    output.mkdir(parents=True, exist_ok=True)
    (output / "objects").mkdir(exist_ok=True)
    with zipfile.ZipFile(args.client_zip) as archive:
        entries = legacy.dat_entries(archive.read("winbaram.dat"))
        exe = archive.read("winbaram.exe")
        evidence = original_exe_evidence(exe)
        names = {name.casefold(): name for name in archive.namelist()}
        source_names = ["tilea.bmp", "tileb.bmp", "tilec.bmp", "windland.pal", "sobject.otb", "sotp.dat"]
        raw = {name: entries[name][2] for name in source_names}
        palette = legacy.read_palettes(raw["windland.pal"])
        if len(palette) != 1:
            raise ValueError("KR1.25 palette count mismatch")
        rgb = palette[0].colors
        counts = {group: len(raw[f"tile{group.lower()}.bmp"]) // 576 for group in "ABC"}
        if any(len(raw[f"tile{group.lower()}.bmp"]) % 576 for group in "ABC"):
            raise ValueError("Tile bitmap length not divisible by 24x24")
        objects = decode_otb(raw["sobject.otb"], counts["C"])
        if len(raw["sotp.dat"]) != len(objects):
            raise ValueError("SOTP count differs from OTB")
        flags = [0] + list(raw["sotp.dat"])
        bitmaps: dict[tuple[str, int], Image.Image] = {}
        written_objects: set[int] = set()

        def tile(group: str, index: int, transparent: bool) -> Image.Image:
            key = (group, index)
            if key not in bitmaps:
                part = raw[f"tile{group.lower()}.bmp"][index * 576:(index + 1) * 576]
                pixels = bytes(channel for value in part for channel in (*rgb[value], 0 if transparent and value == 0 else 255))
                bitmaps[key] = Image.frombytes("RGBA", (24, 24), pixels)
            return bitmaps[key]

        inventory = []
        map_names = sorted((name for name in archive.namelist() if name.lower().endswith(".map")), key=lambda n: int(Path(n).stem))
        for name in map_names:
            data = archive.read(name)
            record = {"native_id": int(Path(name).stem), "member": name, "size_bytes": len(data), "sha256": sha(data)}
            try:
                decode_map(data, counts, len(objects))
                record.update(status="STRUCTURE_AND_REFERENCES_VALID", storage_grid=[64, 64])
            except ValueError as exc:
                record.update(status="BLOCKED", reason=str(exc))
            inventory.append(record)

        produced = []
        selected = [int(value) for value in args.maps.split(",")]
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("Selected map set empty or duplicated")
        for native_id in selected:
            member = names.get(f"{native_id}.map")
            if not member:
                raise ValueError(f"Required map{native_id} missing")
            data = archive.read(member)
            ground, obj_ids = decode_map(data, counts, len(objects))
            floor = Image.new("RGBA", (64 * 24, 64 * 24), (0, 0, 0, 255))
            placements = []
            dependency_ground = set()
            dependency_objects = set()
            occupied = []
            edge_masks = [flags[index] for index in obj_ids]
            for cell, (word, obj) in enumerate(zip(ground, obj_ids)):
                x, y = cell % 64, cell // 64
                decoded = ground_tile(word, counts)
                if decoded:
                    group, index = decoded
                    floor.alpha_composite(tile(group, index, False), (x * 24, y * 24))
                    dependency_ground.add(decoded)
                    occupied.append((x, y))
                if not obj:
                    continue
                dependency_objects.add(obj)
                stack = objects[obj]
                if not stack:
                    raise ValueError(f"Nonzero map object{obj} has empty stack")
                image_name = f"objects/object-{obj}.png"
                image_path = output / image_name
                # Regenerate referenced objects once per conversion. File existence
                # cannot validate an older parser/palette/input generation.
                if obj not in written_objects:
                    object_image = Image.new("RGBA", (24, 24 * len(stack)), (0, 0, 0, 0))
                    for level, tile_word in enumerate(stack):
                        if tile_word:
                            object_image.alpha_composite(tile("C", tile_word - 1, True), (0, (len(stack) - 1 - level) * 24))
                    object_image.save(image_path)
                    written_objects.add(obj)
                placements.append({"native_id": obj, "frame_png": image_name, "x": x * 24,
                                   "y": (y - len(stack) + 1) * 24, "anchor_x": 0,
                                   "anchor_y": (len(stack) - 1) * 24, "grid_x": x, "grid_y": y,
                                   "depth_y": y * 24 + 24, "layer": "depth", "height": len(stack),
                                   "native_tile_words_bottom_to_top": list(stack), "edge_mask": flags[obj]})
            floor_name = f"map-{native_id}-floor.png"
            floor.save(output / floor_name)
            collision = {"status": "STATIC_EXE_DERIVED", "ground_ids": ground, "edge_masks": edge_masks,
                         "blocked_cells": [[i % 64, i // 64] for i, word in enumerate(ground) if 1024 <= word < 2048 or edge_masks[i] == 15],
                         "ground_block_rule": "1024 <= target_ground_word < 2048",
                         "direction_bits": {name: {"dx": values[0], "dy": values[1], "source_edge_bit": values[2], "target_edge_bit": values[3]} for name, values in DIRS.items()},
                         "boundary": "64x64 inspected storage chunk only; active server rectangle unknown",
                         "original_client_execution": "NOT_RUN"}
            record = {"schema": SCHEMA, "native_id": native_id, "source_map_path": f"LIB-009!{member}",
                      "source_map_sha256": sha(data), "grid_width": 64, "grid_height": 64,
                      "grid_scope": "one exact native storage chunk; active server dimensions UNKNOWN",
                      "active_grid_width": None, "active_grid_height": None,
                      "tile_width": 24, "tile_height": 24, "projection": "orthogonal",
                      "pixel_offset": [0, 0], "floor_png": floor_name, "objects": placements,
                      "occupied_ground_bounds": [min(x for x, _ in occupied), min(y for _, y in occupied), max(x for x, _ in occupied), max(y for _, y in occupied)] if occupied else None,
                      "collisions": collision,
                      "exits": {"status": "UNKNOWN", "items": []},
                      "return_points": {"status": "UNKNOWN", "items": []},
                      "city_name": None, "historical_match": "UNVERIFIED_KR125_NOT_TARGET_PROFILE",
                      "dependencies": {"ground_frames": [f"KR125/{g}:{i}" for g, i in sorted(dependency_ground)],
                                       "object_ids": sorted(dependency_objects), "palette": "KR125/WINDLAND.PAL:0"}}
            map_file = f"map-{native_id}.json"
            write_json(output / map_file, record)
            # Static composition is an inspection artifact, not a gameplay pass.
            preview = floor.copy()
            for obj in sorted(placements, key=lambda item: (item["depth_y"], item["grid_x"])):
                with Image.open(output / obj["frame_png"]) as image:
                    preview.alpha_composite(image, (obj["x"], obj["y"]))
            preview.save(output / f"map-{native_id}-composite.png")
            outcomes = Counter()
            examples = {}
            for y in range(64):
                for x in range(64):
                    for direction in DIRS:
                        status = "allowed" if can_step(ground, edge_masks, x, y, direction) else "blocked"
                        outcomes[status] += 1
                        examples.setdefault(status, {"x": x, "y": y, "direction": direction})
            produced.append({"native_id": native_id, "json": map_file, "floor_png": floor_name,
                             "composite_png": f"map-{native_id}-composite.png", "object_placements": len(placements),
                             "static_move_outcomes": dict(outcomes), "static_move_examples": examples})
        source_usage = [{"source_id": f"LIB-009!winbaram.dat!{entries[name][0]}",
                         "dat_offset": entries[name][1], "size_bytes": len(raw[name]), "sha256": sha(raw[name])} for name in source_names]
        index = {"schema": SCHEMA, "source_zip_sha256": sha(client), "source_zip_bytes": len(client),
                 "source_id": "LIB-009", "source_exe_sha256": sha(exe), "sources": source_usage,
                 "parser_sha256": sha(parser_path.read_bytes()), "converter_sha256": sha(Path(__file__).read_bytes()),
                 "maps": produced, "objects_total_declared": len(objects), "tile_counts": counts,
                 "map_inventory": inventory, "independent_static_executable_evidence": evidence,
                 "limitations": ["No server active grid dimensions, map names, exits or city returns imported.",
                                 "No claim that KR1.25 geography matches the selected 1998-2001 profile.",
                                 "No original executable runtime, native platform or actor occlusion validation in this converter.",
                                 "4.x/undated tile atlases deliberately not consumed.",
                                 "All 218 source maps retained in inventory; nonexact chunk and broken references remain BLOCKED."]}
        write_json(output / "index.json", index)
        artifacts = [{"path": str(path.relative_to(output)), "size_bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
                     for path in sorted(output.rglob("*")) if path.is_file() and path.name not in ("ARTIFACTS.json", "legacy_assets.py", "legacy_maps.py", "winbaram.exe", "disasm.txt") and "__pycache__" not in str(path)]
        write_json(output / "ARTIFACTS.json", artifacts)
        print(json.dumps({"status": "GENERATED_PRIVATE_INSPECTION_PACKAGE", "maps_rendered": len(produced),
                          "map_structure_valid": sum(row["status"] == "STRUCTURE_AND_REFERENCES_VALID" for row in inventory),
                          "map_blocked": sum(row["status"] == "BLOCKED" for row in inventory),
                          "object_placements": sum(row["object_placements"] for row in produced)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print(f"KR125_MAP_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2)
