#!/usr/bin/env python3
"""Stage exact exported native candidates in an existing private input vault.

Uses the authenticated HostedAppsClient transport supplied by the Library skill;
credentials and binary data are never printed. Upload creates a detached commit.
Publishing its branch ref is a separate explicit command with an expected lease.
This utility neither launches a game nor marks native verification as passed.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from threading import Lock


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def file_digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(args) -> None:
    if args.session.exists() and any(args.session.iterdir()):
        raise ValueError('Use an empty new session directory; never overwrite a session')
    args.session.mkdir(parents=True, exist_ok=True, mode=0o700)
    windows = read(args.windows_export / 'EXPORT_RECEIPT.json')
    android = read(args.android_export / 'EXPORT_RECEIPT.json')
    if any(r.get('result') != 'PASS_EXPORT_ONLY' for r in [windows, android]):
        raise ValueError('Both exports must have successful exporter receipts')
    common = ['source_commit', 'source_content_fingerprint', 'runtime_manifest_sha256']
    for key in common:
        if windows.get(key) != android.get(key):
            raise ValueError('Exports are not the same candidate: ' + key)
        if not re.fullmatch('[0-9a-f]{' + ('40' if key == 'source_commit' else '64') + '}', windows.get(key, '')):
            raise ValueError('Missing exact candidate provenance: ' + key)
    if not re.fullmatch(r'v2-native/[A-Za-z0-9._/-]+', args.prefix) or '..' in args.prefix.split('/'):
        raise ValueError('Use a safe isolated v2-native prefix')
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private = args.session / 'session-private-key.pem'
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    private.chmod(0o600)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode('ascii')
    (args.session / 'session-public-key.pem').write_text(public, encoding='ascii')
    files = {'windows': Path(windows['windows_zip']['path']), 'new': Path(android['artifact']['path']), 'old': args.old_apk.resolve()}
    expected = {'windows': windows['windows_zip']['sha256'], 'new': android['artifact']['sha256']}
    chunks = []
    contract = {}
    for label, path in files.items():
        measured = file_digest(path)
        if label in expected and measured != expected[label]:
            raise ValueError('Export artifact bytes differ from receipt: ' + label)
        parts = []
        with path.open('rb') as stream:
            index = 0
            while block := stream.read(2 * 1024 * 1024):
                name = f'{label}-{index:04}.b64'
                local = args.session / name
                encoded = base64.b64encode(block)
                local.write_bytes(encoded)
                row = {'path': args.prefix + '/' + name, 'local': str(local.resolve()),
                       'sha256': digest(block), 'encoded_sha256': digest(encoded), 'bytes': len(encoded)}
                chunks.append(row)
                parts.append({'path': row['path'], 'sha256': row['sha256']})
                index += 1
        contract[label] = {'sha256': measured, 'bytes': path.stat().st_size, 'chunks': parts}
    shared = {k: windows[k] for k in common}
    manifests = {
        'windows-manifest.json': {**shared, 'schema': 'baram.v2.native_chunks/1',
                                  'zip_sha256': contract['windows']['sha256'], 'chunks': contract['windows']['chunks']},
        'android-manifest.json': {**shared, 'schema': 'baram.v2.android_native_chunks/1',
                                  'new_apk_sha256': contract['new']['sha256'], 'old_apk_sha256': contract['old']['sha256'],
                                  'new_apk_chunks': contract['new']['chunks'], 'old_apk_chunks': contract['old']['chunks']},
    }
    for name, value in manifests.items():
        write(args.session / name, value)
    request_shared = {**shared, 'encryption_public_key_pem': public,
                      'npc_probe': {'map_id': 'gp:map:domestic_city', 'x': 27, 'y': 33}}
    requests = {
        'NATIVE_REQUEST.json': {**request_shared, 'schema': 'baram.v2.native_request/1',
                                'private_manifest_path': args.prefix + '/windows-manifest.json',
                                'windows_zip_sha256': contract['windows']['sha256'],
                                'windows_exe_sha256': windows['artifact']['sha256']},
        'ANDROID_NATIVE_REQUEST.json': {**request_shared, 'schema': 'baram.v2.android_native_request/1',
                                        'private_manifest_path': args.prefix + '/android-manifest.json',
                                        'new_apk_sha256': contract['new']['sha256'], 'old_apk_sha256': contract['old']['sha256'],
                                        'package': 'com.irewon.baram.p3repair20261016', 'old_version_code': 3, 'new_version_code': 4},
    }
    for name, value in requests.items():
        write(args.session / (name + '.template'), value)
    write(args.session / 'SESSION.json', {'schema': 'baram.v2.native_staging_session/1', **shared,
          'prefix': args.prefix, 'chunks': chunks, 'manifest_names': list(manifests),
          'request_names': list(requests), 'native_execution': 'NOT_RUN', 'new_paid_resources': False})
    print(json.dumps({'prepared_chunks': len(chunks), 'source_commit': shared['source_commit'], 'native_execution': 'NOT_RUN'}))


class Transport:
    def __init__(self, helper: Path):
        spec = importlib.util.spec_from_file_location('baram_hosted_apps', helper)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.client = module.HostedAppsClient()
        cursor = None
        for _ in range(100):
            listed = self.client._rpc('tools/list', {'cursor': cursor} if cursor else {})
            for tool in listed.get('tools', []):
                if tool.get('name') == 'github_create_blob':
                    self.connector = tool['_meta']['connector_id']
                    return
            cursor = listed.get('nextCursor', listed.get('next_cursor'))
            if not cursor:
                break
        raise ValueError('Existing authenticated GitHub connector is unavailable')

    def call(self, name: str, **arguments) -> dict:
        result = self.client.call_tool(self.connector, name, arguments)
        value = result.get('structuredContent')
        if not isinstance(value, dict):
            texts = [x.get('text', '') for x in result.get('content', []) if x.get('type') == 'text']
            for text in texts:
                try:
                    parsed = json.loads(text)
                except ValueError:
                    continue
                if isinstance(parsed, dict):
                    value = parsed
                    break
        if not isinstance(value, dict):
            raise ValueError('Missing structured GitHub tool result: ' + name)
        if isinstance(value.get('content'), str):
            try:
                return json.loads(value['content'])
            except ValueError:
                pass
        return value

    def private_repository(self, repository: str) -> None:
        result = self.call('get_repo', repository_full_name=repository)
        if result.get('visibility') != 'private':
            raise ValueError('Inputs may only be staged in the existing private vault')


def upload(args) -> None:
    session = read(args.session / 'SESSION.json')
    api = Transport(args.helper)
    api.private_repository(args.repository)
    if args.branch == 'main':
        raise ValueError('Never publish native staging inputs to vault main')
    branch_url = f'https://api.github.com/repos/{args.repository}/branches/{args.parent_ref}'
    branch = api.call('fetch', url=branch_url)
    parent = branch['commit']['sha']
    base_tree = branch['commit']['commit']['tree']['sha']
    state_path = args.session / 'UPLOAD.json'
    state = read(state_path) if state_path.exists() else {'schema': 'baram.v2.native_staging_upload/1',
        'repository': args.repository, 'branch': args.branch, 'parent_ref': args.parent_ref, 'parent': parent, 'base_tree': base_tree,
        'blobs': {}, 'published': False}
    if state['repository'] != args.repository or state['parent'] != parent:
        raise ValueError('Vault HEAD changed; inspect and coordinate before continuing')
    lock = Lock()

    def one(row):
        local = Path(row['local'])
        encoded = local.read_bytes()
        if digest(encoded) != row['encoded_sha256']:
            raise ValueError('Local immutable chunk changed: ' + row['path'])
        result = api.call('create_blob', repository_full_name=args.repository,
                          content=encoded.decode('ascii'), encoding='utf-8')
        sha = result['sha']
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('Unexpected blob SHA')
        with lock:
            state['blobs'][row['path']] = sha
            write(state_path, state)
        return row['path']

    pending = [x for x in session['chunks'] if x['path'] not in state['blobs']]
    with ThreadPoolExecutor(max_workers=min(args.workers, 6)) as pool:
        futures = [pool.submit(one, row) for row in pending]
        for future in as_completed(futures):
            path = future.result()
            print(json.dumps({'uploaded': path, 'completed': len(state['blobs']), 'total': len(session['chunks'])}), flush=True)
    for name in session['manifest_names']:
        path = session['prefix'] + '/' + name
        if path not in state['blobs']:
            result = api.call('create_blob', repository_full_name=args.repository,
                              content=(args.session / name).read_text(encoding='utf-8'), encoding='utf-8')
            state['blobs'][path] = result['sha']
            write(state_path, state)
    if not state.get('commit'):
        tree = api.call('create_tree', repository_full_name=args.repository, base_tree_sha=base_tree,
                        tree_elements=[{'path': path, 'mode': '100644', 'type': 'blob', 'sha': sha}
                                       for path, sha in state['blobs'].items()])
        commit = api.call('create_commit', repository_full_name=args.repository,
                          message='Stage hash-pinned B5 native candidates ' + session['source_commit'][:8],
                          parent_sha=parent, tree_sha=tree['sha'])
        state['tree'] = tree['sha']
        state['commit'] = commit['sha']
        write(state_path, state)
    for name in session['request_names']:
        request = read(args.session / (name + '.template'))
        request['vault_commit'] = state['commit']
        write(args.session / name, request)
    print(json.dumps({'detached_vault_commit': state['commit'], 'expected_parent': state['parent'],
                      'branch_ref_changed': False, 'next': 'Coordinate branch ref publication before triggering native requests'}))


def publish(args) -> None:
    state = read(args.session / 'UPLOAD.json')
    if args.expected_parent != state['parent'] or not state.get('commit'):
        raise ValueError('Explicit expected parent must match the reviewed staging receipt')
    api = Transport(args.helper)
    api.private_repository(state['repository'])
    if state['branch'] == 'main':
        raise ValueError('Vault main must remain unchanged')
    result = api.call('create_branch', repository_full_name=state['repository'], branch_name=state['branch'],
                      sha=state['commit'])
    state['published'] = True
    state['publish_result'] = result
    write(args.session / 'UPLOAD.json', state)
    print(json.dumps({'vault_commit': state['commit'], 'branch': state['branch'], 'published': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'upload', 'publish'])
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--windows-export', type=Path)
    parser.add_argument('--android-export', type=Path)
    parser.add_argument('--old-apk', type=Path)
    parser.add_argument('--prefix')
    parser.add_argument('--helper', type=Path)
    parser.add_argument('--repository', default='irewon1-lgtm/baram-windows-private')
    parser.add_argument('--branch', default='work/b5-final-native-20261017')
    parser.add_argument('--parent-ref', default='main')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--expected-parent')
    args = parser.parse_args()
    if args.mode == 'prepare':
        if not all([args.windows_export, args.android_export, args.old_apk, args.prefix]):
            parser.error('prepare requires both export directories, old APK and isolated prefix')
        prepare(args)
    else:
        if not args.helper:
            parser.error('upload/publish requires the official HostedAppsClient helper path')
        upload(args) if args.mode == 'upload' else publish(args)


if __name__ == '__main__':
    main()
