#!/usr/bin/env python3
"""Fetch public community repositories into an ignored LOCAL reference folder.

This downloads code for inspection only. It does not execute downloaded code,
copy it into this project's source tree, or assert a right to redistribute it.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research" / "community_sources_20261013.json"
DEST = ROOT / ".third_party_sources"
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def load_sources():
    with MANIFEST.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    return data["repositories"]


def main():
    parser = argparse.ArgumentParser(
        description="Inspect or locally fetch reference GitHub repositories (never commits vendors)."
    )
    parser.add_argument("--list", action="store_true", help="Show candidates without network use")
    parser.add_argument("--all", action="store_true", help="Clone every candidate into ignored local folder")
    parser.add_argument("--name", action="append", default=[], help="Clone a named owner/repo (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Show planned clone commands only")
    args = parser.parse_args()
    entries = load_sources()
    if args.list or not (args.all or args.name):
        for item in entries:
            print(f'{item["priority"]}: {item["name"]} [{item["license"]}]')
        if not (args.all or args.name):
            return 0
    if args.all and args.name:
        parser.error("Use either --all or --name, not both")
    by_name = {x["name"]: x for x in entries}
    requested = list(by_name) if args.all else args.name
    unknown = [x for x in requested if x not in by_name]
    if unknown:
        parser.error("Unknown repository: " + ", ".join(unknown))
    if not args.dry_run and not shutil.which("git"):
        print("BLOCKED: git not found", file=sys.stderr)
        return 2

    results = []
    for name in requested:
        if not SAFE_NAME.fullmatch(name):
            print(f"BLOCKED invalid repository: {name}", file=sys.stderr)
            return 2
        owner, project = name.split("/")
        url = f"https://github.com/{owner}/{project}.git"
        target = DEST / owner / project
        command = ["git", "clone", "--depth=1", url, str(target)]
        if args.dry_run:
            print("WOULD FETCH", name, "->", target)
            continue
        if target.exists():
            results.append({"repo": name, "status": "SKIPPED_EXISTS",
                            "path": str(target.relative_to(ROOT))})
            print("SKIP existing", name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print("FETCH", name, flush=True)
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            results.append({"repo": name, "status": "TIMEOUT"})
            print("TIMEOUT", name)
            continue
        if proc.returncode:
            results.append({"repo": name, "status": "FAILED", "error": proc.stderr[-600:]})
            print("FAILED", name, proc.stderr[-200:])
            continue
        rev = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        sha = rev.stdout.strip() if rev.returncode == 0 else None
        results.append({"repo": name, "status": "CLONED", "sha": sha,
                        "path": str(target.relative_to(ROOT))})
        print("CLONED", name, sha or "(sha read failed)")
    if args.dry_run:
        return 0
    DEST.mkdir(parents=True, exist_ok=True)
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "results": results}
    (DEST / "LOCAL_FETCH_STATUS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if any(x["status"] in ("FAILED", "TIMEOUT") for x in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
