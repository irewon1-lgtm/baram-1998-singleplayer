#!/usr/bin/env python3
"""Select bounded source-frame previews without changing the preserved effect graph.

The overlay is private derived data. The report contains IDs and diagnostics only.
Neutral Alpha/Light and one traversal are RECONSTRUCTED inspection behavior;
neither complete effect semantics nor a skill/sound/hit-time binding is claimed.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

SCHEMA = "baram.priority.effect-preview/1"
MAX_DURATION_MS = 10_000
MAX_FRAME_DURATION_MS = 1000
MAX_FRAMES = 4096


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def frame_problem(frame, root):
    """Fail closed; no negative-index, empty-rectangle or missing-image fallback."""
    raw = frame.get("raw_fields", {})
    index = raw.get("Frame#")
    if not isinstance(index, int) or isinstance(index, bool):
        return "INVALID_FRAME_INDEX"
    if index < 0 or frame.get("sentinel", False):
        return "SENTINEL_OR_NEGATIVE_FRAME"
    image = frame.get("image")
    if not isinstance(image, dict):
        return "MISSING_IMAGE_METADATA"
    if image.get("frame") != index:
        return "FRAME_REFERENCE_MISMATCH"
    if image.get("source_empty_rectangle", False):
        return "EMPTY_SOURCE_RECTANGLE"
    size, offset = image.get("size"), image.get("offset")
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 or v > 4096 for v in size):
        return "INVALID_IMAGE_EXTENT"
    if not isinstance(offset, list) or len(offset) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 8192 for v in offset):
        return "INVALID_IMAGE_OFFSET"
    relative = image.get("path")
    if not isinstance(relative, str) or not relative or "\\" in relative:
        return "UNSAFE_IMAGE_PATH"
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        return "UNSAFE_IMAGE_PATH"
    if not path.is_file():
        return "MISSING_FRAME_FILE"
    if path.stat().st_size > 32 * 1024 * 1024:
        return "OVERSIZED_FRAME_FILE"
    data = path.read_bytes()
    if digest(data) != image.get("sha256"):
        return "FRAME_DIGEST_MISMATCH"
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or list(struct.unpack_from(">II", data, 16)) != size:
        return "INVALID_PNG_OR_SIZE"
    delay = raw.get("Delay")
    if not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay <= 0:
        return "INVALID_DELAY"
    for key in ("Alpha", "Light"):
        value = raw.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return "INVALID_" + key.upper()
    return None


def select_effect(effect, root):
    raw = effect["raw_fields"]
    command_flags = []
    for side in ("Front", "Back"):
        if raw.get("Repeat" + side + "From", -1) != -1 or raw.get("Repeat" + side + "To", -1) != -1:
            command_flags.append("UNRESOLVED_REPEAT_" + side.upper())
    frames = effect.get("front_frames", []) + effect.get("back_frames", [])
    if any(f.get("raw_fields", {}).get("Alpha", 0) != 0 for f in frames):
        command_flags.append("ALPHA_UNINTERPRETED")
    if any(f.get("raw_fields", {}).get("Light", -1) != -1 for f in frames):
        command_flags.append("LIGHT_UNINTERPRETED")
    problems, runs, whole = [], [], {}
    for side in ("front", "back"):
        sequence = effect.get(side + "_frames", [])
        if len(sequence) != raw.get("Num" + side.capitalize() + "Frames"):
            problems.append({"side": side, "index": None, "reason": "LAYER_FRAME_COUNT_MISMATCH"})
        active = []

        def flush():
            if active:
                runs.append({"id": f"{side}:{active[0]['source_index']}-{active[-1]['source_index'] + 1}",
                             "side": side, "start": active[0]["source_index"],
                             "end_exclusive": active[-1]["source_index"] + 1,
                             "duration_ms": sum(f["duration_ms"] for f in active),
                             "frames": active.copy()})
                active.clear()

        valid = []
        for position, frame in enumerate(sequence):
            problem = "FRAME_COUNT_LIMIT" if len(frames) > MAX_FRAMES else frame_problem(frame, root)
            if problem:
                flush()
                problems.append({"side": side, "index": position, "source_line": frame.get("source_line"),
                                 "original_frame": frame.get("raw_fields", {}).get("Frame#"), "reason": problem})
                continue
            duration = int(min(MAX_FRAME_DURATION_MS, max(16, frame["raw_fields"]["Delay"])))
            chosen = {"source_index": position, "source_line": frame.get("source_line"),
                      "original_frame": frame["raw_fields"]["Frame#"], "image": frame["image"],
                      "duration_ms": duration}
            if sum(f["duration_ms"] for f in active) + duration > MAX_DURATION_MS:
                flush()
            active.append(chosen)
            valid.append(chosen)
        flush()
        whole[side] = valid
    total = max((sum(f["duration_ms"] for f in whole[s]) for s in ("front", "back")), default=0)
    if total > MAX_DURATION_MS:
        problems.append({"side": "both", "index": None, "reason": "WHOLE_DURATION_LIMIT"})
    whole_available = not problems and bool(frames)
    if whole_available:
        classification = "ORIGINAL_NEUTRAL_SLIDESHOW" if not command_flags else "RECONSTRUCTED_NEUTRAL_SLIDESHOW"
    else:
        classification = "RECONSTRUCTED_VALID_FRAGMENT_ONLY" if runs else "BLOCKED_NO_VALID_FRAME"
    preview = {"schema": SCHEMA, "classification": classification,
               "available": whole_available or bool(runs), "whole_sequence_available": whole_available,
               "fact_status": "RECONSTRUCTED", "bitmap_fact_status": "ORIGINAL_VERIFIED",
               "era_match": "KR4.91_SOURCE_BUILD_TARGET_1998_2001_UNVERIFIED",
               "source_tier": 1, "source_id": effect["source_id"],
               "command_flags": command_flags, "blocked_frames": problems,
               "whole": whole if whole_available else {}, "fragments": runs if not whole_available else [],
               "whole_duration_ms": total if whole_available else None,
               "limits": {"max_duration_ms": MAX_DURATION_MS, "max_frame_duration_ms": MAX_FRAME_DURATION_MS,
                          "max_frames": MAX_FRAMES, "repeat_count": 0},
               "renderer": {"blend": "SOURCE_OVER_NEUTRAL", "opacity": 1.0, "light": "DISABLED",
                            "repeat": "SINGLE_TRAVERSAL", "delay_unit": "EXPERIMENTAL_MS_CLAMP_16_1000"},
               "original_graph_sha256": digest(json.dumps(effect, sort_keys=True, separators=(",", ":")).encode()),
               "semantic_replay": "UNRESOLVED", "skill_sound_hit_binding": "UNKNOWN", "runtime_test": "NOT_RUN"}
    report = {"id": effect["id"], "source_id": effect["source_id"], "classification": classification,
              "baseline_preview_supported": effect.get("preview_supported", False),
              "whole_sequence_available": whole_available, "valid_fragment_count": len(preview["fragments"]),
              "source_frame_count": len(frames), "valid_frame_count": sum(len(whole[s]) for s in whole),
              "has_front": bool(effect.get("front_frames")), "has_back": bool(effect.get("back_frames")),
              "command_flags": command_flags, "blocked_frames": problems,
              "source_tier": 1, "bitmap_fact_status": "ORIGINAL_VERIFIED", "preview_fact_status": "RECONSTRUCTED",
              "era_match": preview["era_match"], "runtime_test": "NOT_RUN"}
    return {"id": effect["id"], "source_id": effect["source_id"], "priority_preview": preview}, report


def build(runtime_path):
    source_bytes = runtime_path.read_bytes()
    source = json.loads(source_bytes)
    effects = source["effects"]
    if len(effects) != 128 or [e["id"] for e in effects] != list(range(128)):
        raise ValueError("expected complete original 128-ID graph")
    selections, records = [], []
    for effect in effects:
        chosen, report = select_effect(effect, runtime_path.parent)
        selections.append(chosen)
        records.append(report)
    sounds = source["sounds"]
    sound_ids = [s["source_id"] for s in sounds]
    if len(sounds) != 163 or len(set(sound_ids)) != 163:
        raise ValueError("expected 163 unique original sound IDs; waveform duplicates preserve IDs")
    summary = {"effects": len(records), "baseline_preview_supported": sum(e["baseline_preview_supported"] for e in records),
               "whole_neutral_previews_selected": sum(e["whole_sequence_available"] for e in records),
               "fragment_only_effects_selected": sum(e["classification"] == "RECONSTRUCTED_VALID_FRAGMENT_ONLY" for e in records),
               "wholly_blocked_effects": sum(e["classification"] == "BLOCKED_NO_VALID_FRAME" for e in records),
               "classifications": dict(Counter(e["classification"] for e in records)),
               "command_flags": dict(Counter(c for e in records for c in e["command_flags"])),
               "blocked_frame_reasons": dict(Counter(p["reason"] for e in records for p in e["blocked_frames"])),
               "sound_ids": len(sound_ids), "unique_sound_waveforms": len({s["pcm_sha256"] for s in sounds}),
               "runtime_execution": "NOT_RUN", "full_original_effect_replay": "UNRESOLVED"}
    overlay = {"schema": "baram.priority.effects-overlay/1", "source_runtime_sha256": digest(source_bytes),
               "builder_sha256": digest(Path(__file__).read_bytes()), "effects": selections}
    report = {"schema": "baram.priority.effects-report/1", "source_runtime_sha256": digest(source_bytes),
              "summary": summary, "records": records,
              "selection_scope": "Original bitmap references; RECONSTRUCTED neutral Alpha/Light, single traversal and experimental delay. Fragment-only records are not complete effects.",
              "historical_failures": "Existing GEN003/platform/mask/saves evidence preserved; no platform PASS inferred."}
    return overlay, report


def apply_overlay(runtime, overlay):
    """Return new graph; caller writes a fresh generation, never the source."""
    cloned = json.loads(json.dumps(runtime))
    by_id = {e["id"]: e for e in overlay["effects"]}
    for effect in cloned["effects"]:
        chosen = by_id[effect["id"]]
        if effect["source_id"] != chosen["source_id"] or digest(json.dumps(effect, sort_keys=True, separators=(",", ":")).encode()) != chosen["priority_preview"]["original_graph_sha256"]:
            raise ValueError("effect source graph changed after selection")
        effect["priority_preview"] = chosen["priority_preview"]
    return cloned


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    for target in (args.overlay, args.report):
        if target.exists() or target.resolve() == args.runtime.resolve():
            raise SystemExit("select new output paths; original or previous generations cannot be overwritten")
    overlay, report = build(args.runtime)
    write_json(args.overlay, overlay)
    write_json(args.report, report)
    print(json.dumps(report["summary"], ensure_ascii=False))
