#!/usr/bin/env python3
"""Freeze a new private priority-fill generation without changing parent inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image
from priority_effects import apply_overlay

PARENT_SHA = "ddf88ca05f63ab67c73f12f474005310eed39b31996f8d6c70b9015703922973"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def safe(root, name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("Unsafe dependency: " + name)
    target = root / p
    if not target.is_file() or target.is_symlink():
        raise ValueError("Missing/unsafe dependency: " + name)
    return target

def assemble(args):
    parent = args.parent.resolve()
    if digest(parent / "runtime.json") != PARENT_SHA:
        raise ValueError("Expected pristine GEN003 parent manifest")
    old = json.loads((parent / "runtime.json").read_text())
    for entry in old["files"]:
        if digest(safe(parent,entry["path"])) != entry["sha256"]:
            raise ValueError("Parent input hash mismatch: " + entry["path"])
    target = args.output.resolve()
    if target.exists(): raise ValueError("New empty generation path required")
    shutil.copytree(parent, target)
    shutil.rmtree(target / "maps")
    shutil.copytree(args.maps, target / "maps")
    shutil.copytree(args.icons, target / "icons")
    (target / "rules").mkdir()
    shutil.copyfile(args.rules, target / "rules/priority_rules.json")
    graph = json.loads((parent / "kr491/kr491_runtime.json").read_text())
    overlay = json.loads(args.effects.read_text())
    graph = apply_overlay(graph, overlay)
    dump(target / "kr491/kr491_runtime.json", graph)
    index = json.loads((target / "maps/index.json").read_text())
    index["load_mode"] = "LAZY_VALIDATED_INDEX"
    dump(target / "maps/index.json", index)
    # Static full dependency/range pass. No invented server dimensions or exits.
    seen = set()
    for entry in index["maps"]:
        m = json.loads(safe(target / "maps",entry["json"]).read_text())
        identity = entry["inspection_id"]
        if identity in seen: raise ValueError("Duplicate storage chunk identity")
        seen.add(identity)
        if len(m["collisions"]["ground_ids"]) != 4096 or len(m["collisions"]["edge_masks"]) != 4096:
            raise ValueError("Invalid 64x64 storage probe grid")
        safe(target / "maps", m["floor_png"])
        for obj in m["objects"]: safe(target / "maps", obj["frame_png"])
        if m["exits"]["items"] or m["return_points"]["items"]:
            raise ValueError("Unproven world exits/returns in storage inspection")
    icons = json.loads((target / "icons/icons.json").read_text())
    for entry in icons["entries"]: safe(target / "icons",entry["image_path"])
    for sound in graph["sounds"]: safe(target / "kr491",sound["path"])
    for effect in graph["effects"]:
        for frame in effect.get("front_frames",[]) + effect.get("back_frames",[]):
            if frame.get("image"):
                safe(target / "kr491", frame["image"]["path"])
    pngs = list(target.rglob("*.png"))
    for p in pngs:
        with Image.open(p) as img: img.verify()
    priority = {"schema":"baram.priority.index/1","icons":"icons/icons.json","rules":"rules/priority_rules.json",
                "rules_profile":"KR_GUIDE_2001_WORKING_PROVISIONAL","historical_default_changed":False,
                "map_scope":"Independent native 64x64 storage chunks; no world join/names/exits",
                "icon_scope":"Official document images used as reconstructed inspection thumbnails; equipped sprite unknown",
                "effect_scope":"Neutral bounded one traversal; Light/Alpha/repeat semantics not original"}
    dump(target / "priority_index.json",priority)
    files = [{"path":p.relative_to(target).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p)}
             for p in sorted(target.rglob("*")) if p.is_file() and p.name != "runtime.json"]
    sources = {"parent_runtime":PARENT_SHA,"maps":digest(args.maps/"index.json"),"icons":digest(args.icons/"icons.json"),
               "rules":digest(args.rules),"effects":digest(args.effects),"assembler":digest(Path(__file__))}
    fingerprint = hashlib.sha256(json.dumps({"files":files,"components":sources},sort_keys=True).encode()).hexdigest()
    old.update({"generation":args.generation,"parent_generation":"WORK-P2-GEN003","parent_runtime_sha256":PARENT_SHA,
                "priority_index":"priority_index.json","priority_components":sources,"fingerprint":fingerprint,"files":files})
    dump(target/"runtime.json",old)
    receipt={"status":"PASS_STATIC_DEPENDENCY_SCOPE","generation":old["generation"],"files":len(files),"pngs_decoded":len(pngs),
             "map_chunks":len(index["maps"]),"native_map_ids":len({e["native_id"] for e in index["maps"]}),
             "icon_candidates":len(icons["entries"]),"effects":len(graph["effects"]),"wav_ids":len(graph["sounds"]),
             "runtime_sha256":digest(target/"runtime.json"),"fingerprint":fingerprint,"components":sources,
             "runtime_execution":"NOT_RUN_BY_ASSEMBLER","parent_unchanged":digest(parent/"runtime.json")==PARENT_SHA}
    dump(args.receipt,receipt)
    print(json.dumps(receipt,ensure_ascii=False))

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--generation",required=True)
    for name in ("parent","maps","icons","rules","effects","output","receipt"):p.add_argument("--"+name,required=True,type=Path)
    assemble(p.parse_args())
