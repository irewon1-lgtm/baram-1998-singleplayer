#!/usr/bin/env python3
"""Extract unchanged embedded PCK bytes from one receipted Windows candidate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-export', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt_path = args.windows_export.resolve() / 'EXPORT_RECEIPT.json'
    receipt = json.loads(receipt_path.read_text())
    artifact = receipt['artifact']
    exe = Path(artifact['path']).resolve()
    if (receipt['result'] != 'PASS_EXPORT_ONLY' or receipt['target'] != 'Windows'
            or exe.parent != args.windows_export.resolve() or digest(exe) != artifact['sha256']
            or exe.stat().st_size != artifact['bytes']):
        raise ValueError('Exact successful Windows export bytes are required')
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a fresh PCK output path')
    output.parent.mkdir(parents=True, exist_ok=True)
    with exe.open('rb') as source:
        source.seek(-12, 2)
        size, magic = struct.unpack('<QI', source.read(12))
        offset = exe.stat().st_size - 12 - size
        if magic != 0x43504447 or offset < 0 or size < 64:
            raise ValueError('Embedded PCK footer is invalid')
        source.seek(offset)
        if source.read(4) != b'GDPC':
            raise ValueError('Embedded PCK header is invalid')
        source.seek(offset)
        remaining = size
        with output.open('xb') as target:
            while remaining:
                chunk = source.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise ValueError('Truncated PCK')
                target.write(chunk)
                remaining -= len(chunk)
    proof = {'schema': 'baram.g2.r16.candidate-pck-provenance/1',
        'source_commit': receipt['source_commit'], 'source_content_fingerprint': receipt['source_content_fingerprint'],
        'windows_export_receipt': str(receipt_path), 'windows_export_receipt_sha256': digest(receipt_path),
        'windows_exe': artifact, 'embedded_pck': {'path': str(output), 'bytes': output.stat().st_size,
            'sha256': digest(output), 'source_offset': offset, 'extraction': 'Exact bytes from original Windows EXE; no header or content rewrite'},
        'runtime_manifest_sha256': receipt['runtime_manifest_sha256'],
        'content_sha256': receipt['gameplay_content_sha256'],
        'standard_parity_status': 'PENDING', 'expanded_parity_status': 'PENDING',
        'native_execution': 'NOT_RUN', 'native_update': 'NOT_RUN'}
    proof_path = output.with_suffix('.provenance.json')
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'embedded_pck': proof['embedded_pck'], 'provenance': str(proof_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
