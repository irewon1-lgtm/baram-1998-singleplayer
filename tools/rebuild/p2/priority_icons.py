"""Bind already acquired official guide images for the isolated P2 inspector.

No network, game data defaults, EPF-ID inference or original-file writes.
Document item IDs remain capture-scoped. A 2000 image association may be
inspected in the 2001 working profile only as a CORROBORATED correspondence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html
from PIL import Image


SCHEMA = "baram.priority.icons/1"
PROFILE = "KR_GUIDE_2001_WORKING"
STAT_FIELDS = (
    "listed_price", "listed_price_unit", "price_semantics", "minimum_level",
    "durability", "armor_class", "damage_min", "damage_max",
    "required_strength", "job_restriction_documented", "gender_documented",
    "effects", "item_kind", "vendor_role_hints",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalized_text(node) -> str:
    return " ".join(" ".join(node.itertext()).split())


def image_key(url: str) -> str:
    """Compare the explicit /item/img/ suffix, never a filename alone."""
    path = urlsplit(url).path
    return path.split("/item/img/", 1)[1] if "/item/img/" in path else path


def check_corrupt_source_refusal(source: Path) -> dict:
    """One copied-index negative test; original source bytes are never edited."""
    source = source.resolve()
    with tempfile.TemporaryDirectory(prefix="p2-icon-negative-") as temp:
        base = Path(temp)
        fake = base / "source"
        fake.mkdir()
        (fake / "docs/rebuild/p1_5").mkdir(parents=True)
        (fake / "docs/rebuild/p1_5/selected_content").symlink_to(
            source / "docs/rebuild/p1_5/selected_content", target_is_directory=True)
        (fake / "evidence").symlink_to(source / "evidence", target_is_directory=True)
        (fake / "PRIVATE_SOURCE_INDEX.json").write_bytes((source / "PRIVATE_SOURCE_INDEX.json").read_bytes())
        index = json.loads((source / "PRIVATE_IMAGE_INDEX.json").read_text())
        first = read_jsonl(source / "docs/rebuild/p1_5/selected_content/kr_official_image_bindings.jsonl")[0]
        image_digest = first["original_value"]["image_sha256"]
        (fake / "tampered.gif").write_bytes(b"corrupted-icon-negative-fixture")
        for row in index:
            if row["sha256"] == image_digest:
                row["path"] = "tampered.gif"
        (fake / "PRIVATE_IMAGE_INDEX.json").write_text(json.dumps(index))
        try:
            build(fake, base / "output", base / "report")
        except ValueError as error:
            if not str(error).startswith("Image SHA mismatch: "):
                raise
            return {"test": "corrupt_source_image_refused", "result": "PASS",
                    "observed": str(error), "original_source_mutated": False}
        raise AssertionError("Corrupt image was accepted")


def build(source: Path, output: Path, report: Path) -> dict:
    source, output, report = source.resolve(), output.resolve(), report.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must not modify the read-only P1.5 package")
    selected = source / "docs/rebuild/p1_5/selected_content"
    bindings_path = selected / "kr_official_image_bindings.jsonl"
    items_path = selected / "kr_official_items.jsonl"
    bindings, items = read_jsonl(bindings_path), read_jsonl(items_path)
    item_by_id = {row["content_id"]: row for row in items}
    if len(item_by_id) != len(items):
        raise ValueError("Duplicate document item ID")
    by_name = defaultdict(list)
    for row in items:
        by_name[row["entity_name_ko"]].append(row)
    source_index = {row["sha256"]: row for row in json.loads((source / "PRIVATE_SOURCE_INDEX.json").read_text())}
    image_index = {row["sha256"]: row for row in json.loads((source / "PRIVATE_IMAGE_INDEX.json").read_text())}
    documents = {}
    verified_sources = set()

    def verify_row(row: dict) -> dict:
        digest = row["input_sha256"]
        src = source_index[digest]
        file = source / src["path"]
        if digest not in documents:
            if sha(file) != digest:
                raise ValueError("Source HTML SHA mismatch: " + row["content_id"])
            documents[digest] = html.fromstring(file.read_bytes().decode("cp949", errors="strict"))
            verified_sources.add(digest)
        line = row["source_locator"]["html_line_start"]
        candidates = documents[digest].xpath("//tr")
        actual = [tr for tr in candidates if tr.sourceline == line]
        if len(actual) != 1:
            raise ValueError("Raw table row not found: " + row["content_id"])
        cells = actual[0].xpath("./td|./th")
        if not cells or normalized_text(cells[0]) != row["entity_name_ko"]:
            raise ValueError("Raw table item name mismatch: " + row["content_id"])
        actual_links = {(node.get("src"), node.sourceline) for node in actual[0].xpath(".//img[@src]")}
        for link in row["original_value"]["image_links"]:
            if (link["relative_src"], link["html_line"]) not in actual_links:
                raise ValueError("Raw item image link mismatch: " + row["content_id"])
        return {"source_id": src["source_id"], "sha256": digest, "line": line}

    output.mkdir(parents=True, exist_ok=True)
    (output / "images").mkdir(exist_ok=True)
    report.mkdir(parents=True, exist_ok=True)
    entries, ledger, problems = [], [], []
    converted = {}
    for binding in bindings:
        original = binding["original_value"]
        parent = item_by_id[original["item_record_id"]]
        parent_pointer = verify_row(parent)
        image_digest = original["image_sha256"]
        image_file = source / image_index[image_digest]["path"]
        if sha(image_file) != image_digest:
            raise ValueError("Image SHA mismatch: " + binding["content_id"])
        with Image.open(image_file) as decoded:
            decoded.load()
            if decoded.n_frames != 1:
                raise ValueError("Animated image must have explicit timing handling")
            if (decoded.width, decoded.height) != (original["width"], original["height"]):
                raise ValueError("Image dimensions mismatch")
            rgba = decoded.convert("RGBA")
            if rgba.getbbox() is None:
                raise ValueError("Fully empty source image")
            pixel_digest = hashlib.sha256(rgba.tobytes()).hexdigest()
            png = output / "images" / (image_digest + ".png")
            if image_digest not in converted:
                rgba.save(png)
                with Image.open(png) as check:
                    check.load()
                    if check.convert("RGBA").tobytes() != rgba.tobytes():
                        raise ValueError("Lossless PNG conversion failed")
                converted[image_digest] = {"png_sha256": sha(png), "rgba_sha256": pixel_digest}
        # A direct 2001 association is preferred when it exists. Same name and
        # explicit relative image suffix are required for the lesser join.
        parent_links = {image_key(link["original_url"]) for link in parent["original_value"]["image_links"]}
        candidates = [row for row in by_name[parent["entity_name_ko"]]
                      if row["build_profile_id"] == "KR_GUIDE_2001_SNAPSHOT"
                      and parent_links & {image_key(link["original_url"]) for link in row["original_value"]["image_links"]}]
        if len(candidates) > 1:
            raise ValueError("Ambiguous same-name 2001 image join: " + binding["content_id"])
        working = candidates[0] if candidates else None
        selected_item = working or parent
        selected_pointer = verify_row(selected_item)
        active = working is not None
        fact_status = "CORROBORATED" if active else "ORIGINAL_VERIFIED"
        # The table-to-image association is direct in the 2000 capture. Its use
        # for the 2001 /middle/ item row is explicitly not direct image proof.
        entry = {
            "id": binding["content_id"], "item_id": selected_item["content_id"],
            "original_item_id": parent["content_id"], "name_ko": parent["entity_name_ko"],
            "image_path": "images/" + image_digest + ".png",
            "source_sha256": image_digest, "png_sha256": converted[image_digest]["png_sha256"],
            "rgba_sha256": converted[image_digest]["rgba_sha256"],
            "width": original["width"], "height": original["height"],
            "profile": PROFILE if active else "KR_GUIDE_2000_SNAPSHOT_VARIANT",
            "working_profile_eligible": active,
            "fact_status": fact_status,
            "source_binding_fact_status": "ORIGINAL_VERIFIED",
            "source_pointer": {"binding_id": binding["content_id"], "parent": parent_pointer,
                               "selected_item": selected_pointer, "image_source_id": original["image_source_id"],
                               "table_capture_at": original["table_capture_at"],
                               "image_actual_capture_at": original["image_actual_capture_at"]},
            "stats": {key: selected_item["original_value"].get(key) for key in STAT_FIELDS},
            "stats_fact_status": "ORIGINAL_VERIFIED",
            "stats_profile": selected_item["build_profile_id"],
            "equipment_sprite_id": None, "epf_frame_id": None,
            "view_roles": ["inventory_thumbnail", "equipment_slot_thumbnail", "field_inspection_thumbnail"],
            "view_role_fact_status": "RECONSTRUCTED",
            "runtime_status": "SELECTED", "test_status": "NOT_RUN",
        }
        entries.append(entry)
        ledger.append({
            "field_id": "item.icon." + binding["content_id"], "content_id": selected_item["content_id"],
            "profile": entry["profile"], "selected_value": {"image_sha256": image_digest, "icon_id": entry["id"]},
            "unit": "documented_image", "source_tier": 1,
            "source_id": original["image_source_id"], "source_pointer": entry["source_pointer"],
            "era_match": "WITHIN_TARGET_CROSS_CAPTURE" if active else "2000_VARIANT_WITHIN_TARGET",
            "selection_reason": "2001 named row and explicit image suffix agree; 2000 official image association retained as corroboration" if active else "No same-name and image-suffix 2001 row; preserve 2000 direct document association as variant",
            "alternatives": [{"content_id": parent["content_id"], "profile": parent["build_profile_id"]}] if active else [],
            "fact_status": fact_status, "runtime_status": "SELECTED", "test_evidence": [],
        })
        if not active:
            problems.append({"field_id": "item.icon." + binding["content_id"], "content_id": parent["content_id"],
                             "reason": "OUT_OF_SELECTED_PROFILE", "next": "2001 named item row and exact image URL/bytes required; source2000 variant remains inspectable"})

    covered_working = {row["item_id"] for row in entries if row["working_profile_eligible"]}
    working_items = [row for row in items if row["build_profile_id"] == "KR_GUIDE_2001_SNAPSHOT"]
    remaining = [{"field_id": "item.icon." + row["content_id"], "content_id": row["content_id"],
                  "reason": "ACCESS_BLOCKED_OR_NOT_ACQUIRED", "source_id": row["source_ids"][0],
                  "source_pointer": {"line": row["source_locator"]["html_line_start"], "sha256": row["input_sha256"]},
                  "required": "Exact linked archived official image bytes in kr_official_items.image_links; no shared fallback"}
                 for row in working_items if row["content_id"] not in covered_working]
    result = {"schema": SCHEMA, "generation": "WORK-PRIORITY-ICONS001", "target_profile": PROFILE,
              "source_fingerprints": {"bindings": sha(bindings_path), "items": sha(items_path),
                                      "tool": sha(Path(__file__))},
              "scope": "Official document illustrations consumed by P2 thumbnail inspector; not proven original inventory/floor/equipped sprites",
              "entries": entries}
    (output / "icons.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (report / "ICON_SELECTIONS.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ledger))
    audit = {"schema": SCHEMA, "result": "PARTIAL", "source_fingerprints": result["source_fingerprints"],
             "input": {"official_binding_candidates": len(bindings), "distinct_source_images": len(converted),
                       "parent_2000_item_rows": len(bindings), "all_2001_document_item_rows": len(working_items)},
             "static_results": {"raw_parent_name_image_links_verified": len(entries),
                                "source_images_hash_and_png_pixel_roundtrip_pass": len(converted),
                                "working_2001_named_image_suffix_joins": len(covered_working),
                                "source2000_variant_only": len(problems),
                                "source_html_files_hash_checked": len(verified_sources),
                                "working2001_images_unfilled": len(remaining),
                                "equipment_composition_ids_resolved": 0,
                                "shared_fallbacks": 0, "runtime_exercised": 0},
             "source_item_kind_counts": dict(Counter(item_by_id[row["original_value"]["item_record_id"]]["original_value"]["item_kind"] for row in bindings)),
             "output_manifest": {"file": "icons.json", "sha256": sha(output / "icons.json"), "private_only": True},
             "variant_only": problems, "remaining_working2001_image_gaps": remaining,
             "runtime": {"status": "NOT_RUN", "owner": "P2 runtime integration", "required": "Bind icons.json to actual inspector state and verify representative inventory/equipment/field thumbnails; missing ID must reject"},
             "limits": ["100 working joins are CORROBORATED cross-capture mappings, not direct 2001 image associations",
                        "Source illustrations do not establish in-client EPF/frame/palette/equipped appearance IDs",
                        "477 2001 document rows are a capture namespace, not total game item population",
                        "Price column remains unspecified listed price; absent stats remain null"]}
    (report / "ICON_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    (report / "ICON_NOTES.md").write_text(
        "# Official image binding inspection\n\n"
        f"Recomputed {len(bindings)} named official-guide associations from raw table rows, "
        f"{len(converted)} distinct acquired image hashes. All input hashes, dimensions and lossless PNG pixel roundtrips pass. "
        "These checks establish conversion integrity, not game execution.\n\n"
        f"{len(covered_working)} same-name 2001 rows also contain the same explicit image suffix. Their 2001 documented stats are selected; "
        "the image association stays CORROBORATED because the acquired image originates from the older URL/capture. "
        f"{len(problems)} source2000 variants remain separate and cannot silently enter the working2001 profile. "
        "No weapon image appears in this105-candidate set (59 armour/accessories and46 other items).\n\n"
        "Runtime API: private icons.json entries expose id, item_id, original_item_id, name_ko, image_path, "
        "width/height, stats, profile and working_profile_eligible. PNG paths are relative to icons.json. "
        "Use the selected entry as the single inspector state for inventory, equipped-slot thumbnail, field thumbnail and stat text. "
        "Only an explicit item selection may change the displayed image; missing IDs must error, never fall back. "
        "Source guide thumbnails are being reused in those view roles as RECONSTRUCTED presentation. "
        "equipment_sprite_id and epf_frame_id remain null, so body composition cannot claim to match this image.\n\n"
        f"The2001 capture has {len(working_items)} item rows and {len(remaining)} still lack an acquired matching image for this inspector. "
        "Exact IDs and source pointers are in ICON_AUDIT.json; retrieve the listed source row image URL/bytes, "
        "then check a direct image-to-item relation. Historical game item totals remain UNKNOWN.\n\n"
        "Runtime tests are NOT_RUN in this conversion report. Root integration must record actual P2 screenshots/state checks "
        "without promoting Linux results to Android/Windows.\n"
    )
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p15", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--exercise-negative-tests", action="store_true")
    args = parser.parse_args()
    audit = build(args.p15, args.output, args.report_dir)
    if args.exercise_negative_tests:
        audit["negative_tests"] = [check_corrupt_source_refusal(args.p15)]
        (args.report_dir / "ICON_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": audit["result"], "input": audit["input"], "static_results": audit["static_results"]}))
