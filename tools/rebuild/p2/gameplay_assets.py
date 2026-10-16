#!/usr/bin/env python3
"""Targeted private actor assets for the authorized P3 slice.

Reuse original KR491 part pixels and existing P2 motion/layer assignments.
No full-family re-decode, generic creature drawing, or historical ID invention.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

DAT_SHA = "f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7"
READER_SHA = "f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2"
DIRECTIONS = ["north", "east", "south", "west"]
ROOT = Path(__file__).resolve().parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class Sources:
    def __init__(self, args):
        self.output = args.output.resolve()
        if ROOT == self.output or ROOT in self.output.parents:
            raise ValueError("Original or decoded assets must stay outside public checkout")
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "images").mkdir(exist_ok=True)
        reader_bytes = args.reader.read_bytes()
        if sha(reader_bytes) != READER_SHA:
            raise ValueError("Pinned reader SHA mismatch")
        spec = importlib.util.spec_from_file_location("p3_fixed_kr491_reader", args.reader)
        self.reader = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.reader
        spec.loader.exec_module(self.reader)
        self.raw = args.dat.read_bytes()
        if sha(self.raw) != DAT_SHA:
            raise ValueError("KR491 DAT SHA mismatch")
        self.dat = self.reader.dat_entries(self.raw)
        self.parts = {}
        normalized = args.p15 / "docs/rebuild/p1_5/selected_content/kr_asset_parts.jsonl"
        self.normalized_sha = sha(normalized.read_bytes())
        for row in rows(normalized):
            if row["source"]["container_sha256"] != DAT_SHA:
                raise ValueError("Part table container mismatch")
            member = self.dat[row["source"]["member"].lower()][2]
            if sha(member) != row["source"]["member_sha256"]:
                raise ValueError("Part table member SHA mismatch")
            self.parts[(row["kind"], row["original_value"]["ID"])] = row
        self.base = args.runtime.resolve()
        self.kr491 = json.loads((self.base / "kr491/kr491_runtime.json").read_text())
        self.epfs, self.pals, self.decoded, self.used = {}, {}, {}, {}

    def member(self, name):
        original_name, offset, data = self.dat[name.lower()]
        self.used[original_name] = {"member": original_name, "sha256": sha(data),
                                    "dat_offset": offset, "bytes": len(data)}
        return data

    def frame(self, family, index, palette, recolor=0):
        key = (family, index, palette, recolor)
        if key in self.decoded:
            return self.decoded[key]
        if family not in self.epfs:
            self.epfs[family] = self.reader.Epf(self.member(family + ".epf"))
            self.pals[family] = self.reader.read_palettes(self.member(family + ".pal"))
        if index < 0 or palette < 0 or palette >= len(self.pals[family]):
            raise ValueError("Invalid explicit frame/palette")
        source = self.epfs[family].frame(index)
        if not source.width or not source.height:
            raise ValueError("Chosen gameplay frame has source-defined empty rectangle")
        rgba = source.rgba(self.pals[family][palette], recolor)
        image = Image.frombytes("RGBA", (source.width, source.height), rgba)
        self.decoded[key] = (image, [source.left, source.top], {
            "source_id": f"KR491:sprite:{family}:{index}", "frame": index,
            "palette": palette, "recolor_byte": recolor,
            "recolor_semantics": "WORKING_RECONSTRUCTION_USING_EXISTING_READER_INDEX_SHIFT;KR_ORIGINAL_COLOR_UNVERIFIED" if recolor else "SOURCE_PALETTE_UNSHIFTED",
            "epf": family + ".epf", "palette_member": family + ".pal",
            "rgba_sha256": sha(rgba), "offset": [source.left, source.top]})
        return self.decoded[key]

    def part(self, kind, part_id, relative_frame, recolor=0):
        row = self.parts[(kind.lower(), part_id)]
        value = row["original_value"]
        family = {"body": "Body", "head": "Head", "sword": "Sword", "shield": "Shield", "monster": "Monster", "item": "Item"}[kind.lower()]
        absolute = value.get("Starting", part_id) + relative_frame
        return self.frame(family, absolute, value["Palette"], recolor)

    def write_frame(self, image, offset, sources):
        digest = sha(image.tobytes() + bytes(str(offset), "ascii"))
        path = "images/" + digest[:24] + ".png"
        target = self.output / path
        if not target.exists():
            image.save(target)
        return {"path": path, "offset": offset, "duration_ms": 130,
                "png_sha256": sha(target.read_bytes()), "source_frames": sources}

    def actor_frame(self, parts, action, direction, tick):
        armed = parts.get("sword") is not None
        motion_action = "armed_walking" if action in ("standing", "walking") and armed else action
        motion = self.kr491["motion_inspection"][motion_action]
        chosen, source_frames, body_index = {}, [], -1
        for kind in ("body", "head", "sword", "shield"):
            part_id = parts.get(kind)
            if part_id is None:
                continue
            seqs = motion.get(kind, [])
            if not seqs:
                continue
            seq = seqs[direction]
            if not seq:
                continue
            index = seq[(0 if action == "standing" else tick) % len(seq)]
            image, offset, provenance = self.part(kind, part_id, index, parts.get("recolors", {}).get(kind, 0))
            chosen[kind] = (image, offset)
            source_frames.append({**provenance, "part_id": f"KR491:{kind}:{part_id}", "relative_frame": index})
            if kind == "body":
                body_index = index
        if body_index < 0:
            raise ValueError("Actor has no body frame")
        order = self.kr491["motion_inspection"]["draw_order"][body_index]
        surface = Image.new("RGBA", (128, 128))
        origin = (64, 96)
        for token in order:
            kind = {"b": "body", "h": "head", "w": "sword", "s": "shield"}.get(token)
            if kind in chosen:
                image, offset = chosen[kind]
                if min(origin[0] + offset[0], origin[1] + offset[1]) < 0:
                    raise ValueError("Actor canvas clips source frame")
                surface.alpha_composite(image, (origin[0] + offset[0], origin[1] + offset[1]))
        bbox = surface.getbbox()
        if bbox is None or bbox[0] == 0 or bbox[1] == 0 or bbox[2] == 128 or bbox[3] == 128:
            raise ValueError("Composed actor empty or clipped")
        return self.write_frame(surface.crop(bbox), [bbox[0] - origin[0], bbox[1] - origin[1]], source_frames)


def preview(src):
    """One representative per chosen group, rather than decoding all frames."""
    groups = [("monster", list(range(100))), ("body", list(range(40))),
              ("head", list(range(50))), ("item", list(range(160)))]
    manifest = []
    for kind, ids in groups:
        width, height = (100, 112) if kind == "monster" else (90, 96)
        sheet = Image.new("RGBA", (width * 10, height * ((len(ids) + 9) // 10)), "#79735c")
        draw = ImageDraw.Draw(sheet)
        for n, part_id in enumerate(ids):
            relative = 0 if kind in ("monster", "item") else 6
            try:
                image, offset, provenance = src.part(kind, part_id, relative)
            except ValueError as error:
                manifest.append({"kind": kind, "part_id": part_id, "failed": str(error)})
                continue
            image = image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)
            x, y = (n % 10) * width, (n // 10) * height
            if image.width < width and image.height < height - 16:
                sheet.alpha_composite(image, (x + (width - image.width) // 2, y + height - 20 - image.height))
            else:
                image.thumbnail((width - 4, height - 20), Image.Resampling.NEAREST)
                sheet.alpha_composite(image, (x + 2, y + 2))
            draw.text((x + 3, y + height - 16), f"{kind}:{part_id}", fill="white")
            manifest.append({"kind": kind, "part_id": part_id, "source": provenance})
        sheet.save(src.output / ("preview-" + kind + ".png"))
    (src.output / "PREVIEW_SELECTION_INPUT.json").write_text(json.dumps(manifest, indent=2) + "\n")


def build(src, config):
    looks = {}
    for look_id, parts in config["humanoids"].items():
        animations = {}
        for action, frames in (("standing", 1), ("walking", 3), ("attack", 2), ("casting", 1)):
            animations[action] = {str(direction): [src.actor_frame(parts, action, direction, tick)
                                                   for tick in range(frames)] for direction in range(4)}
        looks[look_id] = {"id": look_id, "source_parts": parts,
                          "fact_status": "RECONSTRUCTED", "animations": animations,
                          "binding_scope": "Original Korean pixels, visually selected role/identity and P2-inferred motion/layer mapping; historical NPC look IDs unknown"}
    for look_id, selected_monster in config["monsters"].items():
        part_id = selected_monster["part_id"]
        recolor = selected_monster.get("recolor", 0)
        row = src.parts[("monster", part_id)]["original_value"]
        walking, attacking = row["Walk"], row["Attack"]
        if not walking or walking + attacking > 30:
            raise ValueError("Unsupported chosen monster group layout")
        next_row = src.parts.get(("monster", part_id + 1))
        if next_row is None:
            raise ValueError("Chosen monster requires next group boundary")
        total = next_row["original_value"]["Starting"] - row["Starting"]
        if total % 4 or total // 4 < walking + attacking:
            raise ValueError("Monster group does not contain four bounded directions")
        animations = {action: {} for action in ("standing", "walking", "attack", "casting")}
        for direction in range(4):
            # Contact-sheet evidence: all four Walk groups precede all four
            # Attack groups. Interleaving walk/attack per direction is wrong.
            start = direction * walking
            def get(indices):
                result = []
                for index in indices:
                    image, offset, provenance = src.part("monster", part_id, index, recolor)
                    result.append(src.write_frame(image, offset, [{**provenance, "part_id": f"KR491:monster:{part_id}", "relative_frame": index}]))
                return result
            animations["standing"][str(direction)] = get([start])
            animations["walking"][str(direction)] = get(range(start, start + walking))
            # Monsters without an attack group visibly lunge using walking
            # pixels; never infer a missing raw frame or negative sentinel.
            attack_start = walking * 4 + direction * attacking
            animations["attack"][str(direction)] = get(range(attack_start, attack_start + attacking)) if attacking else get([start])
            animations["casting"][str(direction)] = get([start])
        looks[look_id] = {"id": look_id, "source_parts": {"monster": part_id, "recolor_byte": recolor},
                          "fact_status": "RECONSTRUCTED", "animations": animations,
                          "binding_scope": "Visually selected animal; original table part/frame/palette explicit; entity-name and action grouping working reconstruction"}
    icons = {}
    for item_id, icon in config.get("icons", {}).items():
        if "official_name" in icon:
            manifest = json.loads((src.base / "icons/icons.json").read_text())
            matches = [row for row in manifest["entries"] if row["name_ko"] == icon["official_name"]]
            if len(matches) != 1:
                raise ValueError("Named official icon missing or ambiguous")
            match = matches[0]
            image = Image.open(src.base / "icons" / match["image_path"]).convert("RGBA")
            value = src.write_frame(image, [-(image.width // 2), -image.height], [{"official_binding_id": match["id"], "image_sha256": match["source_sha256"]}])
            value["fact_status"] = match["fact_status"]
        else:
            image, offset, provenance = src.part(icon.get("family", "item"), icon["part_id"], icon.get("relative_frame", 0), icon.get("recolor", 0))
            value = src.write_frame(image, offset, [provenance])
            value["fact_status"] = "RECONSTRUCTED"
        icons[item_id] = value
    result = {"schema": "baram.gameplay.actor-assets/1", "generation": "WORK-GAMEPLAY-ASSETS001",
              "direction_order": DIRECTIONS, "original_timing": "UNKNOWN; explicit130ms working frame duration",
              "source": {"dat_sha256": DAT_SHA, "reader_sha256": READER_SHA,
                         "normalized_parts_sha256": src.normalized_sha, "members": src.used,
                         "selection_config_sha256": sha(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()),
                         "builder_sha256": sha(Path(__file__).read_bytes())},
              "looks": looks, "icons": icons,
              "actor_aliases": config.get("actor_aliases", {}),
              "item_equipment_graphics": config.get("item_equipment_graphics", {}),
              "decoded_target_frames": len(src.decoded), "full_family_decode_performed": False}
    (src.output / "actors.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"looks": len(looks), "icons": len(icons), "decoded_target_frames": len(src.decoded), "original_timing": "UNKNOWN"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dat", type=Path, required=True)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--p15", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    src = Sources(args)
    if args.preview:
        preview(src)
    if args.config:
        build(src, json.loads(args.config.read_text()))
    if not args.preview and not args.config:
        parser.error("Choose --preview or --config")
