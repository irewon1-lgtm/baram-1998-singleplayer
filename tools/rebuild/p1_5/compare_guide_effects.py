#!/usr/bin/env python3
"""Exact source-bitmap comparison; never joins web-image and client effect IDs.

Pillow's composited GIF frames are compared on black backgrounds with the
trimmed original RGB bitmaps. Equality deliberately excludes position/timing.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

from PIL import Image, ImageSequence


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signature(image):
    box = image.getbbox()
    if box is None:
        return None
    cropped = image.crop(box)
    return cropped.size, digest(cropped.tobytes())


def main(args):
    repo = Path(args.repo)
    content = repo / "docs/rebuild/p1_5/selected_content"
    spec = importlib.util.spec_from_file_location("kr_fixed_inspector", Path(__file__).with_name("inspect_kr_tables.py"))
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    reader = inspector.load_reader(args.reader)
    raw = reader.dat_entries(inspector.checked(args.dat, inspector.EXPECTED["NWind.dat"]))
    epf = reader.Epf(raw["effect.epf"][2])
    palettes = reader.read_palettes(raw["effect.pal"][2])
    frame_palette = {row["original_value"]["frame_index"]: row["original_value"]["palette_index"] for row in map(json.loads, (content / "kr_asset_effect_frame_palettes.jsonl").read_text().splitlines())}
    lookup = defaultdict(list)
    for index in range(epf.count):
        frame = epf.frame(index)
        if not frame.width or not frame.height:
            continue
        rgba = Image.frombytes("RGBA", (frame.width, frame.height), frame.rgba(palettes[frame_palette[index]]))
        rgb = Image.new("RGB", rgba.size, (0, 0, 0))
        rgb.paste(rgba, (0, 0), rgba)
        lookup[signature(rgb)].append(index)

    effects = [json.loads(row) for row in (content / "kr_asset_effect_sequences.jsonl").read_text().splitlines()]
    guide_rows = [json.loads(row) for row in (content / "kr_official_core.jsonl").read_text().splitlines()]
    acquisition = json.loads(Path(args.guide_manifest).read_text())
    named = []
    results = []
    for source in acquisition:
        if source.get("status") != 200 or not source.get("local_private_path"):
            continue
        if "/effect/" not in source["original_url"].casefold():
            continue
        match = re.search(r"([^/]+\.gif)$", source["original_url"], re.I)
        if not match:
            continue
        basename = match[1].casefold()
        image_path = Path(source["local_private_path"])
        if digest(image_path.read_bytes()) != source["sha256"]:
            raise ValueError("guide image hash mismatch")
        guide_matches = []
        with Image.open(image_path) as image:
            for index, frame in enumerate(ImageSequence.Iterator(image)):
                rgba = frame.convert("RGBA")
                rgb = Image.new("RGB", rgba.size, (0, 0, 0))
                rgb.paste(rgba, (0, 0), rgba)
                sig = signature(rgb)
                guide_matches.append({"gif_frame": index, "blank": sig is None, "exact_trimmed_rgb_matches": lookup.get(sig, []) if sig else []})
        nonblank = [x for x in guide_matches if not x["blank"]]
        # Only full, one-layer, ordered sequences can be identified here.
        # Layered/composited/repeated animations remain unselected, even when
        # several images resemble source frames.
        exact = []
        near = []
        for effect in effects:
            if effect["back_frames"] or len(effect["front_frames"]) != len(nonblank):
                continue
            original_frames = [x["frame_index"] for x in effect["front_frames"]]
            equal = sum(f >= 0 and f in g["exact_trimmed_rgb_matches"] for f, g in zip(original_frames, nonblank))
            if original_frames and equal == len(original_frames):
                exact.append(effect["id"])
            elif equal:
                near.append({"effect_id": effect["id"], "exact_frames": equal, "sequence_length": len(original_frames)})
        mapped_rows = []
        for guide_row in guide_rows:
            value = guide_row.get("original_value", {})
            if not isinstance(value, dict):
                continue
            images = value.get("guide_effect_relative_images", [])
            if any(str(x).casefold().endswith(basename) for x in images) and set(guide_row.get("source_ids", [])) & set(source.get("parent_source_ids", [])):
                mapped_rows.append({"guide_row_id": guide_row["content_id"], "entity_name_ko": guide_row.get("entity_name_ko"), "source_ids": guide_row.get("source_ids"), "source_locator": guide_row.get("source_locator"), "input_sha256": guide_row.get("input_sha256"), "html_archive_capture": guide_row.get("archive_capture_at")})
        actual_capture = source.get("actual_archive_capture")
        capture_within_target = bool(actual_capture and "1998" <= actual_capture[:4] <= "2001")
        entry = {"guide_source_id": source["source_id"], "guide_sha256": source["sha256"], "guide_url": source["original_url"], "requested_archive_capture": source.get("archive_capture_requested"), "actual_archive_capture": actual_capture, "image_capture_within_target_period": capture_within_target, "gif_frames": guide_matches, "unique_exact_full_sequence": exact[0] if len(exact) == 1 else None, "exact_full_sequence_candidates": exact, "near_candidates_not_selected": sorted(near, key=lambda row: -row["exact_frames"])[:5], "guide_skill_rows": mapped_rows, "numeric_ID_join": False, "runtime_timing_or_sound_proof": False}
        results.append(entry)
        for row in mapped_rows:
            # Keep the full guide relationship; a reused GIF may serve several
            # skills. Selection is only for P2 image identity, never spell rules.
            named.append({"id": "KR491:guide_image:" + source["source_id"] + ":" + str(row["guide_row_id"]), "kind": "guide_effect_bitmap_binding", "source_ids": ["LIB-010", source["source_id"]] + row["source_ids"], "original_value": {"guide_row_id": row["guide_row_id"], "entity_name_ko": row["entity_name_ko"], "guide_image_source_id": source["source_id"], "guide_image_sha256": source["sha256"], "effect_sequence_id": exact[0] if len(exact) == 1 else None, "matched_full_sequence_count": len(exact)}, "reconstructed_value": None, "fact_status": "CORROBORATED_RECONSTRUCTION" if len(exact) == 1 else "UNKNOWN", "fact_scope": "exact complete ordered nonblank RGB images only; source positions, delays, invocation and sound remain unknown", "requested_image_capture": source.get("archive_capture_requested"), "actual_image_capture": actual_capture, "html_archive_capture": row["html_archive_capture"], "image_capture_within_target_period": capture_within_target, "target_era_eligibility": "CONTEMPORANEOUS_GUIDE_IMAGE; KR491 sequence continuity/placement remains field-specific" if capture_within_target else "UNRESOLVED_LATER_OR_UNKNOWN_IMAGE_CAPTURE", "utilization_status": "IDENTIFIED" if len(exact) == 1 else "DECODED", "selected_for_build": False, "selected_for_p2_technical_input": len(exact) == 1, "consumer": "P2 skill named image identity comparison; no assumed numeric imageID equivalence or audio binding", "test_result": "NOT_RUN"})
    if len({row["id"] for row in named}) != len(named):
        raise ValueError("duplicate guide→effect relationship IDs")
    output = {"method": "Pillow composited GIF→trimmed nonblackRGB SHA256 with exact dimensions→all1611KR491Effect frames and their original FRM palettes→complete front-only ordered effect sequence; no position/timing equivalence. Named HTML row must both reference basename and belong to the acquired image's recorded parent sources.", "script_sha256": digest(Path(__file__).read_bytes()), "counts": {"guide_images_checked": len(results), "unique_guide_image_hashes": len({r["guide_sha256"] for r in results}), "guide_images_with_unique_full_sequence_match": sum(bool(r["unique_exact_full_sequence"]) for r in results), "unique_image_hashes_with_full_sequence_match": len({r["guide_sha256"] for r in results if r["unique_exact_full_sequence"]}), "distinct_effect_sequences_identified": len({r["unique_exact_full_sequence"] for r in results if r["unique_exact_full_sequence"]}), "named_guide_relationship_rows": len(named), "named_exact_relationships": sum(r["selected_for_p2_technical_input"] for r in named), "distinct_exact_skill_names": len({r["original_value"]["entity_name_ko"] for r in named if r["selected_for_p2_technical_input"]})}, "results": results, "game_tests": "NOT_RUN"}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    inspector.write_jsonl(content / "kr_asset_guide_effects.jsonl", named)
    print(json.dumps(output["counts"], ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", required=True)
    parser.add_argument("--reader", required=True)
    parser.add_argument("--guide-manifest", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args)
