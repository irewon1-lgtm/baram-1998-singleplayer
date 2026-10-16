#!/usr/bin/env python3
"""Build private KR491 inspection assets from fixed-hash original DAT/SND.

Reuses the P1.5 reader without changing it. Original mask failures stay failures;
no clipping, transparent substitution, negative frame indexing or spell/audio
binding is introduced. Motion labels are separately recorded visual inferences.
All decoded images, audio and detailed manifests must stay outside the checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import wave


REPO = Path(__file__).resolve().parents[3]
PINS = {
    "dat": "f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7",
    "snd": "003534e57b426971900f7ec39f5e65d3662fa5f32672cd0564d04680e31e300c",
    "reader": "f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2",
}
SOURCE_ID = "LIB-010"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, pin):
    data = Path(path).read_bytes()
    if sha(data) != pin:
        raise ValueError("input hash mismatch: " + Path(path).name)
    return data


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def mask_diagnosis(reader, epf, frame_index):
    top, left, bottom, right, pixels, mask = reader.unpack("<hhhhII", epf.table, frame_index * 16)
    width, height = right - left, bottom - top
    cursor = mask
    rows = []
    for row_index in range(height):
        runs = []
        row_offset = cursor
        while True:
            run, = reader.region(epf.pixels, cursor, 1)
            cursor += 1
            if run == 0:
                break
            runs.append(run)
        length = sum(x & 127 for x in runs)
        if length > width or any((x & 127) == 0 for x in runs):
            rows.append({"row": row_index, "mask_payload_offset": row_offset,
                         "raw_runs": runs, "decoded_width": length,
                         "expected_width": width})
    return {"frame": frame_index, "rectangle": [left, top, width, height],
            "pixel_offset": pixels, "mask_offset": mask, "mask_end": cursor,
            "invalid_rows": len(rows), "first_invalid_rows": rows[:3],
            "source_pixels_preserved": True,
            "resolution": "BLOCKED_ORIGINAL_MASK; no clipping or frame replacement"}


def build(args):
    output = args.output.resolve()
    if output == REPO or output.is_relative_to(REPO):
        raise ValueError("decoded assets must be outside the public checkout")
    output.mkdir(parents=True, exist_ok=True)
    checked(args.reader, PINS["reader"])
    reader = load_module(args.reader, "kr491_inspection_fixed_reader")
    tables = load_module(REPO / "tools/rebuild/p1_5/inspect_kr_tables.py", "kr491_inspection_tables")
    raw = checked(args.dat, PINS["dat"])
    raw_snd = checked(args.snd, PINS["snd"])
    entries, sound_entries = reader.dat_entries(raw), reader.dat_entries(raw_snd)
    consumed = {}

    def member(name):
        actual, offset, data = entries[name.casefold()]
        consumed[actual] = {"member": actual, "bytes": len(data), "sha256": sha(data),
                            "dat_byte_offset": offset, "source_id": SOURCE_ID,
                            "container_sha256": PINS["dat"]}
        return data

    def source(name, **more):
        member(name)
        return {**consumed[entries[name.casefold()][0]], **more}

    epfs, palettes = {}, {}

    def epf(stem):
        if stem not in epfs:
            epfs[stem] = reader.Epf(member(stem + ".epf"))
        return epfs[stem]

    def palette(stem):
        if stem not in palettes:
            palettes[stem] = reader.read_palettes(member(stem + ".pal"))
        return palettes[stem]

    images = {}

    def image(stem, frame, pal, palette_stem=None):
        if frame < 0:
            raise ValueError("negative sentinel is not an image frame")
        palette_stem = palette_stem or stem
        key = f"{stem}:{frame}:{palette_stem}:{pal}"
        if key in images:
            return images[key]
        f = epf(stem).frame(frame)
        pals = palette(palette_stem)
        if not 0 <= pal < len(pals):
            raise ValueError("palette outside source")
        record = {"key": key, "source_id": f"KR491:sprite:{stem}:{frame}",
                  "epf_member": stem + ".epf", "frame": frame,
                  "palette_member": palette_stem + ".pal", "palette": pal,
                  "offset": [f.left, f.top], "size": [f.width, f.height],
                  "source_empty_rectangle": f.width == 0 or f.height == 0}
        if f.width and f.height:
            path = f"images/{stem.lower()}-{frame:05}-{palette_stem.lower()}-{pal}.png"
            target = output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = reader.png_bytes(f.width, f.height, f.rgba(pals[pal]))
            target.write_bytes(data)
            record.update(path=path, sha256=sha(data), rgba_sha256=sha(f.rgba(pals[pal])))
        else:
            # A source-defined zero rectangle remains empty; it is never
            # silently supplied for a missing or undecodable frame.
            record.update(path=None, sha256=None, rgba_sha256=sha(b""))
        images[key] = record
        return record

    # Full source-frame regression, including the earlier two known failures
    # and all login/creation/password peers. Failures are retained, not patched.
    regression = []
    failures = []
    for stem in ["Body", "Head", "Sword", "Shield", "Monster", "Effect", "Item",
                 "DLGLOGIN", "DLGNEW01", "DLGNEW02", "DLGPASS", "NEWUSER"]:
        parsed = epf(stem)
        count = 0
        digest = hashlib.sha256()
        for index in range(parsed.count):
            try:
                f = parsed.frame(index)
                digest.update(struct.pack("<IiiiiI", index, f.left, f.top, f.width, f.height, len(f.indices)))
                digest.update(f.indices)
                digest.update(f.alpha)
                count += 1
            except ValueError as exc:
                failures.append({"member": stem + ".epf", "error": str(exc),
                                 **mask_diagnosis(reader, parsed, index)})
        regression.append({"member": stem + ".epf", "declared": parsed.count,
                           "decoded": count, "failed": parsed.count - count,
                           "decoded_frames_sha256": digest.hexdigest()})

    parts = {}
    selections = {"Body": [0, 2], "Head": [0, 1], "Sword": [0, 1], "Shield": [0, 1]}
    for stem, ids in selections.items():
        rows = [v for _, _, v in tables.parse_counted(member(stem + ".tbl"))]
        result = []
        for part_id in ids:
            row = rows[part_id]
            start = row["Starting"]
            end = rows[part_id + 1]["Starting"] if part_id + 1 < len(rows) else epf(stem).count
            result.append({"source_id": f"KR491:{stem.lower()}:{part_id}", "id": part_id,
                           "table": source(stem + ".tbl"), "raw_fields": row,
                           "frames": [image(stem, index, row["Palette"]) for index in range(start, end)]})
        parts[stem.lower()] = result

    draw = [x for x in member("DrwOrder.tbl").decode("ascii").split(";") if x]
    if len(draw) != 100 or any(set(x) - set("wbhs0") or len(x) != 4 for x in draw):
        raise ValueError("unexpected draw-order table")
    motion = {"status": "VISUALLY_INFERRED_FROM_ORIGINAL_FRAME_CONTACT_SHEET",
              "direction_order": ["north", "east", "south", "west"],
              "direction_mirroring": "NONE; four original frame groups",
              "layer_token_candidate": {"b": "body", "h": "head", "w": "sword", "s": "shield", "0": "absent"},
              "layer_token_semantics": "INFERRED; DrwOrder.tbl is preserved verbatim",
              "draw_order_source": source("DrwOrder.tbl"), "draw_order": draw,
              "inspection_duration_ms": 130,
              "original_animation_time": "UNKNOWN; inspection duration is not an original speed",
              "standing": {"body": [[0], [3], [6], [9]], "head": [[0], [3], [6], [9]], "sword": [], "shield": []},
              "walking": {"body": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]],
                          "head": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]], "sword": [], "shield": []},
              "armed_walking": {"body": [[12, 13, 14], [15, 16, 17], [18, 19, 20], [21, 22, 23]],
                                "head": [[12, 13, 14], [15, 16, 17], [18, 19, 20], [21, 22, 23]],
                                "sword": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]],
                                "shield": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]},
              "attack": {"body": [[24, 25], [26, 27], [28, 29], [30, 31]],
                         "head": [[24, 25], [26, 27], [28, 29], [30, 31]],
                         "sword": [[12, 13], [14, 15], [16, 17], [18, 19]],
                         "shield": [[12, 13], [14, 15], [16, 17], [18, 19]]},
              "casting": {"body": [[72], [73], [74], [75]], "head": [[72], [73], [74], [75]], "sword": [], "shield": []},
              "standing_binding": "holding neutral first image of each directional walking source group; runtime historical idle rule unresolved",
              "clothes_binding": "KR491 Body.tbl contains complete outfit bodies, no separate Coat.tbl; changing body ID switches original outfit"}

    # Full effect sequence and palette graph. Unsupported semantics remain
    # explicit even though the individual underlying images can be inspected.
    frm = member("Effect.frm")
    count, = struct.unpack_from("<I", frm)
    if len(frm) != 4 + 4 * count or count != epf("Effect").count:
        raise ValueError("effect frame/EPF count mismatch")
    pal_indices = list(struct.unpack_from("<" + "I" * count, frm, 4))
    if any(index >= len(palette("Effect")) for index in pal_indices):
        raise ValueError("effect palette index outside source")
    effects = []
    for rec in tables.parse_effects(member("Effect.tbl")):
        fields = rec["fields"]
        seq = {"id": fields["ID"], "source_id": f"KR491:effect_sequence:{fields['ID']}",
               "source": source("Effect.tbl", line=rec["line"], line_byte_offset=rec["offset"]),
               "raw_fields": fields, "front_frames": [], "back_frames": [],
               "skill_id": None, "sound_id": None, "hit_time": None,
               "delay_unit": "UNKNOWN", "alpha_semantics": "UNKNOWN", "light_semantics": "UNKNOWN",
               "inspection_policy": "single traversal; source repeat ranges are retained, unresolved repeats not silently executed"}
        for i, raw_frame in enumerate(rec["frames"]):
            f = raw_frame["fields"]
            idx = f["Frame#"]
            if idx < -1 or idx >= count:
                raise ValueError("unsupported effect frame index")
            frame = {"source_line": raw_frame["line"], "raw_fields": f,
                     "sentinel": idx == -1, "image": image("Effect", idx, pal_indices[idx]) if idx >= 0 else None,
                     "inspection_duration_ms": max(1, f["Delay"]),
                     "inspection_duration_semantics": "display experiment interprets numeric Delay as ms; original unit unproven"}
            seq["front_frames" if i < fields["NumFrontFrames"] else "back_frames"].append(frame)
        unsupported = []
        for side in ("Front", "Back"):
            if fields["Repeat" + side + "From"] != -1 or fields["Repeat" + side + "To"] != -1:
                unsupported.append("UNRESOLVED_REPEAT_" + side.upper())
        all_frames = seq["front_frames"] + seq["back_frames"]
        if any(f["sentinel"] for f in all_frames):
            unsupported.append("FRAME_MINUS_ONE_SENTINEL")
        if any(f["raw_fields"]["Alpha"] != 0 for f in all_frames):
            unsupported.append("NONZERO_ALPHA_SEMANTICS")
        if any(f["raw_fields"]["Light"] != -1 for f in all_frames):
            unsupported.append("LIGHT_COMMAND_SEMANTICS")
        seq.update(unsupported_commands=unsupported,
                   preview_supported=not unsupported,
                   preview_scope="raw original frame slideshow using source-over and experimental display delay; no skill, hit, sound or original blend/time proof",
                   original_semantic_replay_supported=False,
                   image_frame_inspection_supported=True)
        effects.append(seq)

    guards = []
    if args.batch_observations:
        batch_bytes = args.batch_observations.read_bytes()
        batch = json.loads(batch_bytes)
        for candidate in batch["observations"]:
            if candidate["candidate_id"] not in {f"WD-MS-{i:03}" for i in range(1, 6)}:
                continue
            if candidate["received"] is not True or candidate["bytes_and_declared_record_validation"] != "PASS":
                raise ValueError("selected Work observation was not byte-validated")
            guard = {"candidate_id": candidate["candidate_id"], "field": candidate["field"],
                     "candidate_value": candidate["candidate_value"],
                     "observation_input_sha256": sha(batch_bytes),
                     "consumption": "INSPECTION_GUARD; originals remain unchanged; no GIF time-to-game time conversion",
                     "data_patch_applied": False}
            if candidate["candidate_id"] == "WD-MS-001":
                if guard["candidate_value"]["client_delay_unit"] != "UNKNOWN":
                    raise ValueError("unreviewed source timing claim")
            else:
                value = guard["candidate_value"]
                idx = int(value["effect_sequence_id"].rsplit(":", 1)[1])
                frames = effects[idx]["front_frames"]
                step = value.get("source_omitted_step", value.get("differing_step"))
                source_frame = step.get("frame_index", step.get("client_frame"))
                if frames[step["index_zero_based"]]["raw_fields"]["Frame#"] != source_frame:
                    raise ValueError("batch-to-original effect reference changed")
                effects[idx].setdefault("guide_discrepancy_guards", []).append(guard)
            guards.append(guard)
        if len(guards) != 5:
            raise ValueError("not all five motion guards were received")

    sounds = []
    for _, (name, offset, data) in sorted(sound_entries.items()):
        if not name.lower().endswith(".wav"):
            raise ValueError("unexpected SND member")
        with wave.open(io.BytesIO(data)) as stream:
            params = stream.getparams()
            pcm = stream.readframes(params.nframes)
        if len(pcm) != params.nframes * params.nchannels * params.sampwidth:
            raise ValueError("truncated WAV")
        path = "sounds/" + name.lower()
        (output / "sounds").mkdir(exist_ok=True)
        (output / path).write_bytes(data)
        # Decode the measured source formats, including signed 16-bit PCM.
        # Reject unknown formats rather than reporting an unexamined signal.
        if params.sampwidth not in (1, 2) or params.nchannels not in (1, 2):
            raise ValueError("unmeasured PCM width/channel format")
        peak = (max((abs(x - 128) for x in pcm), default=0) if params.sampwidth == 1
                else max((abs(x[0]) for x in struct.iter_unpack("<h", pcm)), default=0))
        sounds.append({"source_id": "KR491:sound:" + Path(name).stem,
                       "member": name, "path": path, "sha256": sha(data),
                       "container_sha256": PINS["snd"], "member_byte_offset": offset,
                       "pcm_sha256": sha(pcm), "channels": params.nchannels,
                       "sample_rate": params.framerate, "sample_width": params.sampwidth,
                       "frames": params.nframes, "duration_seconds": params.nframes / params.framerate,
                       "decoded_pcm_peak_amplitude": peak,
                       "audio_device_output": "NOT_RUN", "hardware_listening": "NOT_RUN",
                       "skill_id": None, "effect_id": None})

    # Source-defined UI frames. DLGNEW02 uses BARAM.PAL: KR491 original
    # Winbaram.exe call 0x44649a -> constructor 0x4196c0 passes palette=NULL;
    # 0x419727..0x419744 resolves NULL to BARAM.PAL. See UI_PALETTE_DIAGNOSIS.json.
    # This static binding is independent of the P1.5 EPF reader.
    ui = []
    for stem, palstem in [("DLGNEW02", "Baram"), ("NEWUSER", "NEWUSER"), ("TITLE", "TITLE")]:
        for i in range(epf(stem).count):
            ui.append({"name": stem, "frame": i, "image": image(stem, i, 0, palstem),
                       "palette_binding": "original matching PAL" if stem == palstem else "ORIGINAL_BINARY_STATIC_BINDING: KR491 Winbaram.exe 0x44649a -> 0x4196c0 -> BARAM.PAL default",
                       "historical_flow_binding": "UNKNOWN"})

    mask_report = {"schema": "baram.p2.kr491-mask-regression/1", "families": regression,
                   "failures": failures, "old_failures_reproduced": ["DLGLOGIN.epf:0", "DLGNEW01.epf:0"],
                   "new_peer_failure": "DLGPASS.epf:0",
                   "diagnosis": "two opaque FF127 runs make each login/new01/password mask row two pixels wider than its source pixel rectangle",
                   "proposed_global_FF126_fix": "REJECTED: valid NEWUSER rows need five FF127 runs + 5 = 640; global change corrupts them",
                   "independent_reader_comparison": "Pinned TKViewer Stencil.java and EPFViewer EpfFileHandler.gd also decode 0xff as127; both share lineage, not independent historical evidence",
                   "minimal_fix": "NONE_PROVEN; source-mask failures stay BLOCKED; valid DLGNEW02/NEWUSER used instead"}
    dump(output / "mask_regression.json", mask_report)
    runtime = {"schema": "baram.p2.kr491-runtime/1", "source_id": SOURCE_ID,
               "source_version": "KR4.91", "target1998_2001_match": "UNVERIFIED",
               "builder_sha256": sha(Path(__file__).read_bytes()), "input_sha256": PINS,
               "parts": parts, "motion_inspection": motion,
               "character_variants": [{"id": "original-base", "body": 0, "head": 0, "sword": 0, "shield": 0},
                                      {"id": "original-outfit2", "body": 2, "head": 1, "sword": 1, "shield": 1}],
               "effects": effects, "sounds": sounds, "ui": ui, "work_batch_guards": guards,
               "source_members": list(consumed.values()),
               "unresolved": ["historical frame times", "KR client motion/part map proof", "NPC name/look binding",
                              "skill/effect/sound linkage", "hit and next-action timing", "Alpha/Light and mixed repeat commands",
                              "three corrupt original UI masks", "native output and hardware listening"]}
    dump(output / "kr491_runtime.json", runtime)
    result = {"status": "PARTIAL_ORIGINAL_ASSETS_BUILT_WITH_SEMANTIC_AND_MASK_GAPS",
              "source_members": len(consumed), "images": len(images),
              "nonempty_png": sum(x["path"] is not None for x in images.values()),
              "parts": {k: len(v) for k, v in parts.items()}, "effect_sequences": len(effects),
              "effect_sequence_frames": sum(len(x["front_frames"]) + len(x["back_frames"]) for x in effects),
              "frame_slideshow_supported_sequences": sum(x["preview_supported"] for x in effects),
              "work_batch_guards_consumed": len(guards),
              "sentinel_frames": sum(f["sentinel"] for x in effects for side in ["front_frames", "back_frames"] for f in x[side]),
              "sounds": len(sounds), "non_silent_pcm": sum(x["decoded_pcm_peak_amplitude"] > 0 for x in sounds),
              "regression_declared_frames": sum(x["declared"] for x in regression),
              "regression_decoded_frames": sum(x["decoded"] for x in regression),
              "original_mask_failures": len(failures), "runtime_render": "NOT_RUN",
              "runtime_manifest_sha256": sha((output / "kr491_runtime.json").read_bytes()),
              "output": str(output)}
    dump(output / "BUILD_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--snd", type=Path, required=True)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-observations", type=Path)
    try:
        return build(parser.parse_args())
    except (ValueError, OSError, struct.error, wave.Error, UnicodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
