#!/usr/bin/env python3
"""Repackage a SHA-pinned verified Linux release as a private Windows x64 game.

Build tools are needed only here. The resulting ZIP needs no Python or Godot
installation. No new Work data, user saves, or unlicensed source code is added.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "4.6.3"
MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
KEEP = ("game/", "private_assets/", "private_content/", "licenses/")
PLAYER_NAME = "바람의나라.exe"
PACKAGE_NAME = "바람의나라_Windows64_개인용"
README = """바람의나라 · 개인용 오프라인 게임 (Windows 64비트)

1. ZIP을 폴더에 '모두 압축 풀기' 하세요.
2. 그 폴더 안의 '바람의나라.exe'를 더블클릭하세요.
   Godot, Python 설치와 인터넷 연결은 필요 없습니다.
   private_assets와 private_content 폴더는 실행 파일과 함께 두세요.
   최초 로딩은 잠시 걸릴 수 있습니다.

방향키/WASD: 이동   Shift+방향키: 방향   Space: 공격
Enter/F: 대화·출입구   G: 줍기   I: 물품(E 장착/U 사용)
O: 개별 장비(E 장착/X 해제/N 선택 강화)   K: 기술   1~3: 기술 단축키
F5: 저장   F6: 복구   Esc: 메뉴   Q: 종료
길잡이에게 사냥터·실내 이동을 부탁할 수 있습니다.
마을의 '추가 지역 길목'에서 연결된 Work 지역으로 이동합니다.

저장 파일: %LOCALAPPDATA%\\BaramSinglePlayer\\saves\\v2\\character.json
저장은 게임 폴더와 별개이며 새 ZIP을 풀어도 지워지지 않습니다.
이 ZIP에는 사용자 저장이 없습니다. 정상 백업 1개를 유지합니다.
손상 또는 지원하지 않는 저장을 새 게임으로 덮어쓰지 않습니다.
Linux 저장을 옮길 때는 게임을 종료하고 원본을 보존한 사본만 위 경로에
복사하세요. 이미 Windows 저장이 있으면 먼저 별도 복사해 보존하세요.

현재 검증된 Linux 게임의 코드·콘텐츠·그래픽·음향을 재사용했습니다.
새 Work 패키지는 섞지 않았습니다. 기존 미확보 자산과 미완료 콘텐츠는
그대로 구분되며 전체 원작 복원·네 직업 자연 육성 완주는 미검증입니다.
Windows 파일 제작과 Windows에서 직접 플레이한 검증은 다릅니다.
정확한 검증 상태는 PACKAGE_MANIFEST.json 및 실행검증.json을 보세요.

원본·파생 자산은 개인용 비공개 자료입니다. 공개 업로드하지 마세요.
Godot 및 폰트 라이선스는 licenses 폴더에 보존했습니다.
"""


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_path(name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or ".." in p.parts or "\\" in name
            or ":" in name or "\x00" in name or str(p) != name):
        raise ValueError("Unsafe package member: " + repr(name))
    return p


def pe_info(path):
    data = Path(path).read_bytes()
    if data[:2] != b"MZ" or len(data) < 0x40:
        raise ValueError("Windows engine is not PE")
    offset = struct.unpack_from("<I", data, 0x3c)[0]
    if offset + 96 > len(data) or data[offset:offset+4] != b"PE\0\0":
        raise ValueError("Invalid PE header")
    machine = struct.unpack_from("<H", data, offset+4)[0]
    magic = struct.unpack_from("<H", data, offset+24)[0]
    subsystem = struct.unpack_from("<H", data, offset+24+68)[0]
    if (machine, magic, subsystem) != (0x8664, 0x20b, 2):
        raise ValueError("Expected AMD64 PE32+ Windows GUI template")
    return dict(machine="AMD64", optional_header="PE32+", subsystem="WINDOWS_GUI",
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def extract_source(archive, expected, destination):
    if sha256(archive) != expected:
        raise ValueError("Verified Linux ZIP SHA256 mismatch; input not used")
    destination.mkdir()
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > 10000:
            raise ValueError("Archive member limit")
        seen = set()
        total = 0
        for member in entries:
            safe_path(member.filename.rstrip("/"))
            if member.filename in seen:
                raise ValueError("Duplicate ZIP member: " + member.filename)
            seen.add(member.filename)
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("ZIP symlink rejected")
            total += member.file_size
            if member.file_size > MAX_MEMBER or total > MAX_TOTAL:
                raise ValueError("ZIP size limit")
        candidates = [m.filename for m in entries if m.filename.endswith("/PACKAGE_MANIFEST.json")]
        if len(candidates) != 1:
            raise ValueError("Expected one source package manifest")
        prefix = candidates[0].removesuffix("PACKAGE_MANIFEST.json")
        manifest = json.loads(z.read(candidates[0]))
        if manifest.get("contains_user_saves") is not False or manifest.get("private_only") is not True:
            raise ValueError("Input must be private and exclude user saves")
        records = {}
        for row in manifest["files"]:
            name = str(safe_path(row["path"]))
            if name in records:
                raise ValueError("Duplicate source manifest path")
            records[name] = row
        for name, row in records.items():
            if not name.startswith(KEEP):
                continue
            member = z.getinfo(prefix+name)
            if member.file_size != row["bytes"]:
                raise ValueError("Source member size mismatch: " + name)
            raw = z.read(member)
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Source member SHA mismatch: " + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    return manifest


def verify_private_equivalence(source, stage):
    rows = [r for r in source["files"] if r["path"].startswith(("private_assets/", "private_content/"))]
    expected = {r["path"] for r in rows}
    present = {p.relative_to(stage).as_posix() for folder in ("private_assets", "private_content")
               for p in (stage/folder).rglob("*") if p.is_file()}
    if expected != present:
        raise ValueError("Private asset/content membership changed")
    for r in rows:
        p = stage/r["path"]
        if p.stat().st_size != r["bytes"] or sha256(p) != r["sha256"]:
            raise ValueError("Private content changed: " + r["path"])
    return dict(status="PASS_EXACT_VERIFIED_LINUX_PRIVATE_BYTES", files=len(rows),
                private_assets=sum(r["path"].startswith("private_assets/") for r in rows),
                private_content=sum(r["path"].startswith("private_content/") for r in rows),
                bytes=sum(r["bytes"] for r in rows))


def json_write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def write_archive(stage, archive):
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, PACKAGE_NAME+"/"+path.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise ValueError("Windows ZIP CRC failed")


def finalize(args):
    """Create a fresh delivery copy after executed checks; never invent a native PASS."""
    original = json.loads(Path(args.build_report).read_text(encoding="utf-8"))
    archive = Path(original["archive"])
    source = Path(original["stage"])
    if sha256(archive) != original["sha256"]:
        raise ValueError("Initial Windows ZIP changed")
    manifest = json.loads((source/"PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        member = source/str(safe_path(row["path"]))
        if member.stat().st_size != row["bytes"] or sha256(member) != row["sha256"]:
            raise ValueError("Initial player files changed: "+row["path"])
    evidence = []
    modes = set()
    for report_path in args.evidence_report:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        if report.get("status") != "PASS_EXECUTED_SCREEN_INPUT_AND_RESTART":
            raise ValueError("Requires actually executed GUI checks and fresh-process restart")
        runs = []
        for run in report["runs"]:
            game = json.loads(Path(run["game_report"]).read_text(encoding="utf-8"))
            if (run["exit_code"] != 0 or game["status"] != "PASS_EXECUTED_SCREEN_INPUT"
                    or game["game_build"] != manifest["build"]["commit"]
                    or game["content_version"] != manifest["build"]["content_version"]
                    or any(c["status"] != "PASS" for c in game["checks"])
                    or not run["x11_captures"]
                    or any(c["status"] != "PASS" for c in run["x11_captures"])):
                raise ValueError("Evidence does not match frozen game or contains failure")
            modes.add(run["mode"])
            runs.append(dict(mode=run["mode"], checks=len(game["checks"]),
                             check_names=[c["name"] for c in game["checks"]],
                             report_sha256=sha256(run["game_report"]),
                             screen_checks=len(run["x11_captures"]),
                             audio_mix=run["audio_mix"]["status"]))
        evidence.append(dict(file=Path(report_path).name, sha256=sha256(report_path),
                             status=report["status"], platform="LINUX_GODOT_READS_EMBEDDED_PCK_NOT_WINDOWS_PE_EXECUTION", runs=runs))
    if not {"work-core", "work-restart", "windows-loot", "windows-loot-restart"} <= modes:
        raise ValueError("Missing baseline input, actual pickup, or restart evidence")
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output/PACKAGE_NAME
    if stage.exists():
        raise ValueError("Preserve prior player package; choose fresh output")
    shutil.copytree(source, stage)
    checks = json.loads((stage/"실행검증.json").read_text(encoding="utf-8"))
    checks.update(linux_exported_pck_execution="PASS", windows_native_execution="NOT_RUN",
                  controls_combat_npc_loot_restart="PASS_LINUX_EMBEDDED_PCK_ONLY",
                  tested_exe_sha256=sha256(stage/PLAYER_NAME), evidence=evidence)
    json_write(stage/"실행검증.json", checks)
    manifest.update(windows_native_execution="NOT_RUN", linux_embedded_pck_checks="PASS",
                    finalization_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                    delivery="NOT_DELIVERED", evidence=evidence,
                    files=[dict(path=p.relative_to(stage).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
                           for p in sorted(stage.rglob("*")) if p.is_file() and p != stage/"PACKAGE_MANIFEST.json"])
    json_write(stage/"PACKAGE_MANIFEST.json",manifest)
    target=output/(PACKAGE_NAME+".zip")
    write_archive(stage,target)
    result=dict(status="PASS_PACKAGING_AND_LINUX_EMBEDDED_PCK_CHECKS", archive=str(target),
                bytes=target.stat().st_size, sha256=sha256(target), stage=str(stage),
                build=manifest["build"], packager_commit=manifest["packager_commit"],
                finalization_commit=manifest["finalization_commit"],
                private_equivalence=manifest["private_equivalence"],
                windows_native_execution="NOT_RUN", delivery="NOT_DELIVERED", evidence=evidence)
    json_write(args.report,result)
    print(json.dumps(result,ensure_ascii=False))


def build(args):
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if branch != "codex/game-core":
        raise ValueError("Package only from Codex branch")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise ValueError("Commit reviewed packaging code before freezing")
    engine = Path(args.template).resolve()
    if sha256(engine) != args.template_sha256:
        raise ValueError("Windows template SHA256 mismatch")
    pe = pe_info(engine)
    version = subprocess.check_output([args.godot, "--headless", "--version"], text=True).strip()
    if not version.startswith(VERSION+"."):
        raise ValueError("Packaging engine version must match 4.6.3")
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output/PACKAGE_NAME
    project = output/"export-source"
    if stage.exists() or project.exists():
        raise ValueError("Preserve existing package; choose fresh output")
    source = extract_source(Path(args.source), args.source_sha256, stage)
    equivalence = verify_private_equivalence(source, stage)
    shutil.move(str(stage/"game"), project)
    for name in ("windows_bootstrap.gd", "windows_bootstrap.tscn"):
        shutil.copy2(ROOT/"game"/name, project/name)
    cfg = (project/"project.godot").read_text(encoding="utf-8")
    if 'run/main_scene="res://main.tscn"' not in cfg:
        raise ValueError("Source game main scene changed")
    cfg = cfg.replace('run/main_scene="res://main.tscn"', 'run/main_scene="res://windows_bootstrap.tscn"')
    (project/"project.godot").write_text(cfg, encoding="utf-8")
    # Only the packaging scene changes. All original game scripts/data stay frozen.
    presets = '''[preset.0]
name="Windows64"
platform="Windows Desktop"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter="*.json"
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=1

[preset.0.options]
custom_template/debug=""
custom_template/release=TEMPLATE
binary_format/embed_pck=true
binary_format/architecture="x86_64"
debug/export_console_wrapper=0
codesign/enable=false
application/modify_resources=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
'''
    (project/"export_presets.cfg").write_text(presets.replace("TEMPLATE", json.dumps(str(engine))), encoding="utf-8")
    env = dict(os.environ)
    for variable, folder in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache")):
        directory = output/"build-local"/folder
        directory.mkdir(parents=True, exist_ok=True)
        env[variable] = str(directory)
    commands = [[args.godot, "--headless", "--editor", "--path", str(project), "--import", "--quit"],
                [args.godot, "--headless", "--path", str(project), "--export-release", "Windows64", str(stage/PLAYER_NAME)],
                [args.godot, "--headless", "--path", str(project), "--export-pack", "Windows64", str(output/"verification-only.pck")]]
    for index, command in enumerate(commands):
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=240)
        (output/("export-"+str(index)+".log")).write_text(result.stdout+result.stderr, encoding="utf-8")
        if result.returncode or "SCRIPT ERROR:" in result.stdout+result.stderr or re.search(r"^ERROR:", result.stdout+result.stderr, re.MULTILINE):
            raise ValueError("Godot export failed; inspect export-"+str(index)+".log")
    pe_info(stage/PLAYER_NAME)
    if (stage/PLAYER_NAME).stat().st_size <= engine.stat().st_size:
        raise ValueError("Exported EXE must contain embedded game PCK")
    (stage/"처음읽기.txt").write_text(README, encoding="utf-8-sig")
    checks = dict(windows_native_execution="NOT_RUN", linux_exported_pck_execution="NOT_RUN",
                  controls_combat_npc_loot_restart="NOT_RUN_ON_EXPORTED_BUILD",
                  private_equivalence=equivalence, windows_pe=pe)
    json_write(stage/"실행검증.json", checks)
    manifest = dict(private_only=True, contains_user_saves=False,
                    source_linux_sha256=args.source_sha256, build=source["build"],
                    packager_commit=commit, packaging_engine=version,
                    windows_template=pe, windows_native_execution="NOT_RUN",
                    persistent_save="%LOCALAPPDATA%\\BaramSinglePlayer\\saves\\v2\\character.json",
                    imports=source["imports"], private_equivalence=equivalence,
                    files=[dict(path=p.relative_to(stage).as_posix(), bytes=p.stat().st_size, sha256=sha256(p))
                           for p in sorted(stage.rglob("*")) if p.is_file()])
    json_write(stage/"PACKAGE_MANIFEST.json", manifest)
    archive = output/(PACKAGE_NAME+".zip")
    write_archive(stage, archive)
    report = dict(status="PASS_WINDOWS_X64_EXPORT_NOT_NATIVE_EXECUTION", archive=str(archive),
                  bytes=archive.stat().st_size, sha256=sha256(archive), stage=str(stage),
                  project=str(project), verification_pck=str(output/"verification-only.pck"),
                  build=source["build"], packager_commit=commit, private_equivalence=equivalence,
                  windows_native_execution="NOT_RUN", delivery="NOT_DELIVERED")
    json_write(args.report, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true", help="Repackage only after executed embedded-PCK GUI reports")
    parser.add_argument("--build-report")
    parser.add_argument("--evidence-report", action="append", default=[])
    for option in ("source", "source-sha256", "template", "template-sha256", "out", "report"):
        parser.add_argument("--"+option, required=option in ("out","report"))
    parser.add_argument("--godot", default="/usr/local/bin/godot")
    options=parser.parse_args()
    if options.finalize:
        if not options.build_report or not options.evidence_report:
            parser.error("Finalization requires --build-report and --evidence-report")
        finalize(options)
    else:
        if any(not getattr(options,key) for key in ("source","source_sha256","template","template_sha256")):
            parser.error("Build requires SHA-pinned --source and --template")
        build(options)
