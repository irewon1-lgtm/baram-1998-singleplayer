#!/usr/bin/env python3
"""Package an exact frozen r16 export; native execution remains a separate gate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

PACKAGE = 'com.irewon.baram.p3repair20261016'
USER_DIR = 'baram_rebuild_p3repair_001'
CERT = 'c0bc3989d93d7b9443bbfa59281797a48e2b020e5da4b1dc91858768b35ccd05'


def digest(path: Path) -> str:
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in frozen input')
        if path.is_file() and '.godot' not in path.relative_to(root).parts:
            result[path.relative_to(root).as_posix()] = digest(path)
    if not result:
        raise ValueError('Empty frozen input')
    return result


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def checked_artifact(row: dict, parent: Path) -> Path:
    path = Path(row['path']).resolve()
    if parent not in path.parents or not path.is_file():
        raise ValueError('Export artifact is outside its explicit build directory')
    if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Export artifact differs from its immutable receipt')
    return path


def safe_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError('Unsafe archive path')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['project', 'runtime', 'windows-export', 'android-export', 'freeze', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--version-code', type=int, default=8)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.source_commit) or args.version_code != 8:
        raise ValueError('r16 requires an exact source SHA and version code8')
    project, runtime = args.project.resolve(), args.runtime.resolve()
    windows_dir, android_dir = args.windows_export.resolve(), args.android_export.resolve()
    windows, android, freeze = [read(p) for p in [windows_dir / 'EXPORT_RECEIPT.json',
        android_dir / 'EXPORT_RECEIPT.json', args.freeze]]
    for receipt, target in [(windows, 'Windows'), (android, 'Android')]:
        if receipt.get('result') != 'PASS_EXPORT_ONLY' or receipt.get('target') != target:
            raise ValueError('A successful exact export receipt is required')
        if receipt.get('source_commit') != args.source_commit:
            raise ValueError('Export source SHA differs from the approved freeze')
        if not receipt.get('sources_unchanged') or not receipt.get('runtime_unchanged'):
            raise ValueError('Export did not preserve its frozen inputs')
        if receipt.get('preserved_user_dir') != USER_DIR or receipt.get('installed_package') != PACKAGE:
            raise ValueError('Installed identity changed')
    for key in ['source_snapshot', 'runtime_snapshot', 'source_content_fingerprint',
                'runtime_manifest_sha256', 'gameplay_content_sha256']:
        if windows.get(key) != android.get(key):
            raise ValueError('Windows/Android exports differ: ' + key)
    if freeze.get('source_commit') != args.source_commit:
        raise ValueError('Freeze source SHA differs')
    for key in ['source_snapshot', 'runtime_snapshot']:
        if freeze.get(key) != windows.get(key):
            raise ValueError('Freeze differs from both actual export snapshots: ' + key)
    if snapshot(project) != windows['source_snapshot'] or snapshot(runtime) != windows['runtime_snapshot']:
        raise ValueError('Current frozen inputs differ from the actual exports')
    if (digest(runtime / 'runtime.json') != windows['runtime_manifest_sha256']
            or digest(runtime / 'gameplay_content.json') != windows['gameplay_content_sha256']):
        raise ValueError('Runtime manifest/content hash differs')
    manifest = android.get('final_apk_manifest', {})
    if (manifest.get('package') != PACKAGE or manifest.get('version_code') != 8
            or manifest.get('version_name') != '0.3.1-g2-r16-candidate'
            or android.get('retained_signer_sha256') != CERT
            or android.get('final_apk_signer_matches_retained') is not True
            or android.get('new_signing_key_created') is not False):
        raise ValueError('Android package/version/retained-signing contract failed')
    exe = checked_artifact(windows['artifact'], windows_dir)
    checked_artifact(windows['windows_zip'], windows_dir)
    original_apk = checked_artifact(android['artifact'], android_dir)
    for name in windows['runtime_snapshot']:
        safe_name(name)
        if (runtime / name).suffix.lower() not in {'.png', '.json', '.wav'}:
            raise ValueError('Only generated runtime PNG/JSON/WAV may be packaged')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    apk = out / 'baram-G2-r16-Android-candidate.apk'
    archive = out / 'baram-G2-r16-Windows64-candidate.zip'
    pack = out / 'baram-G2-r16-private-runtime.zip'
    if any(p.exists() for p in [apk, archive, pack]):
        raise ValueError('Use fresh candidate filenames; do not overwrite an earlier package')
    guide = ('바람의나라 G2 r16 설치 후보\n\n'
        'ZIP 전체를 새 폴더에 풀고 baram-p3-playable.exe를 실행하세요.\n'
        'EXE-SHA256.txt는 동봉 실행 파일의 SHA-256입니다.\n'
        '기존 P3 보수본의 사용자 저장 경로를 유지합니다. 업데이트 전 게임을 종료하세요.\n'
        '저장 위치: %APPDATA%\\baram_rebuild_p3repair_001\\gameplay-p3\\characters\n'
        '이어 하기로 기존 캐릭터를 선택합니다. 삭제 설치로 서명 오류를 해결하지 마세요.\n\n'
        '방향키/지면 클릭: 이동, Space: 공격, Enter: 대화, Z: 줍기, Tab: 우측 패널, Esc: 닫기.\n'
        '현재 파일은 설치 후보이며 실제 Windows·Android 실행/업데이트 검증은 별도입니다.\n')
    shutil.copy2(original_apk, apk)
    exe_hash = digest(exe)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(exe, 'baram-p3-playable.exe')
        z.writestr('START.txt', guide)
        z.writestr('EXE-SHA256.txt', exe_hash + '  baram-p3-playable.exe\n')
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory(prefix='baram-r16-clean-extract-') as temp:
        if set(z.namelist()) != {'baram-p3-playable.exe', 'START.txt', 'EXE-SHA256.txt'}:
            raise ValueError('Unexpected Windows ZIP payload')
        for info in z.infolist():
            safe_name(info.filename)
        z.extractall(temp)
        clean = Path(temp)
        if digest(clean / 'baram-p3-playable.exe') != exe_hash:
            raise ValueError('Clean-directory EXE differs from exported bytes')
        if (clean / 'START.txt').read_text() != guide:
            raise ValueError('Korean installation guide differs')
        clean_names = sorted(p.name for p in clean.iterdir())
    with zipfile.ZipFile(pack, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, expected in windows['runtime_snapshot'].items():
            file = runtime / name
            if digest(file) != expected:
                raise ValueError('Frozen runtime changed during packaging')
            z.write(file, name)
    with zipfile.ZipFile(pack) as z:
        if set(z.namelist()) != set(windows['runtime_snapshot']):
            raise ValueError('Runtime package differs from export snapshot')
        for name, expected in windows['runtime_snapshot'].items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError('Runtime ZIP member differs: ' + name)
    if (digest(apk) != android['artifact']['sha256']
            or snapshot(project) != windows['source_snapshot']
            or snapshot(runtime) != windows['runtime_snapshot']):
        raise ValueError('Inputs or APK changed during packaging')
    artifacts = [{'filename': p.name, 'local_path': str(p), 'bytes': p.stat().st_size,
                  'sha256': digest(p), 'status': 'BUILT_NOT_NATIVE_EXECUTION_VERIFIED'}
                 for p in [apk, archive, pack]]
    result = {'schema': 'baram.g2.r16.packaged-artifacts/1', 'source_commit': args.source_commit,
        'source_content_fingerprint': windows['source_content_fingerprint'],
        'runtime_manifest_sha256': windows['runtime_manifest_sha256'],
        'content_sha256': windows['gameplay_content_sha256'], 'windows_exe_sha256': exe_hash,
        'artifacts': artifacts, 'installed_package': PACKAGE, 'user_directory': USER_DIR,
        'version_code': 8, 'signer_sha256': CERT, 'private_keys_or_user_saves_or_raw_DAT_in_artifacts': False,
        'clean_directory_structural_check': {'status': 'PASS', 'files': clean_names,
            'exe_hash_matches_export': True, 'scope': 'Archive structure/extraction only; not EXE execution'},
        'runtime_archive_verified_members': len(windows['runtime_snapshot']),
        'native_execution': 'NOT_RUN', 'native_update': 'NOT_RUN'}
    (out / 'r16-packaging-provenance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'artifacts': artifacts, 'native_execution': 'NOT_RUN'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
