#!/usr/bin/env python3
"""Run an observed GUI command and its private TCP Xvfb in one execution session.

The host prohibits Unix sockets and separate command sessions do not share a
network namespace. This launcher keeps the display and client together. It does
not treat a working display as evidence that the game itself is correct.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xvfb", type=Path, required=True)
    parser.add_argument("--library-path", type=Path, required=True)
    parser.add_argument("--display", type=int, default=0,
                        help="X display number; 0 chooses an unused lock from 120 through 499")
    parser.add_argument("--screen", default="1600x1000x24")
    parser.add_argument("--xvfb-log", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("A GUI command is required after --")
    if args.display == 0:
        for candidate in secrets.SystemRandom().sample(range(120, 500), 380):
            if not Path(f"/tmp/.X{candidate}-lock").exists():
                args.display = candidate
                break
        else:
            parser.error("No unlocked private display found")
    env = os.environ.copy()
    env.update(DISPLAY=f"127.0.0.1:{args.display}", LIBGL_ALWAYS_SOFTWARE="1",
               GODOT_SILENCE_ROOT_WARNING="1")
    env["LD_LIBRARY_PATH"] = str(args.library_path.resolve()) + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    args.xvfb_log.parent.mkdir(parents=True, exist_ok=True)
    with args.xvfb_log.open("wb") as log:
        server = subprocess.Popen([str(args.xvfb.resolve()), f":{args.display}",
            "-screen", "0", args.screen, "-nolisten", "unix", "-nolisten", "local",
            "-listen", "tcp", "-ac"], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    print("Xvfb failed; inspect " + str(args.xvfb_log), file=sys.stderr)
                    return 2
                try:
                    with socket.create_connection(("127.0.0.1", 6000 + args.display), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                print("Xvfb TCP display did not become available", file=sys.stderr)
                return 2
            return subprocess.run(command, env=env).returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
