#!/usr/bin/env python3
"""Create a new private input generation correcting only DLGNEW02's palette.

The frozen parent is never modified. Original KR491 code, not border similarity,
establishes BARAM.PAL as the default palette for this dialog's EPF constructor.
EPF pixels/stencil decoding and all other assets remain byte-for-byte unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("parent", "output", "dat", "exe", "reader"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    parent, output = args.parent.resolve(), args.output.resolve()
    checkout = Path(__file__).resolve().parents[3]
    if output.exists() or output.is_relative_to(checkout) or parent == output:
        raise ValueError("new output must not exist and must be outside checkout")
    raw = args.dat.read_bytes()
    exe = args.exe.read_bytes()
    if sha(raw) != "f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7":
        raise ValueError("KR491 DAT pin mismatch")
    if sha(exe) != "f88846f2d3ce394d8dcc6e55288b8977ff3d34e160a4029337bdaccee84475ea":
        raise ValueError("KR491 executable pin mismatch")
    if sha(args.reader.read_bytes()) != "f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2":
        raise ValueError("parent reader pin mismatch")
    # Pin the disassembled original call, constructor default, and draw lookup.
    excerpts = {
        0x44649A: (20, "2abaa3634d768ab0b1ca39a9c70b950a706c75f32c257b4528ae62369e80bf18"),
        0x419727: (34, "d17003ce086c570f8b024516af759c997725267f37adfcb8fde357c980f970d3"),
        0x4197FD: (19, "6ee2b123c605235d854c0e8d203e341459a9e24c6881b4c175ca72b224159f4b"),
    }
    for va, (size, expected_sha256) in excerpts.items():
        if sha(exe[va - 0x400000:va - 0x400000 + size]) != expected_sha256:
            raise ValueError("original palette-binding code changed")
    if not exe[0xED29C:].startswith("DLGNEW02.EPF\0".encode("utf-16le")):
        raise ValueError("dialog resource name changed")
    if not exe[0xE7414:].startswith("BARAM.PAL\0".encode("utf-16le")):
        raise ValueError("default palette name changed")
    spec = importlib.util.spec_from_file_location("kr491_parent_reader", args.reader)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    entries = reader.dat_entries(raw)
    epf = reader.Epf(entries["dlgnew02.epf"][2])
    frame = epf.frame(0)
    old_palette = reader.read_palettes(entries["dlglogin.pal"][2])[0]
    new_palette = reader.read_palettes(entries["baram.pal"][2])[0]
    parent_bytes = (parent / "kr491_runtime.json").read_bytes()
    manifest = json.loads(parent_bytes)
    parent_ui = [x for x in manifest["ui"] if x["name"] == "DLGNEW02"]
    if len(parent_ui) != 1 or parent_ui[0]["image"]["palette_member"].lower() != "dlglogin.pal":
        raise ValueError("parent is not the known incorrect palette generation")
    if parent_ui[0]["image"]["rgba_sha256"] != sha(frame.rgba(old_palette)):
        raise ValueError("parent UI image does not match pinned original decode")
    old_file = parent / parent_ui[0]["image"]["path"]
    if sha(old_file.read_bytes()) != parent_ui[0]["image"]["sha256"]:
        raise ValueError("parent UI PNG pin mismatch")
    shutil.copytree(parent, output, copy_function=shutil.copy2)
    relative = "images/dlgnew02-00000-baram-0.png"
    data = reader.png_bytes(frame.width, frame.height, frame.rgba(new_palette))
    (output / relative).write_bytes(data)
    record = parent_ui[0]["image"]
    record.update(key="DLGNEW02:0:Baram:0", palette_member="Baram.pal", palette=0,
                  path=relative, sha256=sha(data), rgba_sha256=sha(frame.rgba(new_palette)))
    parent_ui[0]["palette_binding"] = "ORIGINAL_BINARY_STATIC_BINDING: KR491 Winbaram.exe 0x44649a -> 0x4196c0 -> BARAM.PAL default"
    name, offset, paldata = entries["baram.pal"]
    if not any(x["member"].lower() == "baram.pal" for x in manifest["source_members"]):
        manifest["source_members"].append({"member": name, "bytes": len(paldata),
            "sha256": sha(paldata), "dat_byte_offset": offset, "source_id": "LIB-010",
            "container_sha256": sha(raw)})
    diagnosis = {
        "schema": "baram.p2.kr491-ui-palette-correction/1",
        "status": "STATIC_BINDING_VERIFIED_CANDIDATE_RENDERED_RUNTIME_PENDING",
        "parent_runtime_sha256": sha(parent_bytes),
        "correction_script_sha256": sha(Path(__file__).read_bytes()),
        "original_exe_sha256": sha(exe), "original_dat_sha256": sha(raw),
        "source_sprite": "DLGNEW02.epf:0", "wrong_palette": "DlgLogin.pal:0",
        "correct_palette": "Baram.pal:0", "new_palette_sha256": sha(paldata),
        "root_cause": "incorrect inferred palette binding; not EPF compression or encryption",
        "original_static_evidence": [
            {"virtual_address": "0x44649a..0x4464ad", "meaning": "DLGNEW02 constructor passes palette argument NULL"},
            {"virtual_address": "0x419727..0x419748", "meaning": "NULL palette name defaults to BARAM.PAL string at0x4e7414"},
            {"virtual_address": "0x4197fd..0x41980f", "meaning": "draw path obtains palette from the constructor field"},
        ],
        "unchanged": ["source EPF bytes", "pixel indices", "mask alpha", "frame rectangle", "all other UI and assets"],
        "mask3_status": "BLOCKED_UNCHANGED; palette correction does not repair DLGLOGIN/DLGNEW01/DLGPASS masks",
        "historical_1998_2001_match": "UNVERIFIED", "original_ui_flow": "NOT_IMPLEMENTED",
    }
    manifest["palette_correction"] = diagnosis
    write_json(output / "UI_PALETTE_CORRECTION.json", diagnosis)
    write_json(output / "kr491_runtime.json", manifest)
    result = json.loads((output / "BUILD_RESULT.json").read_bytes())
    result.update(runtime_manifest_sha256=sha((output / "kr491_runtime.json").read_bytes()),
                  output=str(output), source_members=len(manifest["source_members"]),
                  parent_runtime_sha256=sha(parent_bytes),
                  correction="DLGNEW02 palette only; inherited base full-frame regression, no rerun claim",
                  runtime_render="NOT_RUN_GEN003")
    write_json(output / "BUILD_RESULT.json", result)
    changed = []
    for original in parent.rglob("*"):
        if original.is_file() and original.read_bytes() != (output / original.relative_to(parent)).read_bytes():
            changed.append(original.relative_to(parent).as_posix())
    if sorted(changed) != ["BUILD_RESULT.json", "kr491_runtime.json"]:
        raise ValueError("unexpected change in inherited assets")
    # Verify all copied PNG files without re-decoding all 27,886 EPF frames.
    from PIL import Image
    verified = 0
    for png in output.rglob("*.png"):
        with Image.open(png) as im:
            im.verify()
        verified += 1
    diagnosis.update(inherited_files_changed=changed, png_verified=verified,
                     parent_frozen_preserved=True,
                     corrected_png_sha256=sha(data),
                     parent_png_sha256=sha(old_file.read_bytes()))
    write_json(output / "UI_PALETTE_CORRECTION.json", diagnosis)
    print(json.dumps(diagnosis, ensure_ascii=False))


if __name__ == "__main__":
    main()
