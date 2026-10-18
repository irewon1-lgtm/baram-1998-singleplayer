#!/usr/bin/env python3
"""Private P0/P1 compiler; requires the user's frozen Project1998 sources and DATs.

No third-party game bytes live in this repository. The official, pinned renderer
is loaded from the supplied checkout as an independent reference, never vendored.
The selected maps retain raw words, object IDs, dimensions and all warp rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

PINS = {
    "4x/NexusTK.dat": "9de5ebe95682ee6587ccf6f9e55227bdf671edd3c7197f77ab3021a6bc84eca4",
    "533/Tile.dat": "9eb60ff381063e24b589126f33620db3157adf3851d6de9a8009619ad558473f",
}
RENDERER_PIN = "6c26dd2c334ae54fe1e4d27e0f56e92bca34c62c42bed0fb2873997d74e47c71"
MAP_IDS = (0, 2, 4711)
CELL = 24


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def dat_entries(raw):
    """Validate the actual DAT directory, including its EOF sentinel."""
    count, = struct.unpack_from("<I", raw)
    assert 1 < count < 100000 and 4 + count * 17 <= len(raw)
    records = []
    for i in range(count):
        offset, = struct.unpack_from("<I", raw, 4 + 17 * i)
        name = raw[8 + 17 * i:21 + 17 * i].split(b"\0", 1)[0].decode("ascii").upper()
        records.append((offset, name))
    assert all(a[0] <= b[0] for a, b in zip(records, records[1:]))
    # Both fixed-hash client archives contain an eight-byte trailer after the
    # sentinel offset. The official parser correctly excludes it from members.
    assert records[0][0] >= 4 + count * 17 and records[-1][0] == len(raw) - 8
    return {a[1]: raw[a[0]:b[0]] for a, b in zip(records, records[1:]) if a[1]}


def palettes(raw):
    starts = [match.start() for match in re.finditer(b"DLPalette", raw)]
    assert starts
    result = []
    for begin, end in zip(starts, starts[1:] + [len(raw)]):
        assert end - begin >= 1024
        result.append(np.frombuffer(raw[end - 1024:end], np.uint8).reshape(256, 4)[:, :3].copy())
    return result


class Epf:
    def __init__(self, raw):
        self.raw = raw
        self.count, = struct.unpack_from("<H", raw)
        self.toc = 12 + struct.unpack_from("<I", raw, 8)[0]
        assert self.toc + 16 * self.count <= len(raw)

    def decode(self, index, palette, dye=0):
        assert 0 <= index < self.count
        top, left, bottom, right, pixels, mask = struct.unpack_from("<hhhhII", self.raw, self.toc + 16 * index)
        width, height = right - left, bottom - top
        assert width >= 0 and height >= 0
        if not width or not height:
            return None
        assert mask - pixels == width * height, (index, "EPF raster length")
        assert 12 + mask <= self.toc
        indices = np.frombuffer(self.raw, np.uint8, width * height, 12 + pixels).reshape(height, width).copy()
        alpha = np.zeros((height, width), np.uint8)
        cursor = 12 + mask
        for y in range(height):
            x = 0
            while True:
                assert cursor < self.toc, (index, "EPF stencil end")
                run = self.raw[cursor]
                cursor += 1
                if run == 0:
                    break
                length = run - 128 if run > 128 else run
                assert length > 0 and x + length <= width, (index, y, x, run, width)
                if run > 128:
                    alpha[y, x:x + length] = 255
                x += length
        if dye:
            # Source Protocol.md: add (8 * colour), wrapping u8, only for indices >= 0x30.
            selected = indices >= 0x30
            indices[selected] = ((indices[selected].astype(np.uint16) + 8 * dye) & 255).astype(np.uint8)
        return Image.fromarray(np.dstack((palette[indices], alpha))), [left, top]


def table(raw):
    rows = {}
    for line in raw.decode("ascii").splitlines():
        if line.startswith("ID "):
            fields = {}
            for part in line.strip().strip(",").split(", "):
                key, value = part.rsplit(" ", 1)
                fields[key] = int(value)
            rows[fields["ID"]] = fields
    return rows


def sobj(raw):
    count, = struct.unpack_from("<I", raw)
    offset = 4
    columns, flags = [], []
    for i in range(count):
        flag, length = raw[offset:offset + 2]
        flags.append(flag)
        offset += 2
        columns.append(list(struct.unpack_from("<" + "H" * length, raw, offset)))
        offset += length * 2
        # The documented five-byte separator has nonzero variants in the real
        # archive. Its contents are opaque, not a reason to shift record IDs.
        assert offset + 5 <= len(raw), (i, "SObj record truncated")
        offset += 5
    return columns, flags


class Atlas:
    def __init__(self):
        self.rows = []
        self.regions = {}

    def add(self, key, decoded):
        if key in self.regions:
            return
        if decoded is None:
            self.regions[key] = {"rect": [0, 0, 0, 0], "offset": [0, 0], "empty_in_source": True}
            return
        image, offset = decoded
        self.rows.append((key, image, offset))

    def write(self, path):
        x, y, row_height = 1, 1, 0
        placed = []
        for key, image, offset in self.rows:
            assert image.width + 2 <= 2048 and image.height + 2 <= 2048
            if x + image.width + 1 > 2048:
                x, y, row_height = 1, y + row_height + 2, 0
            placed.append((key, image, offset, x, y))
            self.regions[key] = {"rect": [x, y, image.width, image.height], "offset": offset,
                                 "rgba_sha256": sha(image.tobytes())}
            x += image.width + 2
            row_height = max(row_height, image.height)
        height = y + row_height + 1
        image = Image.new("RGBA", (2048, height))
        for key, part, offset, x, y in placed:
            image.alpha_composite(part, (x, y))
        image.save(path)
        return self.regions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--ko-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checkout = Path(__file__).resolve().parents[3]
    out = args.output.resolve()
    if out.is_relative_to(checkout):
        raise ValueError("Private original/decoded assets must remain outside the public checkout")
    out.mkdir(parents=True, exist_ok=True)
    (out / "reference").mkdir(exist_ok=True)
    (out / "maps").mkdir(exist_ok=True)
    source = args.source.resolve()
    official_path = source / "re/render_maps.py"
    assert sha(official_path.read_bytes()) == RENDERER_PIN
    spec = importlib.util.spec_from_file_location("project1998_frozen_reference", official_path)
    official = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(official)
    for path, expected in PINS.items():
        assert sha((args.originals / path).read_bytes()) == expected, path
    tile_raw = (args.originals / "533/Tile.dat").read_bytes()
    legacy_raw = (args.originals / "4x/NexusTK.dat").read_bytes()
    tiles = dat_entries(tile_raw)
    legacy = dat_entries(legacy_raw)
    assert tiles == official.read_dat(args.originals / "533/Tile.dat")
    objects, _ = sobj(tiles["SOBJ.TBL"])
    legacy_objects, legacy_flags = sobj(legacy["SOBJ.TBL"])
    assert objects == official.TileSet._parse_sobj(tiles["SOBJ.TBL"])
    # Collision uses the original 4.x flag, not the reauthored 5.33 flag.
    for row in csv_rows(source / "game-data/ObjectFlagOverrides.csv"):
        if (row.get("Obj") or "").isdigit():
            legacy_flags[int(row["Obj"])] = int(row["Flag"], 0)
    ground_epf, object_epf = Epf(tiles["TILE.EPF"]), Epf(tiles["TILEC.EPF"])
    ground_pals, object_pals = palettes(tiles["TILE.PAL"]), palettes(tiles["TILEC.PAL"])
    ground_palette = np.frombuffer(tiles["TILE.TBL"], np.uint8, ground_epf.count * 2, 4)[::2]
    object_palette = np.frombuffer(tiles["TILEC.TBL"], np.uint8, object_epf.count * 2, 4)[::2]
    remap = official.load_sheet2(str(source / "game-data/Tile533Map.csv"))
    dimensions = {int(row["id"]): row for row in csv_rows(source / "game-data/map_index.csv")}
    ko_maps = {int(row["MapId"]): row["MapName"] for row in csv_rows(args.ko_source / "game-data-ko/Maps.csv")}
    warps = csv_rows(source / "game-data/Warps.csv")
    overlays = csv_rows(source / "game-data/MapCells.csv")
    fixed_spawns = csv_rows(source / "game-data/Spawns.csv")
    ground_images, frame_images, maps = {}, {}, []
    for mid in MAP_IDS:
        row = dimensions[mid]
        width, height = int(row["xs"]), int(row["ys"])
        raw = (source / f"game-data/maps/TK{mid}.map").read_bytes()
        assert len(raw) == width * height * 4
        cells = np.frombuffer(raw, "<u2").reshape(-1, 2)
        words = set(map(int, cells[:, 0]))
        lookup = {}
        for word in sorted(words):
            fid = (remap[word - 0xC000] if word >= 0xC000 else word) if word else 0
            assert word == 0 or 0 < fid < ground_epf.count, (mid, word, fid)
            lookup[str(word)] = fid
            if fid not in ground_images:
                image = Image.new("RGB", (CELL, CELL))
                if fid:
                    decoded = ground_epf.decode(fid, ground_pals[int(ground_palette[fid])])
                    if decoded:
                        part, offset = decoded
                        image.paste(part, tuple(offset), part)
                ground_images[fid] = image
        used_objects = sorted(set(map(int, cells[:, 1])) - {0})
        for object_id in used_objects:
            assert object_id < len(objects) and object_id < len(legacy_flags)
            for fid in objects[object_id]:
                if fid and fid not in frame_images:
                    frame_images[fid] = object_epf.decode(fid, object_pals[int(object_palette[fid])])
        raw_path = f"maps/TK{mid}.map"
        (out / raw_path).write_bytes(raw)
        maps.append({"id": mid, "name": row["name"], "name_ko": ko_maps.get(mid, row["name"]),
                     "width": width, "height": height, "raw_path": raw_path, "source_sha256": sha(raw),
                     "layer": "FILE_UNMODIFIED; authored overlays preserved separately, not silently baked",
                     "ground_lookup": lookup, "object_ids": used_objects,
                     "warps": [{key: int(value) for key, value in warp.items()} for warp in warps if warp["SourceMapId"] == str(mid)],
                     "authored_map_cells": [r for r in overlays if r.get("Map") == str(mid)],
                     "fixed_spawns": [r for r in fixed_spawns if r["SpnMapId"] == str(mid)]})
    atlas = Atlas()
    for fid, image in frame_images.items():
        atlas.add(str(fid), image)
    frame_regions = atlas.write(out / "objects.png")
    ground_ids = sorted(ground_images)
    ground_slots = {fid: index for index, fid in enumerate(ground_ids)}
    ground_atlas = Image.new("RGB", (64 * CELL, math.ceil(len(ground_ids) / 64) * CELL))
    for fid in ground_ids:
        n = ground_slots[fid]
        ground_atlas.paste(ground_images[fid], (n % 64 * CELL, n // 64 * CELL))
    ground_atlas.save(out / "ground.png")
    for m in maps:
        m["ground_lookup"] = {word: ground_slots[fid] for word, fid in m["ground_lookup"].items()}

    # Independent full-map composition vs unmodified official renderer, including transparency.
    reference_tiles = official.TileSet(str(args.originals / "533/Tile.dat"))
    tests = []
    for m in maps:
        width, height, mid = m["width"], m["height"], m["id"]
        cells = np.frombuffer((out / m["raw_path"]).read_bytes(), "<u2").reshape(-1, 2)
        canvas = Image.new("RGB", (width * CELL, height * CELL))
        for n, (word, _) in enumerate(cells):
            word = int(word)
            fid = remap[word - 0xC000] if word >= 0xC000 else word
            canvas.paste(ground_images[fid], (n % width * CELL, n // width * CELL))
        for n, (_, object_id) in enumerate(cells):
            if not object_id:
                continue
            for k, fid in enumerate(objects[int(object_id)]):
                if not fid or not frame_images[fid]:
                    continue
                part, (left, top) = frame_images[fid]
                canvas.paste(part, (n % width * CELL + left, (n // width - k) * CELL + top), part)
        reference, *_ = official.render_map(reference_tiles, mid, official.load_index())
        reference.save(out / f"reference/TK{mid}-official.png")
        canvas.save(out / f"reference/TK{mid}-converted.png")
        a, b = np.asarray(canvas), np.asarray(reference)
        mismatch = int(np.count_nonzero(np.any(a != b, axis=2)))
        tests.append({"map_id": mid, "pixels": width * height * CELL * CELL,
                      "different_pixels": mismatch, "status": "PASS" if mismatch == 0 else "FAIL"})
        assert mismatch == 0, (mid, "map composition differs from official reference", mismatch)

    # Original 4.x human and rabbit, no mirrored or procedurally drawn replacement frames.
    actor_atlas = Atlas()
    epfs = {name: Epf(legacy[name + ".EPF"]) for name in ("BODY", "HEAD", "MONSTER")}
    pals = {name: palettes(legacy[name + ".PAL"]) for name in epfs}
    tables = {name: table(legacy[name + ".TBL"]) for name in epfs}
    body_id, head_id = 2, 0
    actor_frames = {}
    sheet = Image.new("RGB", (4 * 210, 5 * 126), "#192025")
    draw = ImageDraw.Draw(sheet)
    animation_rows = [("idle", 0), ("walk", 0), ("walk", 1), ("walk", 2), ("attack", 0)]
    for direction in range(4):
        for action in ("idle", "walk", "attack"):
            sequence = []
            for tick in range(1 if action == "idle" else (3 if action == "walk" else 2)):
                relative = direction * 3 + tick if action != "attack" else 24 + 2 * direction + tick
                frame_key = f"player-{action}-{direction}-{tick}"
                parts = []
                provenance = []
                for name, identity in (("BODY", body_id), ("HEAD", head_id)):
                    row = tables[name][identity]
                    frame_index = row["Starting"] + relative
                    decoded = epfs[name].decode(frame_index, pals[name][row["Palette"]])
                    assert decoded, (name, frame_index)
                    # Independent frame raster/stencil parity with the official format authority.
                    official_dec = official.decode_frame(legacy[name + ".EPF"], official.epf_entries(legacy[name + ".EPF"])[1], frame_index, pals[name][row["Palette"]])
                    _, _, w, h, rgb, alpha = official_dec
                    assert np.array_equal(np.asarray(decoded[0]), np.dstack((rgb, alpha.astype(np.uint8) * 255)))
                    parts.append(decoded)
                    provenance.append({"member": name + ".EPF", "part_id": identity, "frame": frame_index,
                                       "palette": row["Palette"], "dye": 0})
                union = [min(p[1][0] for p in parts), min(p[1][1] for p in parts),
                         max(p[1][0] + p[0].width for p in parts), max(p[1][1] + p[0].height for p in parts)]
                composite = Image.new("RGBA", (union[2] - union[0], union[3] - union[1]))
                for image, offset in parts:
                    composite.alpha_composite(image, (offset[0] - union[0], offset[1] - union[1]))
                actor_atlas.add(frame_key, (composite, union[:2]))
                sequence.append({"key": frame_key, "source_frames": provenance})
            actor_frames[f"{action}-{direction}"] = sequence
    mob = next(row for row in csv_rows(source / "game-data/mobs.csv") if row["MobId"] == "1")
    rabbit_row = tables["MONSTER"][int(mob["MobLook"])]
    for direction in range(4):
        sequence = []
        for tick in range(rabbit_row["Walk"]):
            index = rabbit_row["Starting"] + direction * rabbit_row["Walk"] + tick
            decoded = epfs["MONSTER"].decode(index, pals["MONSTER"][rabbit_row["Palette"]], int(mob["MobLookColor"]))
            assert decoded
            key = f"rabbit-{direction}-{tick}"
            actor_atlas.add(key, decoded)
            sequence.append({"key": key, "source_frame": index})
        actor_frames[f"rabbit-{direction}"] = sequence
    actors = actor_atlas.write(out / "actors.png")
    for row_index, (action, tick) in enumerate(animation_rows):
        for direction in range(4):
            key = actor_frames[f"{action}-{direction}"][tick]["key"]
            image = next(image for k, image, _ in actor_atlas.rows if k == key)
            big = image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)
            x, y = direction * 210, row_index * 126
            sheet.paste(big, (x + 80, y + 20), big)
            draw.text((x + 6, y + 5), f"{action} {tick} / {['N','E','S','W'][direction]}", fill="white")
    sheet.save(out / "reference/player-directions.png")
    rabbit_sheet = Image.new("RGB", (4 * 150, 100), "#444a35")
    for direction in range(4):
        key = actor_frames[f"rabbit-{direction}"][0]["key"]
        image = next(image for k, image, _ in actor_atlas.rows if k == key)
        big = image.resize((image.width * 3, image.height * 3), Image.Resampling.NEAREST)
        rabbit_sheet.paste(big, (direction * 150 + 50, 20), big)
    rabbit_sheet.save(out / "reference/rabbit-directions.png")
    data = {"schema": "project1998.p2.assets.v1", "cell_size": CELL,
            "game_world_version": "4.95", "tile_art_version": "5.33; explicit Tile533Map.csv translation",
            "map_layer": "source FILE; authored overlay rows preserved separately",
            "maps": maps, "objects": {str(i): {"frames": objects[i], "collision_flags_4x": legacy_flags[i]} for i in sorted({i for m in maps for i in m['object_ids']})},
            "object_frames": frame_regions, "actor_regions": actors, "animations": actor_frames,
            "rabbit_source": mob, "rabbit_animation_table": rabbit_row,
            "animation_binding": {"human_direction_order": ["north", "east", "south", "west"],
                                  "walk_frames": "0..11, three per direction; source first front-view head pose=6",
                                  "human_pose_assignment": "original frame contact sheet + existing 4.91 motion mapping; source timing not claimed",
                                  "attack": "original unarmed body/head poses 24..31; no fabricated hit/skill rule",
                                  "rabbit": "Monster.tbl Starting + direction*Walk + tick; MobLookColor ramp shift, never frame-offset"},
            "pins": PINS, "renderer_sha256": RENDERER_PIN}
    save_json(out / "assets.json", data)
    files = [{"path": str(p.relative_to(out)), "size": p.stat().st_size, "sha256": sha(p.read_bytes())}
             for p in sorted(out.rglob('*')) if p.is_file()]
    save_json(out / "BUILD_ASSETS_MANIFEST.json", {"files": files, "source_inputs": PINS})
    save_json(out / "CONVERSION_TESTS.json", {"status": "PASS", "maps": tests,
              "raw_source_maps_byte_identical": True, "original_actor_frames": len(actor_atlas.rows),
              "ground_atlas_frames": len(ground_images), "object_atlas_frames": len(frame_images),
              "external_editor_screenshot_comparison": "PENDING_SEPARATE_VISUAL_QA",
              "source_resource_redistribution": "private user test only; not committed"})
    print(json.dumps({"maps": tests, "actors": len(actor_atlas.rows), "ground_frames": len(ground_images),
                      "object_frames": len(frame_images)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
