#!/usr/bin/env python3
"""Bind acquired guide-matched native effect pixels without inventing old timing."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    if isinstance(value, Path):
        value = value.read_bytes()
    elif not isinstance(value, bytes):
        value = canonical(value).encode()
    return hashlib.sha256(value).hexdigest()


def name_key(name):
    return "".join((name or "").split())


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def select_binding(skill, rows, core_by_id):
    """Prefer a matched exact source row, then a unique same-name/job/guardian."""
    eligible = [row for row in rows
                if row.get("fact_status") == "CORROBORATED_RECONSTRUCTION"
                and row.get("original_value", {}).get("matched_full_sequence_count") == 1
                and str(row["original_value"].get("effect_sequence_id", "")).startswith("KR491:effect_sequence:")]
    direct = [row for row in eligible if row["original_value"].get("guide_row_id") == skill["id"]]
    candidates, method = direct, "DIRECT_GUIDE_ROW_COMPLETE_RGB_MATCH"
    if not candidates:
        source = skill.get("source_value") or {}
        candidates = []
        for row in eligible:
            value = row["original_value"]
            parent = core_by_id.get(value.get("guide_row_id"), {})
            parent_value = parent.get("selected_original_value") or parent.get("original_value") or {}
            if (name_key(value.get("entity_name_ko")) == name_key(skill.get("name"))
                    and parent_value.get("job") == source.get("job")
                    and parent_value.get("guardian") == source.get("guardian")):
                candidates.append(row)
        method = "SAME_NORMALIZED_NAME_JOB_GUARDIAN_COMPLETE_RGB_MATCH"
    sequences = {row["original_value"]["effect_sequence_id"] for row in candidates}
    if len(sequences) != 1:
        return None, "AMBIGUOUS_MATCH_RECONSTRUCTED_FALLBACK" if sequences else "NO_COMPLETE_RGB_MATCH_RECONSTRUCTED_FALLBACK"
    return sorted(candidates, key=lambda row: row["id"])[0], method


def safe_relative(path):
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Unsafe effect asset path: " + str(path))
    return relative


def bind_effect_assets(data, normalized, priority, output):
    """Mutate skill effect bindings and merge copied native definitions in output.

    Runtime source indexes keep their original IDs (including gaps). Source
    offsets/delays are retained as inspection metadata, not historical truth.
    """
    normalized, priority, output = Path(normalized), Path(priority), Path(output)
    guide_path = normalized / "kr_asset_guide_effects.jsonl"
    core_path = normalized / "kr_official_core.jsonl"
    guide = read_rows(guide_path)
    core = {row["content_id"]: row for row in read_rows(core_path)}
    source_index_path = priority / "kr491" / "kr491_runtime.json"
    target_index_path = output / "kr491" / "kr491_runtime.json"
    source_index = json.loads(source_index_path.read_text())
    target_index = json.loads(target_index_path.read_text())
    source_effects = {int(row["id"]): row for row in source_index["effects"]}
    effects = {int(row["id"]): row for row in target_index["effects"]}
    selected, records, copied = set(), [], {}
    for iid, skill in sorted(data["skills"].items()):
        match, method = select_binding(skill, guide, core)
        previous = skill.get("effect_id")
        if match:
            original = match["original_value"]
            effect_id = int(original["effect_sequence_id"].rsplit(":", 1)[1])
            if effect_id not in source_effects:
                raise ValueError("Matched native effect definition missing: " + str(effect_id))
            effect = source_effects[effect_id]
            frames = [frame for key in ("front_frames", "back_frames") for frame in effect.get(key, [])
                      if isinstance(frame.get("image"), dict) and frame["image"].get("path")]
            if not frames:
                raise ValueError("Corroborated effect has no acquired native frames: " + str(effect_id))
            for frame in frames:
                image = frame["image"]
                relative = safe_relative(image["path"])
                source, target = priority / "kr491" / relative, output / "kr491" / relative
                if not source.is_file():
                    raise ValueError("Acquired native effect frame missing: " + str(source))
                source_sha = digest(source)
                if source_sha != image["sha256"]:
                    raise ValueError("Native effect frame checksum mismatch: " + str(source))
                if not target.is_file() or digest(target) != source_sha:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                if digest(target) != source_sha:
                    raise ValueError("Copied native effect frame checksum mismatch: " + str(target))
                copied[str(relative)] = source_sha
            effects[effect_id] = deepcopy(effect)
            selected.add(effect_id)
            skill["effect_id"] = effect_id
            binding = {"content_id": iid, "field": "effect_id", "source_tier": "LEGACY_RECONSTRUCTED",
                       "source_ref": match["id"], "source_record_sha256": digest(match),
                       "observed_version": "KR491_NATIVE_EFFECT_PIXELS_WITH_ARCHIVED_KOREAN_GUIDE_CORROBORATION",
                       "observed_date": "2026-10-17", "selected_value": effect_id,
                       "action_type": "native_effect_animation", "dependencies": [original["effect_sequence_id"]],
                       "runtime_ref": "skills." + iid + ".effect_id", "method": method,
                       "guide_row_id": original["guide_row_id"], "guide_image_source_id": original["guide_image_source_id"],
                       "guide_image_sha256": original["guide_image_sha256"],
                       "evidence": "Complete ordered nonblank RGB image identity, one matched native sequence",
                       "rationale": "Reuse acquired named effect pixels; placement, impact timing, delay units and audio remain reconstructed",
                       "previous_reconstructed_effect_id": previous, "status": "BOUND_BYTES_HASH_VERIFIED_RUNTIME_TEST_NOT_RUN"}
        else:
            if previous is None or int(previous) not in effects:
                raise ValueError("Reconstructed fallback references unavailable effect: " + str(iid))
            binding = {"content_id": iid, "field": "effect_id", "source_tier": "LEGACY_RECONSTRUCTED",
                       "source_ref": "kr_asset_guide_effects.jsonl", "observed_version": "KR491_WITH_G1_RECONSTRUCTED_BINDING",
                       "observed_date": "2026-10-17", "selected_value": int(previous),
                       "action_type": "native_effect_animation", "dependencies": ["KR491:effect_sequence:" + str(previous)],
                       "runtime_ref": "skills." + iid + ".effect_id", "method": method,
                       "rationale": "No unique complete named RGB identity; retain explicit reconstructed family effect",
                       "evidence": "Normalized guide comparison performed; no exact usable match selected",
                       "status": "RECONSTRUCTED_FALLBACK_RUNTIME_TEST_NOT_RUN"}
        skill["effect_asset_binding"] = binding
        skill.setdefault("effective_field_status", {})["effect_id"] = "LEGACY_RECONSTRUCTED"
        records.append(binding)
    target_index["effects"] = [effects[eid] for eid in sorted(effects)]
    target_index.setdefault("g1_adoption", {})["guide_effect_assets"] = {
        "source_guide_sha256": digest(guide_path), "source_index_sha256": digest(source_index_path),
        "selected_native_effect_ids": sorted(selected), "timing_placement_audio_historical_match": "NOT_ESTABLISHED"}
    target_index_path.write_text(json.dumps(target_index, ensure_ascii=False, indent=2) + "\n")
    return {"schema": "baram.g1.guide-effect-adoption/1", "source_guide_sha256": digest(guide_path),
            "source_core_sha256": digest(core_path), "source_index_sha256": digest(source_index_path),
            "output_index_sha256": digest(target_index_path), "source_guide_rows": len(guide),
            "source_complete_match_rows": sum(row.get("original_value", {}).get("matched_full_sequence_count") == 1 for row in guide),
            "skills": len(records), "binding_methods": dict(Counter(row["method"] for row in records)),
            "selected_native_effect_ids": sorted(selected), "runtime_native_effect_ids": sorted(effects),
            "copied_or_verified_pngs": len(copied), "copied_frame_sha256": copied,
            "bindings": records, "runtime_test": "NOT_RUN", "historical_timing_audio_claim": False}


def self_test():
    def row(iid, parent, name, seq, count=1):
        return {"id": iid, "fact_status": "CORROBORATED_RECONSTRUCTION", "original_value": {
            "guide_row_id": parent, "entity_name_ko": name, "matched_full_sequence_count": count,
            "effect_sequence_id": "KR491:effect_sequence:" + str(seq)}}
    core = {"old": {"selected_original_value": {"job": "전사"}},
            "wrong": {"selected_original_value": {"job": "도사"}}}
    skill = {"id": "new", "name": "진백호령", "source_value": {"job": "전사"}}
    matched, method = select_binding(skill, [row("a", "old", "진백 호령", 56)], core)
    assert matched["original_value"]["effect_sequence_id"] == "KR491:effect_sequence:56"
    assert method.startswith("SAME_NORMALIZED_NAME_JOB_GUARDIAN")
    assert select_binding(skill, [row("a", "wrong", "진백호령", 56)], core)[0] is None
    assert select_binding(skill, [row("a", "old", "진백호령", 56, 0)], core)[0] is None
    assert select_binding(skill, [row("a", "old", "진백호령", 56), row("b", "old", "진백호령", 57)], core)[0] is None
    assert select_binding(skill, [row("a", "new", "진백호령", 56)], core)[1].startswith("DIRECT_GUIDE_ROW")
    try:
        safe_relative("../escape.png")
    except ValueError:
        pass
    else:
        raise AssertionError("Traversal path accepted")
    print(canonical({"status": "PASS", "assertions": 7, "scope": "effect identity selection, ambiguity, job isolation, missing match and path safety", "game_tests": 0}))


if __name__ == "__main__":
    self_test()
