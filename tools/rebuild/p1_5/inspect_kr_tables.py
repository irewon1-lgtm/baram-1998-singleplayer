#!/usr/bin/env python3
"""Static KR491 tables -> provenance-preserving P2 technical input (never a game).

Requires the already reviewed, fixed-hash legacy_assets.py; no fetched tool executes.
Output is normalized fields/metadata. Original DAT/SND, images and audio stay private.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import sys
import wave

EXPECTED = {
    "NWind.dat": "f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7",
    "NWind.snd": "003534e57b426971900f7ec39f5e65d3662fa5f32672cd0564d04680e31e300c",
    "legacy_assets.py": "f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected):
    data = Path(path).read_bytes()
    if sha(data) != expected:
        raise ValueError(f"input hash mismatch: {Path(path).name}")
    return data


def load_reader(path):
    checked(path, EXPECTED["legacy_assets.py"])
    spec = importlib.util.spec_from_file_location("kr491_fixed_asset_reader", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def text_lines(data):
    """Strict CP949. Original bytes and offsets remain authoritative."""
    offset = 0
    for number, raw in enumerate(data.splitlines(keepends=True), 1):
        yield number, offset, raw.decode("cp949").rstrip("\r\n"), len(raw)
        offset += len(raw)


def fields(text):
    out = {}
    for term in text.split(","):
        m = re.fullmatch(r"\s*([A-Za-z#]+)\s+(-?\d+(?:\.\d+)?)\s*", term)
        if not m:
            raise ValueError("unsupported table field: " + term[:70])
        name, value = m.groups()
        out[name] = float(value) if "." in value else int(value)
    return out


def parse_counted(data):
    rows = list(text_lines(data))
    m = re.fullmatch(r"Num[A-Za-z]+\s+(\d+)", rows[0][2])
    if not m:
        raise ValueError("missing counted-table header")
    result = [(n, o, fields(t)) for n, o, t, _ in rows[1:] if t.strip()]
    if len(result) != int(m[1]):
        raise ValueError("declared row count mismatch")
    ids = [r[2]["ID"] for r in result]
    if ids != list(range(len(ids))):
        raise ValueError("IDs not unique contiguous in counted table")
    return result


def parse_effects(data):
    result = []
    declared = None
    current = None
    for n, o, t, _ in text_lines(data):
        if not t.strip():
            continue
        if t.startswith("NumEffects "):
            declared = int(t.split()[1])
        elif t.startswith("ID "):
            current = {"line": n, "offset": o, "fields": fields(t), "frames": []}
            result.append(current)
        elif t.startswith("Frame# ") and current is not None:
            current["frames"].append({"line": n, "offset": o, "fields": fields(t)})
        else:
            raise ValueError(f"unknown effect syntax at line {n}")
    if declared is None or len(result) != declared:
        raise ValueError("effect declared count mismatch")
    if [x["fields"]["ID"] for x in result] != list(range(declared)):
        raise ValueError("effect IDs not unique contiguous")
    for x in result:
        f = x["fields"]
        if len(x["frames"]) != f["NumFrontFrames"] + f["NumBackFrames"]:
            raise ValueError("effect frame count mismatch")
        for side in ["Front", "Back"]:
            low, high = f["Repeat" + side + "From"], f["Repeat" + side + "To"]
            # Four actual rows use From=-1, To=0. Preserve this mixed sentinel;
            # rejecting it as malformed would impose an unproved runtime rule.
            if low < -1 or high < -1:
                raise ValueError("unsupported effect repeat sentinel")
            if low >= 0 and not low <= high < f["Num" + side + "Frames"]:
                raise ValueError("effect repeat range outside sequence")
    return result


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")


def run(args):
    reader = load_reader(args.reader)
    root = Path(args.repo).resolve()
    out = root / "docs/rebuild/p1_5/selected_content"
    out.mkdir(parents=True, exist_ok=True)
    original = checked(args.dat, EXPECTED["NWind.dat"])
    entries = reader.dat_entries(original)
    snd_data = checked(args.snd, EXPECTED["NWind.snd"])
    sounds = reader.dat_entries(snd_data)
    script_fingerprint = sha(Path(__file__).read_bytes())
    metadata = {}

    def source(name, line=None, offset=None):
        actual, start, data = entries[name.casefold()]
        return {"source_id": "LIB-010", "source_family": "KR491_CLIENT", "source_type": "original_client_resource", "container_sha256": EXPECTED["NWind.dat"], "member": actual, "member_sha256": sha(data), "member_byte_offset": start, "line": line, "line_byte_offset": offset, "dat_byte_offset": start + offset if offset is not None else start, "parser_sha256": script_fingerprint, "reader_sha256": EXPECTED["legacy_assets.py"]}

    def base(kind, idx, name, n=None, o=None):
        return {"id": f"KR491:{kind}:{idx}", "kind": kind, "source": source(name, n, o), "region": "KR", "version": "4.91", "target_era_match": "UNKNOWN", "fact_status": "ORIGINAL_VERIFIED", "fact_scope": "raw field decoded from fixed source bytes; not historical KR1998-2001 eligibility", "utilization_status": "DECODED", "selected_for_build": False, "selected_for_p2_technical_input": True, "reconstructed_value": None, "runtime_binding": "NOT_STARTED", "test_result": "NOT_RUN"}

    # All fixed asset count tables, including zero-body weapon tables.
    parts = []
    for stem in ["Body", "Head", "Sword", "Bow", "Fan", "Spear", "Shield", "Monster", "Item"]:
        name = stem + ".tbl"
        rows = parse_counted(entries[name.casefold()][2])
        epf = reader.Epf(entries[(stem + ".epf").casefold()][2]) if (stem + ".epf").casefold() in entries else None
        pals = reader.read_palettes(entries[(stem + ".pal").casefold()][2]) if (stem + ".pal").casefold() in entries else None
        for n, o, values in rows:
            row = base(stem.casefold(), values["ID"], name, n, o)
            row.update(original_value=values, epf_member=stem + ".epf" if epf else None, palette_member=stem + ".pal" if pals else None, consumer="P2 character/equipment/NPC/monster/icon source decoder; name/entity bindings remain separate", required_implementation=["preserve member-specific origin/offset", "strict palette bounds", "version-qualified IDs"], unknown_fields=["Korean entity/name association", "historical eligibility", "action and directional index binding"])
            if "Starting" in values and epf and not 0 <= values["Starting"] < epf.count:
                raise ValueError("part starting frame outside EPF")
            if "Palette" in values and pals and not 0 <= values["Palette"] < len(pals):
                raise ValueError("part palette outside PAL")
            parts.append(row)
        metadata[stem] = {"rows": len(rows), "epf_frames": epf.count if epf else None, "palettes": len(pals) if pals else None}
    write_jsonl(out / "kr_asset_parts.jsonl", parts)

    # Older compatibility group is not a rule for absent 225..326 IDs.
    mons = []
    for n, o, t, _ in text_lines(entries["monsfrm.tbl"][2]):
        t = t.split(";", 1)[0].strip()
        if not t:
            continue
        left, right = t.split("=")
        walk, attack = map(int, right.split())
        for idx in map(int, left.split()):
            row = base("monster_frame_group", idx, "MonsFrm.tbl", n, o)
            row["original_value"] = {"walking": walk, "attacking": attack}
            row["consumer"] = "P2 compare legacy group with Monster.tbl, without inventing absent groups"
            mons.append(row)
    if len({x["id"] for x in mons}) != len(mons):
        raise ValueError("duplicate MonsFrm member")
    write_jsonl(out / "kr_asset_monster_groups.jsonl", mons)

    draw = []
    draw_raw = entries["drworder.tbl"][2]
    offset = 0
    for i, token in enumerate(draw_raw.decode("ascii").strip().split(";")):
        if not token:
            continue
        if not re.fullmatch("[wbhs0]{4}", token):
            raise ValueError("unsupported draw-order token")
        row = base("draw_order", i, "DrwOrder.tbl", 1, offset)
        row.update(original_value={"order_token": token}, token_semantics="UNIDENTIFIED", consumer="P2 legacy part compositor; tokens and applicability must be observed", required_implementation=["do not force modern DSC layer semantics", "preserve absent part marker 0"])
        draw.append(row)
        offset += len(token) + 1
    write_jsonl(out / "kr_asset_draw_order.jsonl", draw)

    # FRM is uint32 count followed by exactly that many uint32 palette indices.
    frm = entries["effect.frm"][2]
    count, = struct.unpack_from("<I", frm)
    if len(frm) != 4 + 4 * count:
        raise ValueError("FRM length mismatch")
    frm_indices = list(struct.unpack_from("<" + "I" * count, frm, 4))
    effect_epf = reader.Epf(entries["effect.epf"][2])
    effect_pal = reader.read_palettes(entries["effect.pal"][2])
    if effect_epf.count != count or any(x >= len(effect_pal) for x in frm_indices):
        raise ValueError("effect FRM/EPF/PAL reference mismatch")
    frm_rows = []
    for i, palette in enumerate(frm_indices):
        row = base("effect_frame_palette", i, "Effect.frm", None, 4 + 4 * i)
        row.update(original_value={"frame_index": i, "palette_index": palette}, consumer="P2 effect source decoder", independent_source_comparison="TKViewer FrmFileHandler + EffectRenderer and EPFViewer FrmFileHandler consume same uint32 layout; related-source family, not independent historic evidence")
        frm_rows.append(row)
    write_jsonl(out / "kr_asset_effect_frame_palettes.jsonl", frm_rows)

    effects = []
    all_effect_frames = []
    for rec in parse_effects(entries["effect.tbl"][2]):
        v = rec["fields"]
        row = base("effect_sequence", v["ID"], "Effect.tbl", rec["line"], rec["offset"])
        row.update(original_value=v, front_frames=[], back_frames=[], delay_unit="UNKNOWN", alpha_interpretation="UNKNOWN", light_interpretation="UNKNOWN", spell_id=None, sound_id=None, hit_event_offset=None, next_action_time=None, consumer="P2 original effect source preview then independently authorized timing observations", required_implementation=["independent front/back sequences", "repeat intervals", "raw delay without assumed ms", "per-frame palette via Effect.frm", "explicit unresolved spell/audio binding"])
        row["mixed_repeat_sentinel"] = any(v["Repeat" + side + "From"] == -1 and v["Repeat" + side + "To"] != -1 for side in ["Front", "Back"])
        row["repeat_sentinel_semantics"] = "UNKNOWN; preserve actual From/To independently"
        for j, f in enumerate(rec["frames"]):
            vv = f["fields"]
            if vv["Frame#"] != -1 and not 0 <= vv["Frame#"] < count:
                raise ValueError("effect frame outside EPF")
            side = "front_frames" if j < v["NumFrontFrames"] else "back_frames"
            item = {"frame_index": vv["Frame#"], "palette_index": frm_indices[vv["Frame#"]] if vv["Frame#"] >= 0 else None, "delay_raw": vv["Delay"], "alpha_raw": vv["Alpha"], "light_raw": vv["Light"], "source_line": f["line"], "source_byte_offset": f["offset"], "unsupported_semantics": "FRAME_MINUS_ONE: retain delay/event; do not index last palette/frame" if vv["Frame#"] == -1 else None}
            row[side].append(item)
            all_effect_frames.append(item)
        effects.append(row)
    write_jsonl(out / "kr_asset_effect_sequences.jsonl", effects)

    secondary = []
    for name, kind, keys in [("EffLayer.tbl", "legacy_effect_layer", ["ID", "front", "back"]), ("EffRange.tbl", "legacy_effect_range", ["ID", "framecount", "palette", "blending"] )]:
        for n, o, t, _ in text_lines(entries[name.casefold()][2]):
            t = t.split(";", 1)[0].strip()
            if not t:
                continue
            raw = t.split()
            if len(raw) != len(keys):
                raise ValueError("legacy effect row shape mismatch")
            values = {k: float(v) if "." in v else int(v) for k, v in zip(keys, raw)}
            row = base(kind, values["ID"], name, n, o)
            row.update(original_value=values, consumer="P2 compare legacy EffLayer/EffRange against newer Effect.tbl without joining ID numbers automatically", semantic_version_relation="UNKNOWN; EffRange ID0 explicitly dummy and Effect.tbl ID0 nonempty; numeric equivalence rejected")
            secondary.append(row)
    write_jsonl(out / "kr_asset_legacy_effect_tables.jsonl", secondary)

    # Preserve all sound IDs even when WAV data/PCM are byte-identical.
    audio = []
    grouped = defaultdict(list)
    for key, (name, offset, data) in sounds.items():
        if not name.casefold().endswith(".wav"):
            raise ValueError("unexpected non-WAV SND member")
        with wave.open(io.BytesIO(data), "rb") as w:
            params = w.getparams()
            pcm = w.readframes(w.getnframes())
            if len(pcm) != w.getnframes() * w.getnchannels() * w.getsampwidth():
                raise ValueError("truncated PCM")
        idx = int(re.search(r"(\d+)", name)[1])
        row = {"id": f"KR491:sound:{idx:03}", "kind": "sound_metadata", "original_value": {"source_name": name, "channels": params.nchannels, "sample_rate_hz": params.framerate, "sample_width_bytes": params.sampwidth, "frame_count": params.nframes, "compression": params.comptype, "duration_seconds": params.nframes / params.framerate}, "source": {"source_id": "LIB-010", "source_family": "KR491_CLIENT", "container_member": "NWind.snd", "container_sha256": EXPECTED["NWind.snd"], "member": name, "member_byte_offset": offset, "member_sha256": sha(data), "pcm_sha256": sha(pcm)}, "fact_status": "ORIGINAL_VERIFIED", "fact_scope": "WAV structure only", "utilization_status": "DECODED", "selected_for_build": False, "selected_for_p2_technical_input": True, "reconstructed_value": None, "target_era_match": "UNKNOWN", "consumer": "P2 bounded audio decoder; no spell/action assigned by generic fallback", "spell_id": None, "loop": None, "volume": None, "playback_timestamp": None, "game_output_test": "NOT_RUN", "conversion_history": "original SND member, no transcoding"}
        audio.append(row)
        grouped[sha(data)].append(row["id"])
    for row in audio:
        row["same_wav_ids"] = grouped[row["source"]["member_sha256"]]
    write_jsonl(out / "kr_asset_sound_metadata.jsonl", audio)

    # Entire Korean resource indexed by hash/location; only necessary UI evidence
    # values are quoted, so this is not a republished original RES file.
    ui = []
    lines = list(text_lines(entries["str_kor.res"][2]))
    patterns = ["새 이름", "암호가 정확", "이어서 하기", "성별 고르기", "모양 고르기", "새 사용자가", "잘못된 생년", "새로운 유저", "당신의", "아이템", "마법", "정보", "접속 인원", "게시판", "말하기", "도움말", "나가기", "고구려인", "부여인", "신라인", "클라이언트 버젼", "서버와의 연결", "DAT 파일", "게임정보가 서버"]
    text_index = []
    for n, o, t, size in lines:
        text_index.append({"line": n, "byte_offset": o, "byte_length": size, "text_sha256": sha(t.encode("cp949"))})
        if not any(t == p or t.startswith(p) for p in patterns):
            continue
        row = base("ui_string", n, "Str_Kor.res", n, o)
        row.update(original_value=t, control_0x11_meaning="UNKNOWN; preserved as U+0011", consumer="P2 Korean text/creation/UI field evidence; string presence does not prove action order/server acceptance", unknown_fields=["runtime call index", "choice order", "name length/duplicate/server rule", "target1998-2001 continuity"])
        ui.append(row)
    write_jsonl(out / "kr_asset_ui_strings.jsonl", ui)

    # Decode every frame of affected sprite families, not only chosen pictures.
    sprites = []
    sprite_frame_count = 0
    sprite_decode_errors = []
    for family in ["Body", "Head", "Sword", "Monster", "Effect", "Item", "DLGLOGIN", "DLGNEW01", "DLGNEW02"]:
        name = family + ".epf"
        epf = reader.Epf(entries[name.casefold()][2])
        bounds = []
        decoded_digest = hashlib.sha256()
        for i in range(epf.count):
            try:
                f = epf.frame(i)
            except ValueError as error:
                top, left, bottom, right, _, _ = reader.unpack("<hhhhII", epf.table, i * 16)
                bounds.append([left, top, right - left, bottom - top])
                sprite_decode_errors.append({"member": name, "frame_index": i, "result": "BLOCKED", "reason": str(error), "impact": "mask semantics/format unresolved; no clipping or blank replacement"})
                continue
            bounds.append([f.left, f.top, f.width, f.height])
            decoded_digest.update(struct.pack("<IiiiiI", i, f.left, f.top, f.width, f.height, len(f.indices)))
            decoded_digest.update(f.indices)
            decoded_digest.update(f.alpha)
            sprite_frame_count += 1
        row = base("sprite_family", family, name)
        row.update(original_value={"family": family, "frame_count": epf.count, "canvas_width": epf.width, "canvas_height": epf.height, "frame_bounds": bounds, "bounds_columns": ["left", "top", "width", "height"], "frame_index_rule": "array position = zero-based original EPF index", "entry_table_offset": 12 + len(epf.pixels), "entry_byte_stride": 16}, decoded_frames_sha256=decoded_digest.hexdigest(), decode_errors=[x for x in sprite_decode_errors if x["member"] == name], decoded_digest_rule="SHA256(concat for every index: little-endian uint32 index,int32 left/top/width/height,uint32 pixel_count,indices,alpha))", consumer="P2 frame rectangle/stencil data; frame origin preserved; no automatic horizontal flip", image_preview="PRIVATE_ONLY", game_render_test="NOT_RUN")
        sprites.append(row)
    write_jsonl(out / "kr_asset_sprite_frames.jsonl", sprites)

    result = {"task_id": "BARAM_REBUILD_P1_5_001", "scope": "full fixed-source selected KR491 text tables, Effect.frm, 163 WAV headers+PCM, all frames in 9 specified EPF families; static only", "inputs": EXPECTED, "parser_sha256": script_fingerprint, "counts": {"parts": len(parts), "monster_group_ids": len(mons), "draw_order_tokens": len(draw), "effect_sequences": len(effects), "effect_sequence_frames": len(all_effect_frames), "effect_frame_palette_rows": len(frm_rows), "legacy_effect_table_rows": len(secondary), "sound_ids": len(audio), "unique_wav_hashes": len(grouped), "ui_selected_strings": len(ui), "korean_resource_lines": len(lines), "sprite_frames_decoded": sprite_frame_count}, "asset_tables": metadata, "effect_raw_delays": dict(sorted(Counter(x["delay_raw"] for x in all_effect_frames).items())), "effect_raw_alpha": dict(sorted(Counter(x["alpha_raw"] for x in all_effect_frames).items())), "ui_resource_index": {"source": source("Str_Kor.res"), "encoding": "cp949 strict; no replacement characters", "entries": text_index}, "limitations": ["Metadata decoding is not gameplay or target-era PASS", "No skill-name to effect/sound binding established", "Frame direction/action/timing/layer-token meanings remain observations needed", "EffLayer/EffRange old IDs must not be directly joined to Effect.tbl", "No independent KR client action-motion table found", "Sound loop/volume/call timing unknown", "Creation strings prove options' presence in this resource, not UI order, server policy or exact1998-2001 eligibility", "No NPC name/look or Korean original dialogue binding from these graphics tables"], "sprite_decode_errors": sprite_decode_errors, "status": "PARTIAL_UI_MASK_UNDECODED" if sprite_decode_errors else "PASS_STATIC_SCOPE_WITH_SEMANTIC_GAPS", "game_tests": "NOT_RUN"}
    p = root / "docs/rebuild/p1_5/research_assets.json"
    result["effect_edge_cases"] = {"minus_one_frame_entries": sum(x["frame_index"] == -1 for x in all_effect_frames), "mixed_repeat_sentinel_sequences": [x["original_value"]["ID"] for x in effects if x["mixed_repeat_sentinel"]], "disposition": "raw fields preserved; unknown behavior remains unsupported, no negative Python indexing or forced replacement"}
    if args.visual_root:
        visual_root = Path(args.visual_root)
        external = []
        for repo in ["DizzyThermal/TKViewer", "DizzyThermal/EPFViewer"]:
            acquired = json.loads((visual_root / repo / "ACQUISITION.json").read_text())
            for entry in acquired["entries"]:
                if entry["acquisition_status"] != "ACQUIRED":
                    continue
                data = (visual_root / repo / entry["path"]).read_bytes()
                blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                if sha(data) != entry["sha256"] or blob != entry["sha"]:
                    raise ValueError("external source byte mismatch")
            external.append({"repository": repo, "ref": acquired["ref"], "source_family": "DizzyThermal_Nexus_tools_related_lineage", "acquired_files": sum(x["acquisition_status"] == "ACQUIRED" for x in acquired["entries"]), "total_tree_files": len(acquired["entries"]), "tree_truncated": False, "source_text_status": "ALL_TREE_TEXT_FILES_ACQUIRED_AND_BLOB_VERIFIED", "runnable_status": "NOT_READY_BINARY_ASSETS_AND_CLIENT_DATA_NOT_ACQUIRED_OR_EXECUTED", "build_or_execute": "NOT_RUN", "files": acquired["entries"]})
        result["external_visual_sources"] = external
        index = visual_root / "previews/INDEX.json"
        if index.is_file():
            result["private_source_previews"] = json.loads(index.read_text())
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result["status"], "counts": result["counts"], "sprite_decode_errors": sprite_decode_errors}, ensure_ascii=False))
    return 2 if sprite_decode_errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", required=True)
    parser.add_argument("--snd", required=True)
    parser.add_argument("--reader", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--visual-root", help="Private pinned-source tree acquisition manifests and optional preview index")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except FileNotFoundError as error:
        print(json.dumps({"result": "BLOCKED", "error": "required input inaccessible", "input": Path(error.filename).name}), file=sys.stderr)
        raise SystemExit(2)
    except (ValueError, OSError, struct.error, wave.Error, UnicodeError) as error:
        print(json.dumps({"result": "FAIL", "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
