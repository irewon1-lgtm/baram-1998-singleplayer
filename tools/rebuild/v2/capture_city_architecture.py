#!/usr/bin/env python3
"""Capture declared city building poses using the existing normal-UI operator.

The offline save starts are visual fixtures. This tool never reports movement,
natural progression, or visual quality PASS. Full X framebuffer/window captures
and per-pose fixture/position receipts are produced by test_os_world_doors.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "godot", "project", "runtime", "xdotool", "xvfb", "library-path", "seed-save", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--worker-index", type=int, default=0)
    parser.add_argument("--worker-count", type=int, default=1)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    assert sha(args.runtime / "gameplay_content.json") == plan["content_sha256"]
    assert 0 <= args.worker_index < args.worker_count
    poses = plan["new_preview_poses"][args.worker_index::args.worker_count]
    parent = args.output.parent
    parent.mkdir(parents=True, exist_ok=True)
    pose_map = []
    for index, pose in enumerate(poses):
        pose_map.append({**pose, "local_preview_case_id": f"preview-{index:03d}"})
    receipt_path = parent / (args.output.name + "-POSE_MAP.json")
    tool = Path(__file__).with_name("test_os_world_doors.py")
    command = [sys.executable, str(tool.resolve())]
    for name in ("godot", "project", "runtime", "xdotool", "seed_save", "output"):
        command.extend(["--" + name.replace("_", "-"), str(getattr(args, name).resolve())])
    command.extend(["--screen", "1600x1000"])
    for pose in poses:
        command.extend(["--preview-scene", pose["map_id"] + "," + ",".join(map(str, pose["point"]))])
    launcher = Path(__file__).with_name("with_display.py")
    wrapped = [sys.executable, str(launcher.resolve()), "--xvfb", str(args.xvfb.resolve()), "--library-path", str(args.library_path.resolve()), "--screen", "1600x1000x24", "--xvfb-log", str(parent / (args.output.name + "-xvfb.log")), "--"] + command
    receipt = {"schema": "baram.city.architecture-pose-worker/1", "scope": "ACTUAL_RENDER_OFFLINE_INITIAL_FIXTURES_NORMAL_UI_ONLY; NOT_MOVEMENT_PASS; NOT_VISUAL_PASS", "content_sha256": plan["content_sha256"], "runtime_sha256": sha(args.runtime / "runtime.json"), "wrapper_sha256": sha(__file__), "operator_sha256": sha(tool), "plan_sha256": sha(args.plan), "poses": pose_map, "command": wrapped}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    env = os.environ.copy()
    env["LP_NUM_THREADS"] = "1"
    result = subprocess.run(wrapped, env=env)
    receipt["process_exit_code"] = result.returncode
    receipt["content_unchanged_after"] = sha(args.runtime / "gameplay_content.json") == plan["content_sha256"]
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
