#!/usr/bin/env python3
"""Check the private KR491 runtime contract, reference closure and file digests.

This verifies a generated package's integrity, not original runtime semantics,
historical sound IDs, hardware output or animation timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import wave


def verify(root):
    root = Path(root).resolve()
    package = json.loads((root / "kr491_runtime.json").read_text())
    if package.get("schema") != "baram.p2.kr491-runtime/1":
        raise ValueError("wrong runtime schema")
    unique = {}
    def image(rec):
        if rec["source_empty_rectangle"]:
            if rec["path"] is not None or all(rec["size"]):
                raise ValueError("empty source rectangle contract broken")
            return
        path = (root / rec["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("image escaped package")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != rec["sha256"]:
            raise ValueError("PNG hash mismatch: " + path.name)
        if data[:8] != b"\x89PNG\r\n\x1a\n" or list(struct.unpack_from(">II", data, 16)) != rec["size"]:
            raise ValueError("PNG dimensions differ from original rectangle")
        unique[rec["path"]] = True

    if set(package["parts"]) != {"body", "head", "sword", "shield"}:
        raise ValueError("missing original part family")
    for family, parts in package["parts"].items():
        if len(parts) != 2:
            raise ValueError("representative outfit variants missing")
        for part in parts:
            if not part["frames"]:
                raise ValueError("empty part graph")
            for offset, frame in enumerate(part["frames"]):
                if frame["frame"] != part["raw_fields"]["Starting"] + offset:
                    raise ValueError("noncontiguous original frame binding")
                image(frame)
    effects = package["effects"]
    if len(effects) != 128 or [s["id"] for s in effects] != list(range(128)):
        raise ValueError("original effect graph incomplete")
    sentinels = 0
    for seq in effects:
        if seq["preview_supported"] and seq["unsupported_commands"]:
            raise ValueError("unsupported command promoted to preview")
        for side in ("front", "back"):
            frames = seq[side + "_frames"]
            if len(frames) != seq["raw_fields"]["Num" + side.capitalize() + "Frames"]:
                raise ValueError("sequence layer frame count mismatch")
            for f in frames:
                idx = f["raw_fields"]["Frame#"]
                if idx == -1:
                    sentinels += 1
                    if not f["sentinel"] or f["image"] is not None:
                        raise ValueError("negative sentinel became image")
                else:
                    if idx < 0 or f["image"]["frame"] != idx:
                        raise ValueError("source frame reference changed")
                    image(f["image"])
        if seq["skill_id"] is not None or seq["sound_id"] is not None or seq["hit_time"] is not None:
            raise ValueError("unverified semantic binding introduced")
    sounds = package["sounds"]
    if len(sounds) != 163:
        raise ValueError("original sound graph incomplete")
    for rec in sounds:
        path = (root / rec["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("WAV escaped package")
        if hashlib.sha256(path.read_bytes()).hexdigest() != rec["sha256"]:
            raise ValueError("WAV hash mismatch")
        with wave.open(str(path)) as stream:
            pcm = stream.readframes(stream.getnframes())
            if stream.getnframes() != rec["frames"] or stream.getframerate() != rec["sample_rate"]:
                raise ValueError("WAV metadata differs")
        if hashlib.sha256(pcm).hexdigest() != rec["pcm_sha256"]:
            raise ValueError("decoded PCM hash mismatch")
    for rec in package["ui"]:
        image(rec["image"])
    guards = package.get("work_batch_guards", [])
    if guards and {g["candidate_id"] for g in guards} != {f"WD-MS-{i:03}" for i in range(1, 6)}:
        raise ValueError("Work guard set incomplete")
    return {"status": "PASS_PACKAGE_INTEGRITY_ONLY", "images_verified": len(unique),
            "wav_verified": len(sounds), "effect_sequences": len(effects),
            "negative_sentinels_preserved": sentinels, "batch_guards": len(guards),
            "runtime_execution": "NOT_ASSESSED", "historical_accuracy": "NOT_ASSESSED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root)))
    except (ValueError, OSError, KeyError, wave.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        raise SystemExit(1)
