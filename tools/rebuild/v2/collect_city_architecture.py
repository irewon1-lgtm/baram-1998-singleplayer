#!/usr/bin/env python3
"""Index actual building fixtures and prove their on-screen sprite bounds.

Bounding-box visibility is geometric evidence only. A person must review the
actual frame before any visual PASS is assigned. Partial hall images remain
separate physical captures and are never presented as one synthetic screenshot.
"""
import argparse
from collections import defaultdict
import hashlib
import html
import json
import math
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def metadata(directory, case_id, frame):
    document = read(directory / "WORLD_DOOR_QA.json", {})
    capture = next((row for row in document.get("captures", []) if row.get("game_frame") == frame.name), None)
    if capture:
        return capture, document.get("source_fingerprint", {})
    checkpoints = directory / (case_id + "-checkpoints.jsonl")
    if checkpoints.exists():
        for line in reversed(checkpoints.read_text().splitlines()):
            row = json.loads(line)
            details = row.get("details", {})
            if row.get("stage") == "ui_layout" and details.get("character_position"):
                return {"view_rect": details["view_rect"], "view_zoom": details["view_zoom"], "view_focus": details["view_focus"], "position": {"character": details["character_position"]}, "metadata_scope": "stationary fixture layout checkpoint; exact capture receipt pending process close"}, {}
    return None, {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    plan = read(root / "CITY_BUILDING_PLAN.json")
    manual_document = read(root / "ARCHITECTURE_VISUAL_REVIEW.json", {})
    manual_rows = {row["architecture_id"]: row for row in manual_document.get("architecture", [])}
    candidates = defaultdict(list)
    for mapping in sorted(root.glob("*-POSE_MAP.json")):
        document = read(mapping)
        directory = root / mapping.name.removesuffix("-POSE_MAP.json")
        for pose in document["poses"]:
            case_id = pose["local_preview_case_id"]
            frame = directory / (case_id + "-actual-game-game.png")
            if frame.exists():
                candidates[pose["architecture_id"]].append((frame, case_id, pose.get("purpose"), mapping))
    (root / "unit-crops").mkdir(exist_ok=True)
    (root / "reused").mkdir(exist_ok=True)
    rows = []
    for number, unit in enumerate(plan["architecture"]):
        source_frames = candidates[unit["architecture_id"]]
        if unit["kind"] == "service" and not unit["entire_unit_requires_multiple_normal_frames"]:
            for reuse in unit["full_house_arrival_reuse_candidates"]:
                for frame in args.door_root.glob("worker-*/" + reuse["expected_file"]):
                    source_frames.append((frame, reuse["case_id"], "full_service_house_arrival_reuse", None))
        x, y, width, height = unit["bounds_cells"]
        covered = np.zeros((height * 24, width * 24), dtype=bool)
        frames = []
        for frame, case_id, purpose, mapping in source_frames:
            capture, source_fingerprint = metadata(frame.parent, case_id, frame)
            if not capture:
                continue
            view = capture["view_rect"]
            zoom = float(capture["view_zoom"])
            telemetry_focus = capture["view_focus"]
            character = capture.get("position", {}).get("character", {})
            if character.get("map_id") != unit["map_id"]:
                continue
            # Arrival captures can retain the pre-transition UI-layout focus.
            # The screenshot itself is current. Use production's exact clamped
            # camera formula and the independently observed stationary position;
            # retain the raw layout value and disclose the derivation.
            half = [view[2] / (2 * zoom), view[3] / (2 * zoom)]
            focus = [max(half[0], min(280 * 24 - half[0], (float(character["x"]) + .5) * 24)), max(half[1], min(280 * 24 - half[1], (float(character["y"]) + .5) * 24))]
            left = view[0] + view[2] * .5 + (x * 24 - focus[0]) * zoom
            top = view[1] + view[3] * .5 + (y * 24 - focus[1]) * zoom
            right, bottom = left + width * 24 * zoom, top + height * 24 * zoom
            full = left >= view[0] and top >= view[1] and right <= view[0] + view[2] and bottom <= view[1] + view[3]
            xx0 = max(0, math.ceil((view[0] - left) / zoom))
            yy0 = max(0, math.ceil((view[1] - top) / zoom))
            xx1 = min(width * 24, math.floor((view[0] + view[2] - left) / zoom))
            yy1 = min(height * 24, math.floor((view[1] + view[3] - top) / zoom))
            covered[yy0:yy1, xx0:xx1] = True
            if xx1 <= xx0 or yy1 <= yy0:
                continue
            im = Image.open(frame).convert("RGB")
            crop_box = (max(int(view[0]), math.floor(left) - 8), max(int(view[1]), math.floor(top) - 8), min(int(view[0] + view[2]), math.ceil(right) + 8), min(int(view[1] + view[3]), math.ceil(bottom) + 8))
            crop = root / "unit-crops" / f"unit-{number:03d}-part-{len(frames):02d}.png"
            im.crop(crop_box).save(crop)
            original = frame
            if purpose == "full_service_house_arrival_reuse":
                frame = root / "reused" / (f"unit-{number:03d}-" + original.name)
                if not frame.exists():
                    shutil.copy2(original, frame)
                raw = original.parent / original.name.replace("-game.png", ".png")
                if raw.exists():
                    target = root / "reused" / (f"unit-{number:03d}-" + raw.name)
                    if not target.exists():
                        shutil.copy2(raw, target)
            frames.append({"frame": str(frame.relative_to(root)), "frame_sha256": sha(frame), "original_capture": str(original), "purpose": purpose, "full_native_sprite_bounds_visible": full, "sprite_bounds_in_game_window_px": [left, top, right, bottom], "native_asset_rectangle_visible": [xx0, yy0, xx1, yy1], "view_rect": view, "view_focus": focus, "raw_layout_view_focus": telemetry_focus, "focus_origin": "Production clamped camera formula from observed stationary character and actual view rectangle; raw arrival UI-layout focus may predate transition", "view_zoom": zoom, "position": capture.get("position"), "source_fingerprint": source_fingerprint, "mapping_receipt": str(mapping) if mapping else None, "actual_unit_crop": str(crop.relative_to(root)), "actual_unit_crop_sha256": sha(crop), "crop_box_game_window_px": crop_box})
        row = {**unit, "index": number, "frames": frames, "capture_status": "ACTUAL_FRAME_CAPTURED" if frames else "NOT_RUN", "native_rectangle_union_visible_fraction": float(covered.mean()), "entire_native_rectangle_covered_by_actual_frames": bool(covered.all()), "visual_status": "NOT_RUN_MANUAL_REVIEW_REQUIRED", "coverage_scope": "Actual screenshot/layout intersection of source sprite bounds. Does not infer unobscured pixels or visual quality from geometry."}
        manual = manual_rows.get(unit["architecture_id"])
        if manual and manual.get("frames") and {frame["sha256"] for frame in manual["frames"]} <= {frame["frame_sha256"] for frame in frames}:
            row["visual_status"] = manual["status"]
            row["manual_findings"] = manual["findings"]
        rows.append(row)
    report = {"schema": "baram.city.actual-architecture-index/1", "content_sha256": plan["content_sha256"], "runtime_sha256": plan["runtime_sha256"], "source_ui_sha256": read(root / "FROZEN_SOURCE.json")["source_fingerprint"]["ui/gameplay.gd"], "collector_sha256": sha(__file__), "status": "CAPTURE_INDEX_WITH_EXPLICIT_MANUAL_LEDGER_NO_GLOBAL_PASS", "summary": {"architecture_rows": len(rows), "rows_with_actual_frames": sum(bool(row["frames"]) for row in rows), "rows_with_full_native_bounds_covered": sum(row["entire_native_rectangle_covered_by_actual_frames"] for row in rows), "rows_manually_reviewed": sum(not row["visual_status"].startswith("NOT_RUN") for row in rows), "movement_pass": "NOT_CLAIMED_VISUAL_FIXTURES"}, "architecture": rows}
    (root / "ARCHITECTURE_CAPTURE_INDEX.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    contacts = root / "contact-sheets"
    contacts.mkdir(exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    ready = [row for row in rows if row["frames"]]
    for start in range(0, len(ready), 6):
        sheet = Image.new("RGB", (1200, 600), "#ded4ba")
        draw = ImageDraw.Draw(sheet)
        for slot, row in enumerate(ready[start:start + 6]):
            sx, sy = slot % 3 * 400, slot // 3 * 300
            draw.text((sx + 7, sy + 5), f"{row['index']:03d} {row['kind']} {row['native_view_point']}", font=font, fill="black")
            draw.text((sx + 7, sy + 23), row["architecture_id"], font=font, fill="black")
            pieces = row["frames"][:2] if row.get("entire_unit_requires_multiple_normal_frames", False) else row["frames"][:1]
            for part, frame in enumerate(pieces):
                image = Image.open(root / frame["actual_unit_crop"]).convert("RGB")
                boxw = 388 // len(pieces)
                scale = min(1.0, boxw / image.width, 245 / image.height)
                image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.NEAREST)
                sheet.paste(image, (sx + 6 + part * boxw, sy + 48))
        sheet.save(contacts / f"architecture-{start:03d}-{min(start + 5, len(ready) - 1):03d}.jpg", quality=94)
    html_rows = []
    for row in rows:
        images = "".join(f'<a href="{html.escape(frame["frame"])}"><img width="460" src="{html.escape(frame["actual_unit_crop"])}"></a>' for frame in row["frames"])
        html_rows.append(f'<article><h3>{row["index"]:03d} {html.escape(row["architecture_id"])} / {html.escape(row["map_name"])}</h3><p>{html.escape(row["kind"])} {row["native_view_point"]}; actual bounds coverage {row["native_rectangle_union_visible_fraction"]:.1%}; {html.escape(row["visual_status"])}</p>{images}</article>')
    (root / "architecture-gallery.html").write_text('<meta charset="utf-8"><title>Actual city architecture fixtures</title><style>body{background:#e2dac5;font-family:sans-serif}article{border:1px solid #806d4c;padding:10px;margin:12px}img{image-rendering:pixelated;max-width:100%}</style><h1>142 city architecture units — actual game captures</h1><p>Offline fixture starts and normal UI; no movement or automatic visual PASS. Images link to physical full game-window captures. The hall remains two separate overlapping captures.</p>' + "".join(html_rows), encoding="utf-8")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
