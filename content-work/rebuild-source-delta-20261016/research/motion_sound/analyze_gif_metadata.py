#!/usr/bin/env python3
"""Read only fixed P1.5 GIF metadata and existing comparison rows.

This does not decode client assets, rebuild tables, modify the old comparison,
render a game, or infer a client Delay unit or a sound ID.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from PIL import Image


EXPECTED = {
    "evidence/guide_effect_comparison.json": "cd16d538439ef2ac4ce621b079e92c0c3a275865ead0497dca6996646ebe0abd",
    "docs/rebuild/p1_5/selected_content/kr_asset_effect_sequences.jsonl": "1a269e602493b04a4ae6b96160d480e16dad7e82ba98344e277396f692036961",
    "docs/rebuild/p1_5/selected_content/kr_asset_guide_effects.jsonl": "63d8fb07e70a72ee3c1a94999c76aac5959edd67fef12d9e3adf99bd2efca7d7",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected, max_bytes=2_000_000):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or symlink input")
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("input byte limit")
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError("input SHA256 mismatch")
    return data


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main(args):
    root = Path(args.package).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = {name: checked(root / name, digest) for name, digest in EXPECTED.items()}
    comparison = json.loads(inputs["evidence/guide_effect_comparison.json"])
    sequences = {r["id"]: r for r in map(json.loads, inputs["docs/rebuild/p1_5/selected_content/kr_asset_effect_sequences.jsonl"].decode().splitlines())}
    bindings = list(map(json.loads, inputs["docs/rebuild/p1_5/selected_content/kr_asset_guide_effects.jsonl"].decode().splitlines()))
    index = json.loads((root / "PRIVATE_IMAGE_INDEX.json").read_text())
    image_paths = {r["sha256"]: r["path"] for r in index}
    evidence = []
    seen = set()
    selected = []
    for row in comparison["results"]:
        if row["unique_exact_full_sequence"] and row["guide_sha256"] not in seen:
            selected.append(row)
            seen.add(row["guide_sha256"])
    if len(selected) != 13:
        raise ValueError("fixed comparison expected 13 unique exact GIFs")
    for row in selected:
        relative = Path(image_paths[row["guide_sha256"]])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("image path traversal")
        p = root / relative
        data = checked(p, row["guide_sha256"])
        if not data.startswith((b"GIF87a", b"GIF89a")):
            raise ValueError("not a GIF")
        timings = []
        with Image.open(p) as image:
            if image.n_frames != len(row["gif_frames"]) or image.n_frames > 300:
                raise ValueError("GIF frame count mismatch")
            loop = image.info.get("loop")
            size = list(image.size)
            if image.width * image.height > 1_000_000:
                raise ValueError("GIF pixel limit")
            for f in row["gif_frames"]:
                image.seek(f["gif_frame"])
                duration = image.info.get("duration")
                if duration is not None and (not isinstance(duration, int) or duration < 0):
                    raise ValueError("invalid declared duration")
                timings.append({
                    "gif_frame": f["gif_frame"],
                    "blank_in_prior_exact_comparison": f["blank"],
                    "declared_duration_ms": duration,
                    "declared_duration_cs": None if duration is None else duration // 10,
                    "disposal_method": getattr(image, "disposal_method", None),
                    "exact_client_frame_candidates": f["exact_trimmed_rgb_matches"],
                })
        seq = sequences[row["unique_exact_full_sequence"]]
        nonblank = [f for f in timings if not f["blank_in_prior_exact_comparison"]]
        if seq["back_frames"] or len(seq["front_frames"]) != len(nonblank):
            raise ValueError("prior full sequence contract mismatch")
        pairs = []
        for source, gif in zip(seq["front_frames"], nonblank):
            if source["frame_index"] not in gif["exact_client_frame_candidates"]:
                raise ValueError("prior exact comparison mismatch")
            raw = source["delay_raw"]
            duration = gif["declared_duration_ms"]
            ratio = None if not raw or duration is None else str(Fraction(duration, raw))
            pairs.append({"client_frame_index": source["frame_index"], "effect_tbl_line": source["source_line"], "effect_tbl_byte_offset": source["source_byte_offset"], "raw_delay_unit_unknown": raw, "gif_frame": gif["gif_frame"], "gif_declared_ms": duration, "numerical_ratio_ms_per_raw_value_NOT_A_UNIT_ASSIGNMENT": ratio})
        ratios = sorted({f["numerical_ratio_ms_per_raw_value_NOT_A_UNIT_ASSIGNMENT"] for f in pairs})
        related = [b["id"] for b in bindings if b["original_value"]["guide_image_sha256"] == row["guide_sha256"]]
        evidence.append({
            "record_id": "MS-GIF-TIMING-" + seq["id"].rsplit(":", 1)[-1].zfill(3),
            "kind": "EXISTING_BYTES_NEW_CONTAINER_TIMING_ANALYSIS",
            "binding_ids": ["BND-022", "BND-023", "BND-024"],
            "requirement_ids": ["RQ-086", "RQ-088", "RQ-089", "RQ-093", "RQ-094"],
            "guide_source_id": row["guide_source_id"],
            "guide_url": row["guide_url"],
            "guide_sha256": row["guide_sha256"],
            "guide_bytes": len(data),
            "guide_input_relative_path": relative.as_posix(),
            "actual_archive_capture": row["actual_archive_capture"],
            "requested_archive_capture": row["requested_archive_capture"],
            "effect_sequence_id": seq["id"],
            "effect_source": seq["source"],
            "related_stable_guide_bindings": related,
            "gif_dimensions_px": size,
            "gif_declared_loop": loop,
            "gif_frame_metadata": timings,
            "aligned_nonblank_timing_pairs": pairs,
            "numerical_ratio_set_NOT_A_CLIENT_UNIT": ratios,
            "constant_numerical_scale_across_all_nonblank_frames": len(ratios) == 1,
            "meaning": "Exact RGB identity does not imply equal timing. GIF centiseconds are container declarations, not recorded client elapsed time or hit time.",
            "client_delay_unit": "UNKNOWN",
            "sound_id": None,
            "runtime_test": "NOT_RUN",
        })
    discrepancies = []
    specs = [("P15-ARIMG-9fea529308b2", 44, "SOURCE_LEADING_FRAME_OMITTED"), ("P15-ARIMG-82708b093b28", 1, "SOURCE_FRONT_FRAME_OMITTED_AND_BACK_UNPROVEN"), ("P15-ARIMG-d8a35803b6cf", 10, "ONE_DIFFERENT_FRAME"), ("P15-ARIMG-ffa43c98a126", 45, "ONE_DIFFERENT_FRAME")]
    for source_id, effect_id, classification in specs:
        row = next(r for r in comparison["results"] if r["guide_source_id"] == source_id)
        seq = sequences[f"KR491:effect_sequence:{effect_id}"]
        gf = [f for f in row["gif_frames"] if not f["blank"]]
        sf = seq["front_frames"]
        omissions = []
        mismatches = []
        if len(sf) == len(gf) + 1:
            for skip in range(len(sf)):
                rest = sf[:skip] + sf[skip + 1:]
                if all(a["frame_index"] in b["exact_trimmed_rgb_matches"] for a, b in zip(rest, gf)):
                    omissions.append({"sequence_step_zero_based": skip, **sf[skip]})
        elif len(sf) == len(gf):
            for step, (a, b) in enumerate(zip(sf, gf)):
                if a["frame_index"] not in b["exact_trimmed_rgb_matches"]:
                    mismatches.append({"sequence_step_zero_based": step, "source_frame": a, "gif_frame": b["gif_frame"], "gif_exact_other_client_frames": b["exact_trimmed_rgb_matches"]})
        if classification.startswith("SOURCE_") and len(omissions) != 1:
            raise ValueError("expected unique single omission")
        if classification == "ONE_DIFFERENT_FRAME" and len(mismatches) != 1:
            raise ValueError("expected single differing frame")
        discrepancies.append({
            "record_id": "MS-GIF-DIFFERENCE-" + str(effect_id).zfill(3),
            "binding_ids": ["BND-023", "BND-025"],
            "requirement_ids": ["RQ-087", "RQ-088", "RQ-096"],
            "guide_source_id": source_id,
            "guide_sha256": row["guide_sha256"],
            "guide_url": row["guide_url"],
            "actual_archive_capture": row["actual_archive_capture"],
            "effect_sequence_id": seq["id"],
            "effect_source": seq["source"],
            "classification": classification,
            "guide_nonblank_frames": len(gf),
            "client_front_frames": len(sf),
            "client_back_frames_not_proven_by_guide": len(seq["back_frames"]),
            "unique_omitted_front_steps": omissions,
            "different_steps": mismatches,
            "named_rows": row["guide_skill_rows"],
            "selected_for_build": False,
            "source_sequence_modified": False,
            "fact_scope": "Previously unresolved exact frame candidates explain the precise discrepancy. A partial layer/subsequence is not full sequence identification.",
            "codex_observation": "Compare original client sequence with this guide at the flagged step; preserve both editions. Do not remove/replace frames or infer audio/hit timing from the GIF.",
            "runtime_test": "NOT_RUN",
        })
    save(output / "gif_timing_evidence.json", {"schema": "baram-work-motion-metadata-v1", "input_sha256": EXPECTED, "records": evidence})
    save(output / "gif_sequence_discrepancies.json", {"schema": "baram-work-motion-differences-v1", "input_sha256": EXPECTED, "records": discrepancies})
    counts = {"new_downloads": 0, "new_client_decodes": 0, "unique_existing_GIFs_new_timing_analysis": len(evidence), "aligned_nonblank_frame_pairs": sum(len(r["aligned_nonblank_timing_pairs"]) for r in evidence), "nonconstant_numerical_scale_GIFs": sum(not r["constant_numerical_scale_across_all_nonblank_frames"] for r in evidence), "precise_unresolved_sequence_discrepancies": len(discrepancies), "new_full_sequence_identifications": 0, "KR_sound_bindings_confirmed": 0, "runtime_tests": "NOT_RUN"}
    save(output / "summary.json", counts)
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--package", required=True)
    p.add_argument("--output", required=True)
    main(p.parse_args())
