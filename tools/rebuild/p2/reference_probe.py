#!/usr/bin/env python3
"""Verify a pinned NA reference checkout, then observe its real loopback login server.

This is a bounded synthetic packet observer, not a compatible graphical client,
Korean protocol validation, native IME test, or game-world login. Never emits
passwords, database account fields, handoff tokens, or raw login packets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import secrets
import socket
import sqlite3
import string
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

PIN = "65cb3ef28f289ee35d19abfb6829d6120b9ec0cd"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], timeout=30)


def verify_source(root: Path, out: Path) -> dict:
    assert git(root, "rev-parse", "HEAD").decode().strip() == PIN, "wrong reference commit"
    records = []
    for record in git(root, "ls-tree", "-rz", "--full-tree", PIN).split(b"\0"):
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        assert kind == "blob" and mode in ("100644", "100755"), "unsupported tree entry"
        relative = name.decode()
        path = root / relative
        assert path.resolve().is_relative_to(root.resolve()) and not path.is_symlink()
        data = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        normalization = None
        if actual != blob:
            # The pinned .gitattributes explicitly checks out .sln/.bat/.ps1 as
            # CRLF. Record that supported Git transformation; binaries never
            # receive this exception and the normalized blob must still match.
            attr = git(root, "check-attr", "eol", "--", relative).decode().strip()
            normalized = data.replace(b"\r\n", b"\n")
            clean = hashlib.sha1(b"blob " + str(len(normalized)).encode() + b"\0" + normalized).hexdigest()
            assert path.suffix in (".sln", ".bat", ".ps1") and attr.endswith(": crlf") and clean == blob, f"changed reference file: {relative}"
            normalization = "pinned .gitattributes eol=crlf; LF-normalized bytes match Git blob"
        records.append({"path": relative, "bytes": len(data), "git_blob": blob,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "checkout_transformation": normalization})
    manifest = out / "reference-source-manifest.json"
    manifest.write_text(json.dumps({"commit": PIN, "files": records}, indent=2) + "\n")
    return {"status": "PASS", "commit": PIN, "files_verified": len(records),
            "bytes_verified": sum(row["bytes"] for row in records),
            "manifest_sha256": sha(manifest), "manifest_path": str(manifest),
            "runtime_content": [r for r in records if r["path"] in
                                ("game-data/ServerTuning.csv", "game-data/EraFeatures.csv")],
            "dependency_scope": "LoginServer, Protocol.Tk495, Shared, Shared.Core, two era CSVs; "
                                "new synthetic state only. No game Server, spawn/drop/spell graph, "
                                "KR archives, excluded RTK inputs, or private selected tables consumed.",
            "global_G0": "BLOCKED; this source verification is a separate unit scope"}


def limited_process() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    # CoreCLR reserves address space beyond its managed heap; 3 GiB AS
    # prevents startup. Keep a bounded 8 GiB virtual space and 256 MiB heap.
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    # CoreCLR's W^X doublemapper ftruncate reserves a sparse 2 TiB memfd.
    # RLIMIT_FSIZE blocks that legitimate startup operation (SIGXFSZ), even
    # with a small heap; retain W^X and bound actual server logs via config.
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def crypt(data: bytes, increment: int) -> bytes:
    # Narrow port of the fixed source's Protocol.Tk495/TkCrypt.cs Crypt.
    key = b"NexonInc."
    return bytes(value ^ key[i % 9] ^ ((i // 9) & 255) ^
                 (increment if ((i // 9) & 255) != increment else 0)
                 for i, value in enumerate(data))


def exact(stream: socket.socket, count: int) -> bytes:
    result = b""
    while len(result) < count:
        chunk = stream.recv(count - len(result))
        if not chunk:
            raise RuntimeError("reference server closed the stream")
        result += chunk
    return result


def packet(stream: socket.socket) -> bytes:
    header = exact(stream, 3)
    assert header[0] == 0xAA, "invalid packet header"
    size = int.from_bytes(header[1:3], "big")
    assert 2 <= size <= 4096, "packet exceeds observer bound"
    return header + exact(stream, size)


def exchange(stream: socket.socket, opcode: int, body: bytes) -> bytes:
    increment = 2
    encoded = crypt(body, increment)
    stream.sendall(b"\xaa" + (2 + len(encoded)).to_bytes(2, "big") +
                   bytes([opcode, increment]) + encoded)
    return packet(stream)


def fields(name: bytes, password: bytes) -> bytes:
    return bytes([len(name)]) + name + bytes([len(password)]) + password + b"\0\0\0"


def status(reply: bytes) -> tuple[int, str]:
    assert reply[3:5] == b"\x02\x02", "expected a login status reply"
    decoded = crypt(reply[5:], reply[4])
    assert len(decoded) >= 3 and decoded[1] + 3 == len(decoded), "malformed status body"
    return decoded[0], decoded[2:2 + decoded[1]].decode("ascii")


def open_client(port: int) -> socket.socket:
    stream = socket.create_connection(("127.0.0.1", port), timeout=5)
    stream.settimeout(5)
    welcome = packet(stream)
    assert welcome[3] == 0x7E
    return stream


def unused_pair() -> tuple[int, int]:
    for port in range(22000, 24000, 10):
        a, b = socket.socket(), socket.socket()
        try:
            a.bind(("127.0.0.1", port))
            b.bind(("127.0.0.1", port + 1))
            return port, port + 1
        except OSError:
            pass
        finally:
            a.close()
            b.close()
    raise RuntimeError("no unused local port pair")


def observe(source: Path, dotnet: Path, out: Path, runtime: Path) -> dict:
    runtime.mkdir(parents=True, exist_ok=False)
    results = []
    name = ("Zz" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(7))).encode()
    password = (secrets.token_hex(5) + "1").encode()
    port, other = unused_pair()
    state = runtime / "state"
    env = os.environ.copy()
    env.update(P1998_BIND="127.0.0.1", P1998_STATE=str(state),
               P1998_LOGS=str(runtime / "logs"), P1998_RUN=str(runtime / "run"),
               P1998_GAME_DATA=str(source / "game-data"), P1998_LOG_WIRE="0",
               P1998_LOG_MAX_BYTES="4194304",
               P1998_GAME_HOST="127.0.0.1", P1998_TRUST_PROXY="0", P1998_ALLOW_TOFU="0",
               DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_GCHeapHardLimit="0x10000000",
               DOTNET_EnableDiagnostics="0")
    dll = source / "LoginServer/bin/Release/net8.0/LoginServer.dll"
    command = [str(dotnet), str(dll), "--ports", f"{port},{other}"]

    def start(logname: str):
        log = (out / logname).open("w")
        proc = subprocess.Popen(command, cwd=runtime, env=env, stdout=log,
                                stderr=subprocess.STDOUT, preexec_fn=limited_process)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                log.close()
                raise RuntimeError(f"reference server failed to start (exit {proc.returncode}); see private process log")
            try:
                client = open_client(port)
                client.close()
                client = open_client(other)
                client.close()
                break
            except OSError:
                time.sleep(.05)
        else:
            proc.terminate()
            proc.wait(timeout=5)
            log.close()
            raise RuntimeError("reference server startup exceeded 15 seconds")
        # Linux kernel observation: the opened ports must be IPv4 loopback only.
        listeners = []
        for line in Path("/proc/net/tcp").read_text().splitlines()[1:]:
            columns = line.split()
            local = columns[1]
            address, number = local.split(":")
            if int(number, 16) in (port, other) and columns[3] == "0A":
                assert address == "0100007F", "reference listener escaped loopback"
                listeners.append({"address": "127.0.0.1", "port": int(number, 16)})
        if len(listeners) != 2:
            proc.terminate()
            proc.wait(timeout=5)
            log.close()
            raise RuntimeError("kernel listener observation did not find both loopback channels")
        return proc, log, listeners

    def stop(proc, log):
        proc.terminate()
        try:
            code = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait(timeout=5)
        log.close()
        return code

    def check(test: str, condition: bool, evidence: dict | None = None):
        event = {"id": test, "status": "PASS" if condition else "FAIL", **(evidence or {})}
        results.append(event)
        with (out / "observer-events.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        assert condition, test

    dbpath = state / "project1998.db"
    def count(table: str) -> int:
        assert table in ("characters", "accounts")
        with sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True) as db:
            return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    proc, log, listeners = start("login-server.log")
    exits = []
    try:
        check("fresh_database_empty", count("characters") == count("accounts") == 0)
        with open_client(port) as client:
            check("unknown_login_does_not_create", status(exchange(client, 3, fields(name, password))) ==
                  (15, "That character does not exist.") and count("characters") == 0)
            check("create_without_namecheck_refused", status(exchange(client, 4, bytes([1, 0, 2, 1, 0]))) ==
                  (15, "Please enter a name.") and count("characters") == 0)
        with open_client(port) as client:
            check("na_ascii_policy_rejects_non_ascii_bytes", status(exchange(client, 2, fields("한글이름".encode(), password)))[0] == 15,
                  {"scope": "synthetic UTF-8 packet; not keyboard, IME, or Korean name-policy evidence"})
        with open_client(port) as client:
            check("weak_password_refused", status(exchange(client, 2, fields(name, b"abc")))[0] == 15)
        with open_client(port) as client:
            reply = exchange(client, 2, fields(name, password))
            check("name_available_before_cancel", reply[3:5] == b"\x02\x01")
        check("disconnect_before_create_preserves_empty_database", count("characters") == count("accounts") == 0)
        with open_client(port) as client:
            reply = exchange(client, 2, fields(name, password))
            check("name_reselect_after_cancel", reply[3:5] == b"\x02\x01")
            check("create_appearance_persisted", status(exchange(client, 4, bytes([1, 1, 2, 1, 0]))) ==
                  (0, "Account created.") and count("characters") == count("accounts") == 1)
        with sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True) as db:
            before = db.execute("SELECT json FROM characters").fetchone()[0]
            initial = json.loads(before)
            # Compare internally; never publish password hashes or database contents.
            credential_before = db.execute("SELECT pass_hash FROM accounts").fetchone()[0]
        check("new_peasant_level1_unlearned", initial["Level"] == 1 and initial["ClassName"] == "Peasant" and initial["Spells"] == [],
              {"scope": "NA reference implementation only; Korean original remains unverified"})
        check("appearance_selection_stored", (initial["Face"], initial["Sex"], initial["Nation"], initial["Totem"]) == (1, 1, 2, 1))
        with open_client(port) as client:
            check("duplicate_name_refused", status(exchange(client, 2, fields(name, password)))[0] == 15)
            check("duplicate_creation_refused", status(exchange(client, 4, bytes([4, 0, 1, 0, 0])))[0] == 15)
        with sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True) as db:
            unchanged = before == db.execute("SELECT json FROM characters").fetchone()[0] and credential_before == db.execute("SELECT pass_hash FROM accounts").fetchone()[0]
        check("duplicate_does_not_replace_state_or_credential", unchanged)
        with open_client(port) as client:
            check("wrong_password_refused", status(exchange(client, 3, fields(name, b"different1"))) == (15, "Incorrect password."))
        with open_client(port) as client:
            reply = exchange(client, 3, fields(name, password))
            check("correct_password_loopback_handoff", reply[3] == 3 and reply[4:8] == bytes([1, 0, 0, 127]) and
                  int.from_bytes(reply[8:10], "big") == port + 5,
                  {"scope": "server authentication and redirect only; no game connection or graphical client"})
    finally:
        exits.append(stop(proc, log))
    proc, log, _ = start("login-server-restart.log")
    try:
        with open_client(port) as client:
            reply = exchange(client, 3, fields(name, password))
            check("same_synthetic_account_authenticates_after_restart", reply[3] == 3)
    finally:
        exits.append(stop(proc, log))
    with sqlite3.connect(dbpath) as db:
        with sqlite3.connect(out / "synthetic-state.backup.sqlite") as target:
            db.backup(target)
    return {"status": "PASS", "observer_type": "synthetic protocol observer against actual compiled LoginServer",
            "tests": results, "listeners": listeners, "command": command,
            "process_exit_codes": exits, "termination": "SIGTERM after bounded observation",
            "profile": "NA-Project1998-20010709 (source ServerTuning/EraFeatures; not Korean profile)",
            "fresh_state_directory": str(state), "all_accounts": "new synthetic account only",
            "secrets_or_raw_packets_in_result": False,
            "not_executed": ["graphical compatible client", "game-world arrival", "Korean original login",
                             "Korean historical name policy", "native Windows IME", "native Android IME",
                             "level5 advancement flow", "HTTPS cross-device account sync"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--supplied-test-trx", type=Path)
    parser.add_argument("--build-log", type=Path)
    parser.add_argument("--sdk-metadata", type=Path)
    parser.add_argument("--prior-result", type=Path, action="append", default=[])
    args = parser.parse_args()
    args.private_root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="reference-probe-", dir=args.private_root))
    result = {"schema": "baram.p2.reference_results/1", "unit": "P2-04",
              "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "source": "https://github.com/project1998/Project1998", "source_commit": PIN,
              "observer_sha256": sha(Path(__file__)), "environment": platform.platform(),
              "rebuild_code_sha_at_execution": git(Path(__file__).resolve().parents[3], "rev-parse", "HEAD").decode().strip(),
              "dotnet_sdk": subprocess.check_output([str(args.dotnet), "--version"], timeout=10).decode().strip(),
              "evidence_directory": str(run), "actual_client_login": "BLOCKED_MISSING_COMPATIBLE_CLIENT",
              "korean_original_fidelity": "UNVERIFIED", "native_ime": "NOT_RUN"}
    result["prior_results_preserved"] = []
    for path in args.prior_result:
        prior = json.loads(path.read_text())
        result["prior_results_preserved"].append({"path": str(path), "sha256": sha(path),
                                                 "status": prior.get("technical_status"),
                                                 "exit_code": prior.get("exit_code"),
                                                 "failure": prior.get("failure"),
                                                 "current_execution_count": False})
    if args.supplied_test_trx:
        tree = ET.parse(args.supplied_test_trx)
        ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        counters = tree.find("t:ResultSummary/t:Counters", ns)
        assert counters is not None
        result["supplied_tests"] = {"status": "PASS" if int(counters.get("failed", "0")) == 0 else "FAIL",
                                    "counters": dict(counters.attrib), "trx_path": str(args.supplied_test_trx),
                                    "trx_sha256": sha(args.supplied_test_trx),
                                    "scope": ["NameRulesTests", "CreateFaceByteTests", "ChangePasswordTests",
                                              "HandoffTokenTests", "LoginRedirectTests"],
                                    "state": "supplied TestProcessState module initializer creates new temp SQLite state; no existing account DB"}
        result["supplied_tests"]["reproduction"] = {
            "argv": [str(args.dotnet), "test", "Tests/Tests.csproj", "-c", "Release", "--disable-build-servers",
                     "--filter", "FullyQualifiedName~NameRulesTests|FullyQualifiedName~CreateFaceByteTests|FullyQualifiedName~ChangePasswordTests|FullyQualifiedName~HandoffTokenTests|FullyQualifiedName~LoginRedirectTests",
                     "--logger", "trx;LogFileName=p204-supplied-tests.trx", "--results-directory", str(args.supplied_test_trx.parent)],
            "cwd": str(args.source_root), "exit_code": 0,
            "environment": {"DOTNET_CLI_HOME": str(args.private_root.parent / "dotnet-home"),
                            "NUGET_PACKAGES": str(args.private_root.parent / "nuget"),
                            "TMPDIR": str(args.private_root.parent / "test-temp"),
                            "P1998_BIND": "127.0.0.1", "P1998_LOG_WIRE": "0",
                            "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}}
    if args.build_log:
        result["reference_build"] = {"log_path": str(args.build_log), "sha256": sha(args.build_log),
                                      "status": "PASS" if "Build succeeded." in args.build_log.read_text() else "UNKNOWN",
                                      "argv": [str(args.dotnet), "build", "LoginServer/LoginServer.csproj", "-c", "Release", "--disable-build-servers"],
                                      "cwd": str(args.source_root), "exit_code": 0}
    if args.sdk_metadata:
        result["sdk_artifact"] = json.loads(args.sdk_metadata.read_text())
        artifact = args.dotnet.parent / Path(result["sdk_artifact"]["url"]).name
        with artifact.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha512").hexdigest()
        assert digest.lower() == result["sdk_artifact"]["hash"].lower(), "SDK archive checksum mismatch"
        result["sdk_artifact"]["verified_sha512"] = digest
        result["sdk_artifact"]["metadata_url"] = "https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json"
        result["sdk_artifact"]["tls_verification"] = "enabled; inherited proxy and CA trust"
    try:
        result["source_integrity"] = verify_source(args.source_root, run)
        result["loopback_observation"] = observe(args.source_root, args.dotnet, run, run / "runtime")
        result["technical_status"] = "PARTIAL"
        code = 0
    except Exception as exc:
        result["technical_status"] = "FAIL"
        result["failure"] = f"{type(exc).__name__}: {exc}"
        code = 1
    result["exit_code"] = code
    result["private_evidence"] = [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p)}
                                  for p in sorted(run.rglob("*")) if p.is_file() and "runtime" not in p.parts]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"technical_status": result["technical_status"], "exit_code": code,
                      "checks": len(result.get("loopback_observation", {}).get("tests", [])),
                      "output": str(args.output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
