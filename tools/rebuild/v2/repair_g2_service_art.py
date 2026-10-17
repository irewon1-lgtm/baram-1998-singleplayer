#!/usr/bin/env python3
"""Repair two misplaced forge fragments and eight overpowering guild floors.

Uses the retained native compact storage barrel and previously accepted native
wood parquet. Collision, entrances, coordinates, gameplay data and save identity
remain exact. Actual subsequent screen review is required, never inferred here.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from PIL import Image

from repair_g2_world import digest, filehash, write


def merge_floor(directory, game_map):
    image = Image.new("RGBA", (game_map["width"] * 24, game_map["height"] * 24))
    for layer in game_map["ground_layers"]:
        image.alpha_composite(Image.open(directory / layer["path"]).convert("RGBA"), (layer["x"], layer["y"]))
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "output", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing existing generation")
    shutil.copytree(args.source, args.output)
    before = json.loads((args.source / "gameplay_content.json").read_text())
    data = deepcopy(before)
    floor_rows, prop_rows = [], []
    warm = {mid: merge_floor(args.source, before["maps"][mid]) for mid in ("gp:map:tavern", "g1:map:buya_tavern")}
    dirty = set()
    for mid, game_map in data["maps"].items():
        if game_map["width"] > 20:
            continue
        if "길드" in game_map["name"]:
            source_mid = "g1:map:buya_tavern" if mid.startswith("g1:") else "gp:map:tavern"
            floor = merge_floor(args.source, game_map)
            width, height = floor.size
            # Preserve the existing perimeter and both doorway artwork facts.
            # Only verified native parquet inside the room is reused; the old
            # source floor's bottom black notch is not imported into other maps.
            box = (24, 24, width - 24, height - 24)
            floor.paste(warm[source_mid].crop(box), box[:2])
            relative = "gameplay/world/service-art/floor-" + digest(floor.tobytes())[:24] + ".png"
            target = args.output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            floor.save(target)
            layers, chunks = [], {}
            for cy in range(0, height, 384):
                for cx in range(0, width, 384):
                    image = floor.crop((cx, cy, min(width, cx + 384), min(height, cy + 384)))
                    path = "gameplay/world/service-art/chunk-" + digest(image.tobytes())[:24] + ".png"
                    image.save(args.output / path)
                    layer = {"path": path, "x": cx, "y": cy, "width_px": image.width, "height_px": image.height}
                    layers.append(layer)
                    chunks[f"{cx // 384},{cy // 384}"] = layer
            game_map.update(floor_png=relative, ground_layers=layers, ground_chunks=chunks)
            game_map.setdefault("visual_style", {})["native_parquet_reuse"] = {"source_map": source_mid, "source_floor_sha256": digest(warm[source_mid].tobytes()), "scope": "room interior pixels only; original perimeter unchanged", "historical_room_assignment": "RECONSTRUCTED_REFERENCE_READABILITY"}
            floor_rows.append({"map_id": mid, "name": game_map["name"], "source_map": source_mid, "previous_floor": before["maps"][mid]["floor_png"], "floor": relative, "floor_sha256": filehash(target), "collision_unchanged": True})
            dirty.add(mid)
        if "대장간" in game_map["name"]:
            count = 0
            for obj in game_map["objects"]:
                if obj["path"].endswith("/object-508.png") and obj.get("source_unit") == "interior native prop":
                    old = deepcopy(obj)
                    path = "gameplay/world/g2-native/objects/object-571.png"
                    image = Image.open(args.source / path)
                    obj.update(path=path, width_px=image.width, height_px=image.height, y=obj["depth_y"] - image.height, source_unit="complete native forge storage barrel")
                    assert obj["depth_y"] == old["depth_y"] and obj["x"] == old["x"]
                    prop_rows.append({"map_id": mid, "previous_object": old, "object": deepcopy(obj), "native_source_sha256": filehash(args.source / path), "same_solid_foot_cell": [obj["x"] // 24, obj["depth_y"] // 24 - 1], "collision_unchanged": True})
                    count += 1
            assert count == 1, (mid, count)
            geometry_path = args.output / game_map["geometry_file"]
            geometry = json.loads(geometry_path.read_text())
            geometry["objects"] = deepcopy(game_map["objects"])
            write(geometry_path, geometry)
            dirty.add(mid)
    assert len(floor_rows) == 8 and len(prop_rows) == 2
    for mid in dirty:
        game_map = data["maps"][mid]
        buckets = {}
        for number, obj in enumerate(game_map["objects"]):
            for by in range(max(0, int(obj["y"] // 384)), min((game_map["height"] - 1) // 16, int((obj["y"] + obj["height_px"] - 1) // 384)) + 1):
                for bx in range(max(0, int(obj["x"] // 384)), min((game_map["width"] - 1) // 16, int((obj["x"] + obj["width_px"] - 1) // 384)) + 1):
                    buckets.setdefault(f"{bx},{by}", []).append(number)
        game_map["object_buckets"] = buckets
        overview = merge_floor(args.output, game_map).resize((game_map["width"] * 2, game_map["height"] * 2), Image.Resampling.NEAREST)
        for obj in sorted(game_map["objects"], key=lambda obj: obj["depth_y"]):
            image = Image.open(args.output / obj["path"]).convert("RGBA")
            image = image.resize((max(1, image.width // 12), max(1, image.height // 12)), Image.Resampling.NEAREST)
            overview.alpha_composite(image, (int(obj["x"] // 12), int(obj["y"] // 12)))
        path = "gameplay/world/service-art/overview-" + digest(mid)[:20] + ".png"
        overview.convert("RGB").save(args.output / path)
        game_map["overview_png"] = path
    allowed = {"floor_png", "ground_layers", "ground_chunks", "visual_style", "objects", "object_buckets", "overview_png"}
    for mid, game_map in data["maps"].items():
        old = before["maps"][mid]
        assert {key for key in game_map.keys() | old.keys() if game_map.get(key) != old.get(key)} <= allowed
        for key in ("width", "height", "blocked_base64", "edge_masks_base64", "exits", "door_contracts", "geometry_sha256", "spawns", "gather_nodes"):
            assert game_map.get(key) == old.get(key), (mid, key)
    for mid in data["g2_world"]["city_maps"]:
        assert data["maps"][mid] == before["maps"][mid], mid
    for key in before:
        if key != "maps":
            assert data[key] == before[key], key
    report = {"schema": "baram.g2.service-art/1", "status": "IMPLEMENTED_ART_ONLY_NOT_VISUAL_PASS", "tool_sha256": filehash(Path(__file__)), "source_content_sha256": filehash(args.source / "gameplay_content.json"), "source_runtime_sha256": filehash(args.source / "runtime.json"), "guild_floors": floor_rows, "forge_props": prop_rows, "all_masks_doors_arrivals_gameplay_save_identity_unchanged": True, "entire_city_map_dictionaries_and_assets_unchanged": True, "actual_render_review": "NOT_RUN"}
    data["service_art_repair"] = {key: value for key, value in report.items() if key not in ("guild_floors", "forge_props")}
    write(args.output / "gameplay_content.json", data)
    write(args.output / "G2_R17_SERVICE_ART_REPAIR.json", report)
    write(args.receipt, report)
    manifest = json.loads((args.source / "runtime.json").read_text())
    files = [{"path": str(path.relative_to(args.output)), "bytes": path.stat().st_size, "sha256": filehash(path)} for path in sorted(args.output.rglob("*")) if path.is_file() and path.name != "runtime.json"]
    manifest.update(files=files, fingerprint=digest(files), input_definitions_sha256=filehash(args.output / "gameplay_content.json"), service_art_repair=deepcopy(data["service_art_repair"]))
    write(args.output / "runtime.json", manifest)
    print("SERVICE_ART_READY", filehash(args.output / "gameplay_content.json"), filehash(args.output / "runtime.json"))


if __name__ == "__main__":
    main()
