#!/usr/bin/env python3
"""Expand native KR1.25 storage chunks for P2 inspection, without joining geography.

Reuses the established KR125 bitmap/OTB/edge decoder and the pinned private
DAT/PAL reader. Every exact chunk is independently checked. Odd trailers are
quarantined as whole source files; no bytes are trimmed. The server's active
width, world chunk topology, names, exits and return points remain unknown.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import os
import tempfile
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zipfile
from PIL import Image

import kr125_map as base

READER_SHA256 = "f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2"
SCHEMA = "kr125-priority-storage-inspection-v1"


def atomic_bytes(path: Path, data: bytes):
    """Do not let Pillow's direct file encoder produce a partial published PNG."""
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            count = stream.write(data)
            if count != len(data):
                raise OSError(f"Short file write: {path.name} {count}/{len(data)}")
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise OSError(f"Post-fsync bytes mismatch: {path.name}")
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if path.read_bytes() != data:
            raise OSError(f"Post-replace bytes mismatch: {path.name}")
    finally:
        if temporary.exists():
            temporary.unlink()


def write(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def save_png(image: Image.Image, path: Path):
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    data = encoded.getvalue()
    with Image.open(BytesIO(data)) as check:
        check.verify()
    with Image.open(BytesIO(data)) as check:
        check.load()
        if check.mode != image.mode or check.size != image.size or check.tobytes() != image.tobytes():
            raise ValueError(f"Memory PNG pixel mismatch: {path.name}")
    atomic_bytes(path, data)
    with Image.open(path) as check:
        check.verify()
    with Image.open(path) as check:
        check.load()
        if check.size != image.size:
            raise ValueError(f"Published PNG dimensions mismatch: {path.name}")


def scan(data: bytes, counts: dict, object_count: int) -> dict:
    """Validate the whole source; never salvage prefixes of malformed files."""
    whole, trailer = divmod(len(data), base.CHUNK_BYTES)
    result = {"storage_chunk_count": whole, "trailer_bytes": trailer,
              "active_dimensions": None, "chunk_topology": None, "failures": []}
    if trailer or not whole:
        result.update(status="BLOCKED_NONEXACT_STORAGE", runtime_status="ACQUIRED",
                      cause="DECODE_FAILED", reason=f"{len(data)} bytes; {whole} full chunk(s) plus {trailer} trailing byte(s); whole source quarantined")
        return result
    for chunk in range(whole):
        part = data[chunk * base.CHUNK_BYTES:(chunk + 1) * base.CHUNK_BYTES]
        try:
            base.decode_map(part, counts, object_count)
        except ValueError as exc:
            # Enumerate all unsafe references, not just the decoder's first one.
            words = struct.unpack(f"<{64*64*2}H", part)
            for cell, (ground, obj) in enumerate(zip(words[0::2], words[1::2])):
                try:
                    base.ground_tile(ground, counts)
                except ValueError as detail:
                    result["failures"].append({"chunk": chunk, "cell": cell,
                        "byte_offset": chunk * base.CHUNK_BYTES + cell * 4,
                        "field": "ground", "value": ground, "reason": str(detail)})
                if not 0 <= obj < object_count:
                    result["failures"].append({"chunk": chunk, "cell": cell,
                        "byte_offset": chunk * base.CHUNK_BYTES + cell * 4 + 2,
                        "field": "object", "value": obj, "reason": "outside native OTB bounds"})
    if result["failures"]:
        result.update(status="BLOCKED_REFERENCE", runtime_status="ACQUIRED",
                      cause="DECODE_FAILED", reason="Native tile/object references cannot resolve; no replacement objects or frame0 used")
    else:
        result.update(status="STORAGE_REFERENCES_VALID", runtime_status="DECODED", cause=None,
                      reason="Independent storage chunks, not active map geometry")
    return result


def negative_checks(counts, object_count, valid_data):
    checks = []
    def check(name, good, detail):
        checks.append({"id": name, "status": "PASS" if good else "FAIL", "details": detail})
    for name, data, expected in [
        ("truncated_chunk_rejected", valid_data[:-1], "BLOCKED_NONEXACT_STORAGE"),
        ("extra_byte_not_trimmed", valid_data+b"\0", "BLOCKED_NONEXACT_STORAGE"),
        ("partial_multi_chunk_not_salvaged", valid_data+valid_data[:-1], "BLOCKED_NONEXACT_STORAGE"),
        ("empty_source_rejected", b"", "BLOCKED_NONEXACT_STORAGE")]:
        result = scan(data, counts, object_count)
        check(name, result["status"] == expected, result["status"])
    mutated = bytearray(valid_data)
    struct.pack_into("<H", mutated, 2, object_count)
    result = scan(mutated, counts, object_count)
    check("unknown_object_rejected", result["status"] == "BLOCKED_REFERENCE" and result["failures"][0]["field"] == "object", result["failures"][:1])
    mutated = bytearray(valid_data)
    struct.pack_into("<H", mutated, 0, 65535)
    result = scan(mutated, counts, object_count)
    check("unknown_ground_rejected", result["status"] == "BLOCKED_REFERENCE" and result["failures"][0]["field"] == "ground", result["failures"][:1])
    result = scan(valid_data+valid_data, counts, object_count)
    check("exact_multi_chunk_retains_unknown_geometry", result["status"] == "STORAGE_REFERENCES_VALID" and result["chunk_topology"] is None and result["active_dimensions"] is None, result)
    return checks


def build(client_zip: Path, reader_path: Path, output: Path, audit_path: Path | None = None,
          baseline_maps: Path | None = None):
    output = output.resolve()
    repo = Path(__file__).resolve().parents[3]
    if output == repo or repo in output.parents:
        raise ValueError("Decoded originals must stay outside public checkout")
    if output.exists():
        raise ValueError("Output generation already exists; choose a fresh path")
    client = client_zip.read_bytes()
    if base.sha(client) != base.CLIENT_SHA256:
        raise ValueError("Original KR125 ZIP hash mismatch")
    if base.sha(reader_path.read_bytes()) != READER_SHA256:
        raise ValueError("Pinned legacy reader hash mismatch")
    spec = importlib.util.spec_from_file_location("priority_legacy_assets", reader_path)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    with zipfile.ZipFile(client_zip) as archive:
        entries = reader.dat_entries(archive.read("winbaram.dat"))
        exe = archive.read("winbaram.exe")
        static_evidence = base.original_exe_evidence(exe)
        source_names = ["tilea.bmp", "tileb.bmp", "tilec.bmp", "windland.pal", "sobject.otb", "sotp.dat"]
        raw = {name: entries[name][2] for name in source_names}
        palettes = reader.read_palettes(raw["windland.pal"])
        if len(palettes) != 1:
            raise ValueError("Expected one KR125 palette")
        colors = palettes[0].colors
        if any(len(raw[f"tile{g.lower()}.bmp"]) % 576 for g in "ABC"):
            raise ValueError("Native tile bitmap is incomplete")
        counts = {g:len(raw[f"tile{g.lower()}.bmp"]) // 576 for g in "ABC"}
        objects = base.decode_otb(raw["sobject.otb"], counts["C"])
        if len(raw["sotp.dat"]) != len(objects):
            raise ValueError("SOTP/OTB count mismatch")
        masks = [0] + list(raw["sotp.dat"])
        names = sorted((n for n in archive.namelist() if n.lower().endswith(".map")), key=lambda n:int(Path(n).stem))
        inventory = []
        for name in names:
            data = archive.read(name)
            row = {"native_id": int(Path(name).stem), "member": name,
                "source_id": "LIB-009", "source_tier": 1, "fact_status": "ORIGINAL_VERIFIED",
                "fact_scope": "KR1.25 native storage bytes only; target-era map identity unknown",
                "size_bytes": len(data), "sha256": base.sha(data), **scan(data, counts, len(objects))}
            inventory.append(row)
        checks = negative_checks(counts, len(objects), archive.read("1.map"))
        output.mkdir(parents=True)
        (output/"objects").mkdir()
        tiles = {}
        rendered_objects = set()
        def tile(g, index, transparent):
            key = (g, index, transparent)
            if key not in tiles:
                data = raw[f"tile{g.lower()}.bmp"][index*576:(index+1)*576]
                rgba = bytes(c for idx in data for c in (*colors[idx], 0 if transparent and idx == 0 else 255))
                tiles[key] = Image.frombytes("RGBA", (24,24), rgba)
            return tiles[key]
        produced = []
        for row in inventory:
            if row["status"] != "STORAGE_REFERENCES_VALID":
                continue
            data = archive.read(row["member"])
            for chunk in range(row["storage_chunk_count"]):
                part = data[chunk*base.CHUNK_BYTES:(chunk+1)*base.CHUNK_BYTES]
                ground, obj_ids = base.decode_map(part, counts, len(objects))
                stem = f'map-{row["native_id"]}' + (f'-chunk-{chunk:02d}' if row["storage_chunk_count"] > 1 else "")
                inspection_id = f'kr125:map-{row["native_id"]}:chunk-{chunk}'
                floor = Image.new("RGBA", (1536,1536), (0,0,0,255))
                placements, ground_deps, object_deps, occupied = [], set(), set(), []
                nonvisual = []
                edge_masks = [masks[obj] for obj in obj_ids]
                for cell, (word,obj) in enumerate(zip(ground,obj_ids)):
                    x,y = cell%64,cell//64
                    frame = base.ground_tile(word, counts)
                    if frame:
                        floor.alpha_composite(tile(*frame, False),(x*24,y*24))
                        ground_deps.add(frame)
                        occupied.append((x,y))
                    if not obj:
                        continue
                    stack = objects[obj]
                    object_deps.add(obj)
                    if not stack:
                        # An authenticated height0 record is a native no-draw
                        # instruction, not a missing image. Preserve identity,
                        # coordinates and native collision without any placeholder.
                        nonvisual.append({"native_id":obj,"grid_x":x,"grid_y":y,
                            "height":0,"edge_mask":masks[obj],"render":"NATIVE_ZERO_HEIGHT_NO_DRAW"})
                        continue
                    object_path = f"objects/object-{obj}.png"
                    if obj not in rendered_objects:
                        image = Image.new("RGBA", (24,24*len(stack)),(0,0,0,0))
                        for height, tw in enumerate(stack):
                            if tw:
                                image.alpha_composite(tile("C",tw-1,True),(0,(len(stack)-1-height)*24))
                        save_png(image, output/object_path)
                        rendered_objects.add(obj)
                    placements.append({"native_id": obj, "frame_png": object_path,"x":x*24,"y":(y-len(stack)+1)*24,
                        "anchor_x":0,"anchor_y":(len(stack)-1)*24,"grid_x":x,"grid_y":y,"depth_y":y*24+24,
                        "layer":"depth","height":len(stack),"native_tile_words_bottom_to_top":list(stack),"edge_mask":masks[obj]})
                floor_name = stem+"-floor.png"
                save_png(floor, output/floor_name)
                bounds = [min(x for x,y in occupied),min(y for x,y in occupied),max(x for x,y in occupied),max(y for x,y in occupied)] if occupied else None
                record = {"schema":base.SCHEMA,"native_id":row["native_id"],"inspection_id":inspection_id,
                    "storage_chunk_index":chunk,"source_storage_chunks":row["storage_chunk_count"],
                    "source_chunk_byte_offset":chunk*base.CHUNK_BYTES,"source_chunk_bytes":base.CHUNK_BYTES,
                    "source_chunk_sha256":base.sha(part),"source_map_path":f'LIB-009!{row["member"]}',"source_map_sha256":row["sha256"],
                    "grid_width":64,"grid_height":64,"grid_scope":"isolated exact native storage chunk; chunk topology and active server dimensions UNKNOWN",
                    "active_grid_width":None,"active_grid_height":None,"storage_chunk_world_position":None,
                    "tile_width":24,"tile_height":24,"projection":"orthogonal","pixel_offset":[0,0],"floor_png":floor_name,
                    "objects":placements,"nonvisual_native_objects":nonvisual,"occupied_ground_bounds":bounds,
                    "collisions":{"status":"STATIC_EXE_DERIVED","ground_ids":ground,"edge_masks":edge_masks,
                        "blocked_cells":[[i%64,i//64] for i,w in enumerate(ground) if 1024<=w<2048 or edge_masks[i]==15],
                        "ground_block_rule":"1024 <= target_ground_word < 2048",
                        "direction_bits":{d:{"dx":v[0],"dy":v[1],"source_edge_bit":v[2],"target_edge_bit":v[3]} for d,v in base.DIRS.items()},
                        "boundary":"inspection storage chunk only; no cross-chunk movement claimed","original_client_execution":"NOT_RUN"},
                    "exits":{"status":"UNKNOWN","items":[]},"return_points":{"status":"UNKNOWN","items":[]},
                    "city_name":None,"historical_match":"UNVERIFIED_KR125_NOT_TARGET_PROFILE",
                    "dependencies":{"ground_frames":[f"KR125/{g}:{i}" for g,i in sorted(ground_deps)],"object_ids":sorted(object_deps),"palette":"KR125/WINDLAND.PAL:0"}}
                json_name = stem+".json"
                write(output/json_name,record)
                # Static compositions are actual images, not runtime or geography PASS.
                composite = floor.copy()
                for obj in sorted(placements,key=lambda p:(p["depth_y"],p["grid_x"])):
                    with Image.open(output/obj["frame_png"]) as image:
                        composite.alpha_composite(image,(obj["x"],obj["y"]))
                save_png(composite, output/(stem+"-composite.png"))
                outcomes, examples = Counter(), {}
                for y in range(64):
                    for x in range(64):
                        for direction in base.DIRS:
                            status = "allowed" if base.can_step(ground,edge_masks,x,y,direction) else "blocked"
                            outcomes[status] += 1
                            examples.setdefault(status,{"x":x,"y":y,"direction":direction})
                produced.append({"native_id":row["native_id"],"inspection_id":inspection_id,"storage_chunk_index":chunk,
                    "source_storage_chunks":row["storage_chunk_count"],"json":json_name,"floor_png":floor_name,
                    "composite_png":stem+"-composite.png","object_placements":len(placements),"native_zero_height_placements":len(nonvisual),
                    "occupied_ground_bounds":bounds,"static_move_outcomes":dict(outcomes),"static_move_examples":examples,
                    "runtime_status":"BOUND_READY_NOT_EXERCISED"})
        generation_checks = []
        png_files = sorted(output.rglob("*.png"))
        for file in png_files:
            with Image.open(file) as image:
                image.verify()
            with Image.open(file) as image:
                image.load()
        generation_checks.append({"id":"full_png_verify_and_decode_after_atomic_writes","status":"PASS",
            "details":{"png_files_checked":len(png_files),"corrupt":0,"scope":"Pillow PNG.verify then reopened full pixel decode; independent from file hashes"}})
        if baseline_maps:
            baseline_index = json.loads((baseline_maps/"index.json").read_text())
            baseline_hash = base.sha((baseline_maps/"index.json").read_bytes())
            for old in baseline_index["maps"]:
                item = next((r for r in produced if r["native_id"]==old["native_id"] and r["storage_chunk_index"]==0),None)
                if item is None:
                    raise ValueError(f"Baseline map{old['native_id']} missing")
                old_record = json.loads((baseline_maps/old["json"]).read_text())
                new_record = json.loads((output/item["json"]).read_text())
                same = old_record["objects"]==new_record["objects"] and old_record["collisions"]["ground_ids"]==new_record["collisions"]["ground_ids"] and old_record["collisions"]["edge_masks"]==new_record["collisions"]["edge_masks"]
                same = same and base.sha((baseline_maps/old["floor_png"]).read_bytes())==base.sha((output/item["floor_png"]).read_bytes())
                same = same and base.sha((baseline_maps/old["composite_png"]).read_bytes())==base.sha((output/item["composite_png"]).read_bytes())
                generation_checks.append({"id":f"baseline_map_{old['native_id']}_byte_and_geometry_match","status":"PASS" if same else "FAIL","details":{"baseline_index_sha256":baseline_hash,"scope":"floor/composite PNG bytes, placements, ground IDs and collision edge masks"}})
        for row in inventory:
            if row["native_id"] in [3,4]:
                good = row["status"] == ("BLOCKED_REFERENCE" if row["native_id"]==4 else "BLOCKED_NONEXACT_STORAGE")
                generation_checks.append({"id":f"original_map_{row['native_id']}_unsafe_preserved","status":"PASS" if good else "FAIL","details":row["status"]})
        generation_checks.append({"id":"no_guessed_native_geography","status":"PASS" if all(json.loads((output/r["json"]).read_text())["storage_chunk_world_position"] is None for r in produced) else "FAIL","details":{"chunks":len(produced)}})
        source_usage = [{"source_id":f"LIB-009!winbaram.dat!{entries[n][0]}","dat_offset":entries[n][1],"size_bytes":len(raw[n]),"sha256":base.sha(raw[n])} for n in source_names]
        summary = {"source_map_files":len(inventory),"single_chunk_sources_valid":sum(r["status"]=="STORAGE_REFERENCES_VALID" and r["storage_chunk_count"]==1 for r in inventory),
            "multi_chunk_sources_valid":sum(r["status"]=="STORAGE_REFERENCES_VALID" and r["storage_chunk_count"]>1 for r in inventory),
            "source_files_reference_valid":sum(r["status"]=="STORAGE_REFERENCES_VALID" for r in inventory),
            "storage_chunks_bound_ready":len(produced),"blocked_source_files":sum(r["status"]!="STORAGE_REFERENCES_VALID" for r in inventory),
            "blocked_by_status":dict(Counter(r["status"] for r in inventory if r["status"]!="STORAGE_REFERENCES_VALID")),
            "object_images":len(rendered_objects),"object_placements":sum(r["object_placements"] for r in produced),
            "native_zero_height_placements":sum(r["native_zero_height_placements"] for r in produced),
            "active_geography_verified":0,"runtime_exercised":0,"negative_checks_pass":sum(c["status"]=="PASS" for c in checks),"negative_checks_fail":sum(c["status"]=="FAIL" for c in checks),
            "generation_checks_pass":sum(c["status"]=="PASS" for c in generation_checks),"generation_checks_fail":sum(c["status"]=="FAIL" for c in generation_checks)}
        index = {"schema":SCHEMA,"source_zip_sha256":base.sha(client),"source_zip_bytes":len(client),"source_id":"LIB-009",
            "source_exe_sha256":base.sha(exe),"sources":source_usage,"parser_sha256":READER_SHA256,
            "converter_sha256":base.sha(Path(__file__).read_bytes()),"base_converter_sha256":base.sha(Path(base.__file__).read_bytes()),
            "maps":produced,"objects_total_declared":len(objects),"tile_counts":counts,"map_inventory":inventory,
            "independent_static_executable_evidence":static_evidence,"summary":summary,"negative_tests":checks,"generation_checks":generation_checks,
            "limitations":["Storage chunks are independent; no world shape/width inferred, including MAP0's49 or MAP208's5 chunks.",
                "19 nonexact source files and map4 remain quarantined as whole files; prefixes are never trimmed into success.",
                "KR1.25 source storage facts do not establish 1998-2001 city identity, exits, return points, spawns, occlusion or original runtime behavior.",
                "Static composition and movement predicate enumeration are not Godot/Windows/Android gameplay PASS."]}
        write(output/"index.json",index)
        artifact_rows = [{"path":p.relative_to(output).as_posix(),"size_bytes":p.stat().st_size,"sha256":base.sha(p.read_bytes())} for p in sorted(output.rglob("*")) if p.is_file()]
        write(output/"ARTIFACTS.json",artifact_rows)
        audit = {k:v for k,v in index.items() if k not in {"maps","independent_static_executable_evidence"}}
        audit["runtime_binding_index"]=f"private {output.name}/index.json"
        audit["originals_preserved"]=True
        audit["status"]="PARTIAL_STORAGE_CONSUMPTION_EXPANDED"
        if audit_path:
            audit_path.parent.mkdir(parents=True,exist_ok=True)
            write(audit_path,audit)
        return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-zip",required=True,type=Path)
    parser.add_argument("--reader",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--audit",type=Path)
    parser.add_argument("--baseline-maps",type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(build(args.client_zip,args.reader,args.output,args.audit,args.baseline_maps),ensure_ascii=False))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"PRIORITY_MAPS_BLOCKED: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
