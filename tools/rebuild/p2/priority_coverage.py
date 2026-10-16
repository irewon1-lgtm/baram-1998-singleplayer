"""Recount P2 known-corpus coverage without converting source counts into completion.

The frozen baseline uses git objects plus the untouched GEN003 generation.  The
after measurement uses an independently named runtime, the selection ledger and
explicit observation receipts.  Source facts, active selections, bindings and
observations have different denominators throughout this report.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

FACTS = {"ORIGINAL_VERIFIED", "CORROBORATED", "RECONSTRUCTED", "BALANCE_ESTIMATE", "UNKNOWN", "CONFLICT"}
USES = ["DISCOVERED", "ACQUIRED", "DECODED", "IDENTIFIED", "SELECTED", "BOUND", "EXERCISED"]
AREAS = {
    "A": "NPC 외형", "B": "NPC 대화·퀘스트", "C": "몬스터·스폰·드롭",
    "D": "조합·업그레이드·수리", "E": "직업·기술·성장·경제", "F": "모션·합성",
    "G": "효과·음향·타격 시점", "H": "한국 지도·출구·귀환", "I": "로그인·생성·UI", "J": "저장·업데이트·환경",
}
CATEGORY_AREA = {"START": "I", "UI": "I", "WORLD": "H", "AV": "G", "GROWTH": "E", "LIFE": "E", "SAVE": "J", "OPS": "J", "COMBAT": "C", "CRAFT": "D", "DIALOGUE": "B", "DROP": "C", "MOTION": "F", "AUDIO": "G", "NPC": "A", "SPAWN": "C"}
AREA_TABLES = {
    "A": ["kr_official_services", "kr_official_npc_appearance"], "B": ["kr_documented_fields"],
    "C": ["kr_official_core"], "D": ["kr_official_crafting_facts", "kr_official_services"],
    "E": ["kr_official_core", "kr_official_items", "kr_official_skill_effects", "kr_official_flow", "kr_official_services"],
    "F": ["kr_asset_parts", "kr_asset_draw_order", "kr_asset_monster_groups"],
    "G": ["kr_asset_effect_sequences", "kr_asset_sound_metadata", "kr_asset_guide_effects"],
    "H": ["kr_official_full_maps", "kr_official_services"],
    "I": ["kr_official_flow", "kr_official_creation_visual", "kr_official_image_bindings", "kr_asset_ui_strings"], "J": [],
}
NEXT = {
    "A": ("KR491 Monster.epf/MonsFrm.tbl + kr_official_npc_appearance.jsonl의 KRO-NPCLOOK-*4개 화면; NPC 이름별 원본 look/좌표", "NPC별 화면 crop과 부품/프레임을 대응하고 원본 look 미상은 개별 재구성으로 격리", "P2-02", "Work: NPC 바인딩"),
    "B": ("1998~2001 한국 길드/주막/대장간의 실제 대화창·선택지 화면 및 실패/거절/재방문 원문", "공식 서비스 설명과 실제 발화를 분리; 기존 한국어 재구성4개를 별도 대화 계약으로 연결", "P2 계약/P3 대화", "Work: 대화 자료"),
    "C": ("kr_official_core.jsonl monster행 + 한국 서버/영상의 층별 리스폰·수량·AI·독립/배타 드롭 규칙", "명시 XP/아이템 관계만 선택하고 미관측 확률은 UNKNOWN; nativeID와 변종을 독립 대응", "P2 계약/P3 전투", "Work: 전투 데이터"),
    "D": ("kr_official_crafting_facts.jsonl KRO-CRAFTING_FACT-*; 해당 NPC 수리 가격·실패 소모·성공률 화면", "원문 재료/결과만 채택; 성공률·수리공식의 근거 없는 기본값 금지", "P2 계약/P3 제작", "Work: 경제 데이터"),
    "E": ("KR_GUIDE_2001_SNAPSHOT 공식 기술/아이템/서비스 표; 전체 경험치곡선·상점별 양방향 가격·기술 지속/중첩", "현재 선택 프로필의 개별 학습 조건을 소비하고 서버 의미 공백은 별도 동작 계약으로 전달", "P2 계약/P3 규칙", "Work: 규칙 통합"),
    "F": ("KR491 DrwOrder.tbl/Body.tbl/MonsFrm.tbl + 같은 행동의 한국 당시 영상 프레임·시간", "네 방향/무기 합성의 추론과 원본 시간 단위를 분리; 마스크3개 최소 실패 샘플 해독", "P2-02", "Work: 합성/파서"),
    "G": ("Effect.tbl 음수 Frame#/Repeat/Alpha/Light 명령 + 기술별 한국 실행 영상/녹음의 soundID·명중·재행동 시간", "안전한 한정 미리보기와 원본 효과 의미를 분리; WAV ID 전수 참조 뒤 실제 출력 관측", "P2-03", "Work: 효과/음향"),
    "H": ("KR1.25 0.map..218 inventory + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍", "복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사", "P2-01", "Work: 지도 해독"),
    "I": ("DLGLOGIN/DLGNEW01/DLGPASS mask; 2001 생성GIF KRO-CREATE-VIS-20010607 + Windows/Android 실제 IME", "원본 bitmap, 로컬 생성 흐름, 실인증을 나누고 오류/취소/한글조합을 실제 실행", "P2-04", "Work: 생성/UI"),
    "J": ("동일 새 입력의 native Windows 로그·Android ActivityManager/graphics 로그·Galaxy 실기기·무료 시험인증 endpoint", "기존 save_self_test.gd 안전시험 유지; 플랫폼별 보고서·checksum·오류 원인으로만 상태 갱신", "P2-05/06", "Work: 플랫폼/저장"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_bytes(repo: Path, ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=repo)


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def fact(value: str) -> str:
    return {"CORROBORATED_RECONSTRUCTION": "CORROBORATED", "INFERRED": "RECONSTRUCTED"}.get(value, value if value in FACTS else "UNKNOWN")


def area_of(row: dict) -> str:
    if row.get("area") in AREAS:
        return row["area"]
    text = str(row.get("field_id", "")) + " " + str(row.get("field_path", "")) + " " + str(row.get("content_id", ""))
    text = text.lower()
    if "npc" in text or "service" in text:
        return "A"
    if "dialog" in text:
        return "B"
    if "monster" in text or "drop" in text or "spawn" in text:
        return "C"
    if "craft" in text or "repair" in text:
        return "D"
    if "icon" in text or "creation" in text or "ui." in text:
        return "I"
    if "map" in text or "exit" in text:
        return "H"
    if "sound" in text or "wav" in text or "effect" in text or "fx-" in text:
        return "G"
    if "motion" in text or "mask" in text or "frame" in text:
        return "F"
    if "save" in text or "platform" in text or "android" in text:
        return "J"
    return "E"


def baseline_inputs(repo: Path, ref: str) -> dict:
    paths = ["docs/rebuild/p1_5/requirements_delta.csv", "docs/rebuild/p1_5/gaps_by_feature.csv", "docs/rebuild/p1_5/field_bindings.jsonl", "docs/rebuild/p2-work/SOURCE_USAGE.jsonl", "docs/rebuild/p2-work/BATCH_ADOPTION.jsonl", "docs/rebuild/p1_5/research_official_core.json", "docs/rebuild/p1_5/official_independent_review.json", "docs/rebuild/p2-work/evidence/LINUX_GEN003.json"]
    raw = {p: git_bytes(repo, ref, p) for p in paths}
    return {"bytes": raw, "fingerprints": {p: hashlib.sha256(b).hexdigest() for p, b in raw.items()}}


def corpus_summary(normalized: Path) -> dict:
    tables, counts, selected, profiles, reconstructed = {}, collections.Counter(), [], collections.Counter(), []
    for path in sorted(normalized.glob("*.jsonl")):
        rows = jsonl(path)
        tables[path.stem] = rows
        counts[path.name] = len(rows)
        for row in rows:
            rid = row.get("content_id", row.get("id"))
            if row.get("selected_original_value") is not None:
                selected.append(rid)
                profiles[row.get("build_profile_id") or "UNPROFILED"] += 1
            if row.get("reconstructed_value") is not None:
                reconstructed.append(rid)
    contracts = load(normalized / "save_contracts.json").get("contracts", [])
    return {"tables": tables, "summary": {"jsonl_rows": sum(counts.values()), "save_contracts": len(contracts), "combined_normalized_rows": sum(counts.values()) + len(contracts), "table_rows": dict(counts), "file_sha256": {p.name: sha(p) for p in sorted(normalized.glob("*.json*"))}, "source_profile_selected_original_records": len(selected), "source_profile_selected_by_profile": dict(profiles), "source_profile_selected_ids": selected, "reconstructed_candidate_records": len(reconstructed), "reconstructed_candidate_ids": reconstructed, "active_runtime_records_are_not_inferred_from_source_selection": True}}


def asset_universes(runtime: Path, inputs: dict, normalized: Path, observations: dict) -> dict:
    assets, maps = load(runtime / "kr491/kr491_runtime.json"), load(runtime / "maps/index.json")
    obs = observations.get("assets", {})
    effect_obs, sound_obs, map_obs, icon_obs = [set(str(x) for x in obs.get(k, [])) for k in ["effect_ids_exercised", "sound_ids_exercised", "map_ids_exercised", "icon_ids_exercised"]]
    selected_maps = {str(x["native_id"]) for x in maps["maps"]}
    map_records = [{"content_id": f"KR125:map:{x['native_id']}", "native_id": x["native_id"], "fact_status": "UNKNOWN", "use_status": "EXERCISED" if str(x["native_id"]) in map_obs else "BOUND" if str(x["native_id"]) in selected_maps else "DECODED" if x.get("status") in {"PASS", "STRUCTURE_AND_REFERENCES_VALID", "STORAGE_REFERENCES_VALID"} else "ACQUIRED", "test_status": "PASS" if str(x["native_id"]) in map_obs else "NOT_RUN", "source_status": x.get("status", "UNKNOWN"), "reason": x.get("reason", ""), "historical_city": "UNKNOWN"} for x in maps["map_inventory"]]
    effect_records = []
    for x in assets["effects"]:
        selected = bool(x.get("preview_supported", x.get("safe_preview_supported", x.get("safe_slideshow", False))))
        if "inspection_status" in x:
            selected = x["inspection_status"] in ["SAFE_SLIDESHOW_ONLY", "SAFE_RECONSTRUCTED_PREVIEW", "SUPPORTED_SAFE_PREVIEW"]
        selected = selected or bool(x.get("safe_reconstructed_preview"))
        preview = x.get("priority_preview", {})
        if preview:
            selected = bool(preview.get("available"))
        has_frames = bool(x.get("front_frames") or x.get("back_frames"))
        effect_records.append({"content_id": x.get("source_id", f"KR491:effect_sequence:{x['id']}"), "native_id": x["id"], "fact_status": "RECONSTRUCTED" if selected else "UNKNOWN", "use_status": "EXERCISED" if str(x["id"]) in effect_obs else "BOUND" if selected else "DECODED", "test_status": "PASS" if str(x["id"]) in effect_obs else "NOT_RUN", "safe_preview_selected": selected, "nonempty_source_frames": has_frames, "whole_preview_available": preview.get("whole_sequence_available", selected and has_frames), "fragment_only": bool(preview.get("available") and not preview.get("whole_sequence_available")), "reason": preview.get("classification", x.get("inspection_status", x.get("blocked_reasons", x.get("unsupported_commands", [])))), "original_command_semantics_complete": False})
    # GEN003 reused the map/effect selection ordinal for sound; its largest
    # selector had25 entries. Metadata presence did not make all163 IDs reachable.
    dedicated_sound_selector = (runtime / "priority_index.json").is_file()
    sound_reachable = len(assets["sounds"]) if dedicated_sound_selector else sum(x.get("preview_supported", False) for x in assets["effects"])
    sound_records = [{"content_id": x["source_id"], "native_id": x["member"].removesuffix(".wav"), "fact_status": "ORIGINAL_VERIFIED", "fact_scope": "KR491 resource bytes/metadata, not target-era skill invocation", "use_status": "EXERCISED" if x["source_id"] in sound_obs or x["member"].removesuffix(".wav") in sound_obs else "BOUND" if index < sound_reachable else "DECODED", "ui_selectable": index < sound_reachable, "test_status": "PASS" if x["source_id"] in sound_obs or x["member"].removesuffix(".wav") in sound_obs else "NOT_RUN", "skill_sound_identity": "UNKNOWN"} for index, x in enumerate(assets["sounds"])]
    icons = jsonl(normalized / "kr_official_image_bindings.jsonl")
    runtime_icons = load(runtime / "icons/icons.json").get("entries", []) if (runtime / "icons/icons.json").is_file() else assets.get("official_icons", assets.get("item_icons", []))
    bound_icons = {str(x.get("content_id", x.get("id"))) for x in runtime_icons}
    icon_states = {str(x.get("content_id", x.get("id"))): x for x in runtime_icons}
    # Other overlay layouts can declare exact binding IDs in the observation receipt.
    bound_icons |= set(str(x) for x in obs.get("icon_ids_bound", []))
    icon_records = [{"content_id": x["content_id"], "fact_status": icon_states.get(x["content_id"], {}).get("fact_status", "ORIGINAL_VERIFIED"), "source_binding_fact_status": "ORIGINAL_VERIFIED", "working_profile_eligible": icon_states.get(x["content_id"], {}).get("working_profile_eligible", False), "fact_scope": "official name-to-document-image relation; after cross-year matching is CORROBORATED; original EPF ID remains unknown", "use_status": "EXERCISED" if x["content_id"] in icon_obs else "BOUND" if x["content_id"] in bound_icons else "SELECTED", "test_status": "PASS" if x["content_id"] in icon_obs else "NOT_RUN", "original_epf_id": None} for x in icons]
    adoption = [json.loads(x) for x in inputs["bytes"]["docs/rebuild/p2-work/BATCH_ADOPTION.jsonl"].decode().splitlines() if x.strip()]
    candidates = {x["candidate_id"]: x for x in adoption if x.get("candidate_id")}
    result = {}
    for key, rows in [("kr_maps", map_records), ("effects", effect_records), ("wav_ids", sound_records), ("official_icon_bindings", icon_records)]:
        for row in rows:
            row["remaining_category"] = "지금 사용가능" if row["use_status"] in {"BOUND", "EXERCISED"} else "안전상 차단" if row.get("source_status", "").startswith("BLOCKED") else "자료는 있지만 기술 수정 필요"
        result[key] = {"known_denominator": len(rows), "global_target_denominator": "UNKNOWN", "use_status_counts": dict(collections.Counter(x["use_status"] for x in rows)), "records": rows}
    result["effects"]["preview_scope_counts"] = {"eligible_including_empty": sum(x["safe_preview_selected"] for x in effect_records), "nonempty_selected": sum(x["safe_preview_selected"] and x["nonempty_source_frames"] for x in effect_records), "whole_nonempty": sum(x["whole_preview_available"] for x in effect_records), "fragment_only": sum(x["fragment_only"] for x in effect_records)}
    working_items = [x for x in jsonl(normalized / "kr_official_items.jsonl") if x.get("build_profile_id") == "KR_GUIDE_2001_SNAPSHOT"]
    items_with_icons = {x.get("item_id") for x in runtime_icons if x.get("working_profile_eligible")}
    result["working2001_item_image_gaps"] = {"known_item_rows": len(working_items), "item_rows_with_bound_named_image": len(items_with_icons), "remaining_count": sum(x["content_id"] not in items_with_icons for x in working_items), "global_target_denominator": "UNKNOWN", "records": [{"content_id": x["content_id"], "name_ko": x["entity_name_ko"], "source_ids": x["source_ids"], "source_pointer": x["source_locator"], "required": "Exact official image_links bytes; no shared fallback", "cause_code": "ACCESS_BLOCKED", "cause_scope": "existing image not acquired/eligible match absent; per-link access must be checked before claiming permanent source absence"} for x in working_items if x["content_id"] not in items_with_icons]}
    chunk_obs = set(str(x) for x in obs.get("map_inspection_ids_exercised", []))
    chunk_rows = [{"content_id": "KR125:storage_chunk:" + str(x.get("inspection_id", x["native_id"])), "native_map_id": x["native_id"], "inspection_id": x.get("inspection_id", x["native_id"]), "chunk_index": x.get("storage_chunk_index", 0), "use_status": "EXERCISED" if str(x.get("inspection_id", x["native_id"])) in chunk_obs or (not x.get("inspection_id") and str(x["native_id"]) in map_obs) else "BOUND"} for x in maps["maps"]]
    result["map_storage_chunks"] = {"known_denominator": len(chunk_rows), "global_target_denominator": "UNKNOWN", "use_status_counts": dict(collections.Counter(x["use_status"] for x in chunk_rows)), "records": chunk_rows, "scope": "isolated64x64 disk chunks; never count as separate historical maps/cities"}
    result["work_candidates"] = {"known_denominator": len(candidates), "global_target_denominator": "NOT_APPLICABLE", "counting_rule": "unique candidate_id only; event/receipt rows excluded", "ids": sorted(candidates), "guard_ids": sorted(k for k, v in candidates.items() if v.get("P2_selection") == "INSPECTION_GUARD"), "historical_feature_completion": 0}
    core = json.loads(inputs["bytes"]["docs/rebuild/p1_5/research_official_core.json"])
    review = json.loads(inputs["bytes"]["docs/rebuild/p1_5/official_independent_review.json"])
    conflicts = review["cross_era_conflicts"]
    result["cross_era_conflicts"] = {"known_denominator": len(conflicts), "scope": "independent review: both-epoch explicit skill material/money differences", "additional_epoch_differences": len(core["epoch_conflicts"]), "additional_scope": "all published region/XP/item/ingredient/money differences; not15 equivalent conflicts", "records": conflicts}
    return result


def cause_for(area: str, target: str) -> tuple[str, str]:
    if area == "J" and target in {"windows", "actual_galaxy", "auth_environment_access", "same_account_roundtrip"}:
        return "ENVIRONMENT_BLOCKED", "기기·인증 환경 차단"
    if area == "J" and target == "android":
        return "RUNTIME_ERROR", "자료는 있지만 기술 수정 필요"
    if area == "B" or (area == "C" and target in {"hp_stats", "respawn_delay", "spawn_area_count_cap", "probability_model", "ownership_despawn"}) or (area == "D" and target in {"success_rate", "failure_loss_or_keep", "repair_price"}) or (area == "H" and target in {"exits", "return_by_country_direction", "npc_spawns"}):
        return "SOURCE_MISSING", "추가 원문 탐색 필요"
    if (area == "A" and target in {"native_id", "body_head_clothes_weapon", "motion_layer", "coordinate"}) or (area == "H" and target in {"era_city", "coordinate_origin", "four_gates", "hunting_entrances", "collision_occlusion"}) or (area == "G" and target == "sound_id"):
        return "IDENTITY_UNKNOWN", "자료는 있지만 기술 수정 필요"
    if (area == "G" and target in {"repeat_alpha_light", "layer_position"}) or (area == "F" and target == "delay_raw_unit"):
        return "DECODE_FAILED", "자료는 있지만 기술 수정 필요"
    if (area == "G" and target in {"impact", "next_action_time", "latency_uncertainty", "actual_audio_output"}) or (area == "I" and target == "IME"):
        return "BOUND_NOT_EXERCISED", "자료는 있지만 기술 수정 필요"
    return "SELECTED_NOT_BOUND", "자료는 있지만 기술 수정 필요"


def make_coverage(args: argparse.Namespace) -> dict:
    inputs = baseline_inputs(args.repo, args.baseline_ref)
    gaps = list(csv.DictReader(io.StringIO(inputs["bytes"]["docs/rebuild/p1_5/gaps_by_feature.csv"].decode("utf-8-sig"))))
    reqs = list(csv.DictReader(io.StringIO(inputs["bytes"]["docs/rebuild/p1_5/requirements_delta.csv"].decode("utf-8-sig"))))
    bindings = [json.loads(x) for x in inputs["bytes"]["docs/rebuild/p1_5/field_bindings.jsonl"].decode().splitlines() if x.strip()]
    corpus = corpus_summary(args.normalized)
    observations = load(args.observations) if args.observations else {}
    if args.mode == "BASELINE" and not args.observations:
        # Reuse the unchanged GEN003 receipt only for its exact documented scope.
        # The original runtime ZIP/manifest hashes are verified by the receiver.
        observed_subset_fields = {
            "F": ["direction_order", "frame_start_end", "origin_offset", "palette", "front_back_layer", "body_weapon_alignment", "existent_action_set"],
            "G": ["sequence_frames", "actual_audio_output"], "H": ["dimensions", "tiles_objects", "collision_occlusion"],
            "I": ["background_buttons", "equipped_appearance"],
            "J": ["schema", "payload_integrity", "owner_stable_id_bounds", "atomic_backup_recovery", "coordinate_validity", "explicit_migration", "preserve_on_failure"],
        }
        observations = {"assets": {"effect_ids_exercised": [0], "sound_ids_exercised": ["001"], "map_ids_exercised": [1, 99, 100]}, "fields": {f"GAP-{area}-{field}": {"use_status": "EXERCISED", "test_status": "PASS", "evidence": "docs/rebuild/p2-work/evidence/LINUX_GEN003.json", "scope": "historical Linux subset; unknown target era/all-population/cross-platform semantics retained"} for area, names in observed_subset_fields.items() for field in names}, "receipt": "docs/rebuild/p2-work/evidence/LINUX_GEN003.json", "historical_evidence_reuse": True}
    selections = jsonl(args.selections) if args.selections else []
    selection_keys = []
    for row in selections:
        if not row.get("field_id") or not row.get("content_id"):
            raise ValueError("Selection requires exact field_id and content_id")
        if row.get("runtime_status", "SELECTED") not in USES:
            raise ValueError("Invalid independent use status: " + str(row.get("runtime_status")))
        selection_keys.append((row["field_id"], row["content_id"]))
    if len(set(selection_keys)) != len(selection_keys):
        raise ValueError("Duplicate field/content selection key would inflate counts")
    universes = asset_universes(args.runtime, inputs, args.normalized, observations)
    active = collections.Counter(fact(x.get("fact_status", "UNKNOWN")) for x in selections)
    active_use = collections.Counter(x.get("runtime_status", "SELECTED") for x in selections)
    fields = []
    for old in gaps:
        area, target = old["area"], old["target_field"]
        fid = f"GAP-{area}-{target}"
        bnds = old["binding_ids"].split("|")
        rq_ids = sorted({rid for x in bindings if x["binding_id"] in bnds for rid in x.get("requirement_ids", [])})
        selected = [x for x in selections if fid in x.get("gap_ids", []) or (area_of(x) == area and target in str(x.get("field_id", "")))]
        cause, bucket = cause_for(area, target)
        evidence, next_action, phase, owner = NEXT[area]
        state = "SELECTED" if selected else "IDENTIFIED"
        test = "NOT_RUN"
        if selected and any(x.get("runtime_status") == "EXERCISED" for x in selected):
            state, test = "EXERCISED", "PASS"
        elif selected and any(x.get("runtime_status") == "BOUND" for x in selected):
            state = "BOUND"
        field_observation = observations.get("fields", {}).get(fid, {})
        if field_observation:
            state = field_observation.get("use_status", state)
            test = field_observation.get("test_status", test)
        if area == "J" and target == "android":
            test = "FAIL"
        elif cause == "ENVIRONMENT_BLOCKED":
            test = "BLOCKED"
        fields.append({"field_id": fid, "area": area, "feature": old["feature"], "target_field": target, "requirement_ids": rq_ids, "binding_ids": bnds, "fact_status": "UNKNOWN", "use_status": state, "test_status": test, "test_scope": "supporting subset only; entire historical field is not complete", "known_scope_complete": False, "global_target_denominator": "UNKNOWN", "known_entity_scope": old["known_entity_scope"], "cause_code": cause, "remaining_category": bucket, "information_missing": old["next_action"], "supporting_selection_ids": [x["field_id"] for x in selected], "supporting_selection_fact_counts": dict(collections.Counter(fact(x.get("fact_status", "UNKNOWN")) for x in selected)), "source_tiers_attempted": "1: KR official source/client existing corpus;2/3: existing P1.5 research;4: fixed P1998/RTK tools; no new search claimed", "next_specific_material": evidence + "; field=" + target, "next_action": next_action + "; " + old["next_action"], "substitution_allowed": "YES_RECONSTRUCTED_EXCEPT_TECHNICAL_SAFETY", "risk": "HIGH" if area in {"H", "J"} or target in {"probability_model", "success_rate", "delay_raw_unit", "impact"} else "MEDIUM", "next_owner": owner, "implementation_stage": phase, "observation": field_observation})
    areas = {}
    for area, label in AREAS.items():
        rows = [x for x in fields if x["area"] == area]
        ss = [x for x in selections if area_of(x) == area]
        areas[area] = {"label": label, "gap_field_types": len(rows), "global_entity_population": "UNKNOWN", "unresolved_gap_field_types": len(rows), "active_selection_records": len(ss), "active_fact_counts": dict(collections.Counter(fact(x.get("fact_status", "UNKNOWN")) for x in ss)), "active_use_counts": dict(collections.Counter(x.get("runtime_status", "SELECTED") for x in ss)), "cause_counts": dict(collections.Counter(x["cause_code"] for x in rows)), "field_ids": [x["field_id"] for x in rows], "source_tables": AREA_TABLES[area]}
    historical = {
        "android_gen003": {"status": "FAIL_NO_REPORT", "evidence": "docs/rebuild/p2-work/evidence/ANDROID_GEN003.json", "updated_by_this_data_selection": False},
        "native_windows": {"status": "BLOCKED_ENVIRONMENT_BRANCH_RULE", "evidence": "docs/rebuild/p2-work/platform/WINDOWS_NATIVE_BLOCKER.json", "updated_by_this_data_selection": False},
        "wine_save": {"status": "FAIL", "failed_checks": 12, "evidence": "docs/rebuild/p2/WINE_STORAGE_DIAGNOSIS.json#latest_v4_result", "updated_by_this_data_selection": False},
        "kr491_masks": {"status": "FAIL", "ids": ["DLGLOGIN", "DLGNEW01", "DLGPASS"], "failed_items": 3, "evidence": "docs/rebuild/p2-work/UI_PALETTE_DIAGNOSIS.json", "updated_by_this_data_selection": False},
        "na_source_references": {"status": "FAIL", "failed_edges": 154, "evidence": "docs/rebuild/p1_5/import_reference_failures.json", "updated_by_this_data_selection": False},
    }
    return {"schema": "baram.priority.coverage/1", "measurement": args.mode, "baseline_ref": args.baseline_ref, "runtime_generation": load(args.runtime / "runtime.json")["generation"], "runtime_manifest_sha256": sha(args.runtime / "runtime.json"), "status": "PARTIAL", "population_contract": {"requirement_ids": len(reqs), "binding_groups": len(bindings), "gap_field_types": len(fields), "original_game_total_entities": "UNKNOWN", "restoration_percentage": "NOT_COMPUTABLE", "A_J_labels": "Preserved from actual P1.5 field ledger; not prose enumeration order", "selections_are_field_records_not_complete_game_entities": True}, "baseline_inputs": inputs["fingerprints"], "source_corpus": corpus["summary"], "active_profile_selection_counts": dict(active), "active_profile_use_counts": dict(active_use), "selected_not_bound": sum(x.get("runtime_status", "SELECTED") == "SELECTED" for x in selections), "bound_not_exercised": sum(x.get("runtime_status") == "BOUND" for x in selections), "areas": areas, "fields": fields, "requirements": [{"requirement_id": x["requirement_id"], "area": CATEGORY_AREA.get(x["category"], "J"), "category": x["category"], "required_behavior": x["canonical_requirement"], "test_status": "NOT_RUN", "scope": "Full requirement not certified by P2 asset inspection", "test_ids": [x["normal_test_id"], x["failure_test_id"], x["cancel_test_id"]]} for x in reqs], "asset_universes": universes, "historical_failures_preserved": historical, "new_observation_receipt": {"path": str(args.observations) if args.observations else None, "sha256": sha(args.observations) if args.observations else None}, "unknowns_are_not_removed": True}


def write_gaps(path: Path, coverage: dict) -> None:
    columns = ["field_id", "area", "feature", "target_field", "requirement_ids", "binding_ids", "fact_status", "use_status", "test_status", "cause_code", "remaining_category", "information_missing", "source_tiers_attempted", "next_specific_material", "next_action", "substitution_allowed", "risk", "next_owner", "implementation_stage"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns)
        writer.writeheader()
        for row in coverage["fields"]:
            writer.writerow({k: "|".join(row[k]) if isinstance(row[k], list) else row[k] for k in columns})
        # Exact exceptional IDs supplement, rather than replace, the137 field types.
        for name, error in coverage["historical_failures_preserved"].items():
            writer.writerow({"field_id": "FAILURE-" + name, "area": "J" if name in {"android_gen003", "native_windows", "wine_save"} else "F" if name == "kr491_masks" else "C", "fact_status": "UNKNOWN", "use_status": "BOUND", "test_status": "BLOCKED" if "BLOCKED" in error["status"] else "FAIL", "cause_code": "ENVIRONMENT_BLOCKED" if "BLOCKED" in error["status"] else "RUNTIME_ERROR" if name != "kr491_masks" else "DECODE_FAILED", "remaining_category": "기기·인증 환경 차단" if "BLOCKED" in error["status"] else "안전상 차단", "information_missing": json.dumps(error, ensure_ascii=False), "next_specific_material": error["evidence"], "next_action": "Use new same-platform evidence; preserve original failed receipt", "risk": "HIGH", "next_owner": "Work", "implementation_stage": "P2"})
        for kind, area in [("kr_maps", "H"), ("effects", "G"), ("wav_ids", "G"), ("official_icon_bindings", "I")]:
            for item in coverage["asset_universes"][kind]["records"]:
                if item["use_status"] == "EXERCISED":
                    continue
                cause = "BOUND_NOT_EXERCISED" if item["use_status"] == "BOUND" else "DECODE_FAILED" if item.get("source_status", "").startswith("BLOCKED") or kind == "effects" else "SELECTED_NOT_BOUND"
                material, action, stage, owner = NEXT[area]
                writer.writerow({"field_id": "ASSET-" + item["content_id"], "area": area, "feature": kind, "fact_status": item["fact_status"], "use_status": item["use_status"], "test_status": item["test_status"], "cause_code": cause, "remaining_category": item["remaining_category"], "information_missing": json.dumps(item.get("reason", "Not individually exercised; global identity/semantic scope remains separate"), ensure_ascii=False), "source_tiers_attempted": "1: existing original bytes + source records;4: fixed parser", "next_specific_material": material + "; exactID=" + item["content_id"], "next_action": action, "substitution_allowed": "YES_RECONSTRUCTED_EXCEPT_TECHNICAL_SAFETY", "risk": "HIGH" if cause == "DECODE_FAILED" else "MEDIUM", "next_owner": owner, "implementation_stage": stage})
        for item in coverage["asset_universes"]["working2001_item_image_gaps"]["records"]:
            writer.writerow({"field_id": "item.icon." + item["content_id"], "area": "I", "feature": "2001 item named image", "fact_status": "UNKNOWN", "use_status": "DISCOVERED", "test_status": "BLOCKED", "cause_code": item["cause_code"], "remaining_category": "추가 원문 탐색 필요", "information_missing": item["cause_scope"], "source_tiers_attempted": "1: existing official document/image corpus", "next_specific_material": "kr_official_items.jsonl:" + item["content_id"] + "; source=" + "|".join(item["source_ids"]) + "; image_links actual archived bytes", "next_action": "Check exact linked image in existing PRIVATE_IMAGE_INDEX first; acquire only missing eligible bytes and preserve every failed response", "substitution_allowed": "NO_SHARED_FALLBACK", "risk": "MEDIUM", "next_owner": "Work: item icons", "implementation_stage": "P2"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--normalized", type=Path, required=True)
    parser.add_argument("--mode", choices=["BASELINE", "AFTER"], required=True)
    parser.add_argument("--selections", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gaps-output", type=Path)
    args = parser.parse_args()
    if args.mode == "BASELINE" and args.selections:
        parser.error("Baseline cannot read a new selection ledger")
    result = make_coverage(args)
    baseline_path = args.repo / "docs/rebuild/priority-fill/BASELINE_COVERAGE.json"
    if args.mode == "AFTER" and baseline_path.is_file():
        before = load(baseline_path)
        old_ids, new_ids = [{x["field_id"] for x in d["fields"]} for d in (before, result)]
        if old_ids != new_ids:
            raise ValueError("Field population changed; missing rows cannot become completion")
        if before["source_corpus"]["file_sha256"] != result["source_corpus"]["file_sha256"]:
            raise ValueError("Original normalized source corpus changed")
        result["comparison"] = {"baseline_coverage_sha256": sha(baseline_path), "same_field_ids": True, "same_original_normalized_bytes": True, "field_types_before": len(old_ids), "field_types_after": len(new_ids), "field_types_fully_closed": 0, "field_population_is_not_restoration_total": True, "assets": {k: {"before": before["asset_universes"][k].get("use_status_counts", {}), "after": result["asset_universes"][k].get("use_status_counts", {})} for k in ["kr_maps", "map_storage_chunks", "effects", "wav_ids", "official_icon_bindings"]}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if args.gaps_output:
        write_gaps(args.gaps_output, result)
    print(json.dumps({"status": result["status"], "mode": args.mode, "requirements": result["population_contract"]["requirement_ids"], "gap_types": len(result["fields"]), "source_records": result["source_corpus"]["combined_normalized_rows"], "active_selection_counts": result["active_profile_selection_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
