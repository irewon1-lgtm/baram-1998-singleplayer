#!/usr/bin/env python3
"""Fail before a commit if Codex P2 touches another owner's path."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = "590bd626b63cebf6d858c8e9c1c9ce822ea0ec94"


def permitted(path: str) -> bool:
    return (
        path.startswith(("rebuild/p2/", "tools/rebuild/p2/", "docs/rebuild/p2/"))
        or path.startswith("tools/rebuild/p1_5/")
        or path == "tools/rebuild/step01/validate_step01.py"
        or (path.startswith(".github/workflows/rebuild-p2-") and path.endswith(".yml"))
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(ROOT), *cmd])
    # --no-renames exposes both source and destination of any rename.
    paths = set()
    for cmd in [("diff", "--no-renames", "--name-only", "-z", BASE),
                ("ls-files", "--others", "--exclude-standard", "-z")]:
        paths.update(p.decode() for p in git(*cmd).split(b"\0") if p)
    violations = sorted(p for p in paths if not permitted(p))
    result = {"schema":"baram.p2.boundary/1", "base":BASE,
              "head":git("rev-parse", "HEAD").decode().strip(),
              "branch":git("branch", "--show-current").decode().strip(),
              "paths":sorted(paths), "violations":violations,
              "work_and_game_unchanged":not violations,
              "conditional_common_changes":sorted(p for p in paths if p.startswith("tools/rebuild/p1_5/") or p == "tools/rebuild/step01/validate_step01.py"),
              "result":"FAIL" if violations else "PASS"}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k != "paths"}))
    return bool(violations)


if __name__ == "__main__":
    raise SystemExit(main())
