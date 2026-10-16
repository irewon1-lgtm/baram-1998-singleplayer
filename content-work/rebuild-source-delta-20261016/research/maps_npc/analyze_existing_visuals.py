"""Bounded static visual comparison; reads four known P1.5 evidence files only.

No client, server, decoder, network, or shared-state mutations. Source bytes are
referenced by SHA256 and never exported into the public research directory.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


FILES = {
    "official_map": ("84f59bd84c57777d738736b31ff9e6d5b5517f0c2173b34f6068db040626c64c.pcx", "84f59bd84c57777d738736b31ff9e6d5b5517f0c2173b34f6068db040626c64c"),
    "paststory_75": ("f2eaa4b18165e2e46a016b7d4153b382a0f1bcd1ce6f485b2dc98c21f585f77d.img", "f2eaa4b18165e2e46a016b7d4153b382a0f1bcd1ce6f485b2dc98c21f585f77d"),
    "sooni": ("80ef5507b1acd1d4c1f89a5b7a71c5c4ccbf384383e738f09b2e12e9a9e2d296.gif", "80ef5507b1acd1d4c1f89a5b7a71c5c4ccbf384383e738f09b2e12e9a9e2d296"),
    "shrine": ("297d21eb129c9c45a2ff2e7c790e13f87999d37c51a949cac4ffdc9d270426b1.gif", "297d21eb129c9c45a2ff2e7c790e13f87999d37c51a949cac4ffdc9d270426b1"),
}


def analyze(package_root):
    checks, images = [], {}
    for label, (filename, expected) in FILES.items():
        path = package_root / "evidence/images" / filename
        if path.is_symlink() or path.stat().st_size > 4_000_000:
            raise ValueError("unsafe or oversize evidence input")
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"source hash mismatch: {label}")
        with Image.open(path) as source:
            if source.width * source.height > 3_000_000:
                raise ValueError("image pixel budget exceeded")
            source.load()
            image = source.convert("RGB")
        images[label] = image
        checks.append({"label": label, "relative_path": "evidence/images/" + filename,
                       "bytes": len(data), "sha256": actual,
                       "dimensions_pixels": list(image.size), "hash_match": True,
                       "image_decoded": True})
    a, b = images["official_map"], images["paststory_75"]
    difference = ImageChops.difference(a.resize(b.size, Image.Resampling.BICUBIC), b)
    stats = ImageStat.Stat(difference)
    comparison = {"resize_rgb_bicubic_to": list(b.size),
                  "mean_absolute_difference_rgb": sum(stats.mean) / 3,
                  "rms_difference_rgb": sum(stats.rms) / 3,
                  "luminance_box_downsample": []}
    for n in (16, 32, 64):
        aa = list(a.resize((n, n), Image.Resampling.BOX).convert("L").get_flattened_data())
        bb = list(b.resize((n, n), Image.Resampling.BOX).convert("L").get_flattened_data())
        ma, mb = sum(aa)/len(aa), sum(bb)/len(bb)
        pcc = sum((x-ma)*(y-mb) for x, y in zip(aa, bb)) / math.sqrt(
            sum((x-ma)**2 for x in aa) * sum((y-mb)**2 for y in bb))
        comparison["luminance_box_downsample"].append({"dimensions": [n, n],
            "pearson_correlation": pcc,
            "mean_absolute_difference": sum(abs(x-y) for x, y in zip(aa, bb))/len(aa)})
    return {"schema": "baram.work.visual-input-check/1", "input_checks": checks,
            "map_comparison": comparison,
            "scope": "Existing-source image correspondence and source integrity only",
            "source_acquisition_count": 0, "historical_era_validation": "NOT_PROVEN_BY_METRIC",
            "map_grid_collision_exit_validation": "NOT_RUN", "npc_part_id_validation": "NOT_RUN",
            "runtime_or_P2_status": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.package_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
