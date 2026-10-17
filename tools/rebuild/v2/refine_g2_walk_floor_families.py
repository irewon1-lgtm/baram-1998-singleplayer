#!/usr/bin/env python3
"""Remove whole-cell terrain lotteries from remaining mixed walk-floor families.

Consumes native pixels already present in the retained Korean runtime. Fire,
cave, and crypt use their continuous original base tile; existing wall pixels,
outcrops, actors, portals, contracts, collisions, and save identity stay exact.
"""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from repair_g2_world import Repair as Native, digest, filehash, write

BASES = {"fire": 284, "cave": 291, "crypt": 324}
PRESENTATION_KEYS = {"ground_layers", "ground_chunks", "visual_style", "overview_png", "presentation_ground_ids"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "native-source", "output", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing existing generation")
    shutil.copytree(args.source, args.output)
    before = json.loads((args.source / "gameplay_content.json").read_text())
    data = deepcopy(before)
    native = Native(args.native_source, args.output)
    rows = []
    for mid, game_map in data["maps"].items():
        style = game_map.get("style")
        if style not in BASES or game_map["width"] <= 20:
            continue
        width, height = game_map["width"], game_map["height"]
        blocked = np.frombuffer(base64.b64decode(game_map["blocked_base64"]), dtype=np.uint8).reshape(height, width).astype(bool)
        floor = Image.new("RGBA", (width * 24, height * 24))
        for layer in game_map["ground_layers"]:
            floor.alpha_composite(Image.open(args.source / layer["path"]).convert("RGBA"), (layer["x"], layer["y"]))
        original = np.asarray(floor).copy()
        pixels = original.copy()
        base = BASES[style]
        continuous = np.tile(np.asarray(native.tiles[base]), (height, width, 1))
        walk_pixels = np.repeat(np.repeat(~blocked, 24, 0), 24, 1)
        pixels[walk_pixels] = continuous[walk_pixels]
        # Retain the established wall-boundary shadow, tied only to real masks.
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            edge = (~blocked) & np.roll(blocked, (-dy, -dx), (0, 1))
            for y, x in zip(*np.where(edge)):
                ys = slice(y * 24, y * 24 + 3) if dy < 0 else slice(y * 24 + 21, y * 24 + 24) if dy > 0 else slice(y * 24, y * 24 + 24)
                xs = slice(x * 24, x * 24 + 3) if dx < 0 else slice(x * 24 + 21, x * 24 + 24) if dx > 0 else slice(x * 24, x * 24 + 24)
                pixels[ys, xs, :3] = (pixels[ys, xs, :3].astype(np.uint16) * 64 // 100).astype(np.uint8)
        assert np.array_equal(pixels[~walk_pixels], original[~walk_pixels]), mid
        floor = Image.fromarray(pixels, "RGBA")
        layers, chunks = [], {}
        for cy in range(0, height, 16):
            for cx in range(0, width, 16):
                chunk = floor.crop((cx * 24, cy * 24, min(width, cx + 16) * 24, min(height, cy + 16) * 24))
                relative = "gameplay/world/r17-family-final/floor-" + digest(chunk.tobytes())[:24] + ".png"
                target = args.output / relative
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    chunk.save(target)
                layer = {"path": relative, "x": cx * 24, "y": cy * 24, "width_px": chunk.width, "height_px": chunk.height}
                layers.append(layer)
                chunks[f"{cx // 16},{cy // 16}"] = layer
        previous_bases = deepcopy(game_map["visual_style"]["walkable_native_ground_ids"])
        game_map.update(ground_layers=layers, ground_chunks=chunks)
        game_map["visual_style"].update(walkable_native_ground_ids=[base], continuous_walk_floor="single native base; no whole-cell contrast lottery")
        wall = int(game_map["visual_style"]["blocked_native_ground_id"])
        game_map["presentation_ground_ids"] = [wall if blocked[y, x] else base for y in range(height) for x in range(width)]
        overview = floor.resize((width * 2, height * 2), Image.Resampling.NEAREST)
        for obj in sorted(game_map["objects"], key=lambda obj: obj["depth_y"]):
            image = Image.open(args.output / obj["path"]).convert("RGBA")
            image = image.resize((max(1, image.width // 12), max(1, image.height // 12)), Image.Resampling.NEAREST)
            overview.alpha_composite(image, (int(obj["x"] // 12), int(obj["y"] // 12)))
        relative = "gameplay/world/r17-family-final/overview-" + digest(mid)[:20] + ".png"
        overview.convert("RGB").save(args.output / relative)
        game_map["overview_png"] = relative
        rows.append({"map_id": mid, "style": style, "previous_walkable_ground_ids": previous_bases, "continuous_native_ground_id": base, "all_blocked_pixels_exactly_preserved": True, "changed_pixel_count": int(np.any(pixels != original, axis=2).sum())})
    for mid, game_map in data["maps"].items():
        old = before["maps"][mid]
        changed = {key for key in game_map.keys() | old.keys() if game_map.get(key) != old.get(key)}
        assert changed <= PRESENTATION_KEYS, (mid, changed)
    for key in before:
        if key != "maps":
            assert data[key] == before[key], key
    report = {"schema": "baram.g2.continuous-walk-floor/1", "status": "IMPLEMENTED_ART_ONLY_NOT_VISUAL_PASS", "source_content_sha256": filehash(args.source / "gameplay_content.json"), "source_runtime_sha256": filehash(args.source / "runtime.json"), "tool_sha256": filehash(Path(__file__)), "maps": rows, "source_native_floor_members": ["NWind.dat:tilea.bmp", "NWind.dat:tileb.bmp", "NWind.dat:tilec.bmp", "NWind.dat:windland.pal"], "native_tiles": [{"id": tile, "rgba_sha256": digest(native.tiles[tile].tobytes())} for tile in sorted(BASES.values())], "all_objects_portals_masks_arrivals_save_identity_unchanged": True, "all_blocked_pixels_and_existing_outcrops_exactly_preserved": True, "actual_render_review": "NOT_RUN"}
    data["continuous_walk_floor_repair"] = {key: value for key, value in report.items() if key not in ("maps", "native_tiles")}
    write(args.output / "gameplay_content.json", data)
    write(args.output / "G2_R17_CONTINUOUS_WALK_FLOOR.json", report)
    write(args.receipt, report)
    manifest = json.loads((args.source / "runtime.json").read_text())
    files = [{"path": str(path.relative_to(args.output)), "bytes": path.stat().st_size, "sha256": filehash(path)} for path in sorted(args.output.rglob("*")) if path.is_file() and path.name != "runtime.json"]
    manifest.update(files=files, fingerprint=digest(files), input_definitions_sha256=filehash(args.output / "gameplay_content.json"), continuous_walk_floor_repair=deepcopy(data["continuous_walk_floor_repair"]))
    write(args.output / "runtime.json", manifest)
    print("CONTINUOUS_FAMILY_ART_READY", filehash(args.output / "gameplay_content.json"), filehash(args.output / "runtime.json"))


if __name__ == "__main__":
    main()
