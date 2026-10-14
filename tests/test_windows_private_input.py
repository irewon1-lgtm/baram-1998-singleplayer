import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from restore_private_runtime import restore


class PrivateInputTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.output = self.root / 'runtime'

    def seed(self, extra=None):
        archive = self.root / 'seed.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
            package.writestr('README.txt', 'Private build input')
            package.writestr('.gitattributes', 'runtime/** -text\n')
            package.writestr('runtime/PACKAGE_MANIFEST.json', '{}')
            package.writestr('runtime/template-win64.exe', b'PE template')
            package.writestr('runtime/private_assets/pixels.bin', bytes(range(256)))
            if extra:
                package.writestr(extra, b'unsafe')
        data = archive.read_bytes()
        part = self.vault / 'baram-private-runtime.part000'
        part.write_bytes(data)
        self.manifest = {'format':'BARAM_PRIVATE_RUNTIME_CHUNKS_V1', 'archive_bytes':len(data),
                         'archive_sha256':hashlib.sha256(data).hexdigest(),
                         'parts':[{'file':part.name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}]}
        self.write_manifest()
        return part

    def write_manifest(self):
        (self.vault / 'private-runtime-manifest.json').write_text(json.dumps(self.manifest))

    def test_original_bytes_are_restored_and_previous_output_preserved(self):
        self.seed()
        restore(self.vault, self.output)
        self.assertEqual((self.output / 'private_assets/pixels.bin').read_bytes(), bytes(range(256)))
        with self.assertRaisesRegex(ValueError, 'Previous runtime'):
            restore(self.vault, self.output)

    def test_corrupt_part_blocks_restoration(self):
        part = self.seed()
        data = bytearray(part.read_bytes()); data[0] ^= 1; part.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'part integrity'):
            restore(self.vault, self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_complete_archive_hash_blocks_restoration(self):
        self.seed(); self.manifest['archive_sha256'] = '0' * 64; self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Complete private'):
            restore(self.vault, self.output)

    def test_part_path_cannot_escape_vault(self):
        self.seed(); self.manifest['parts'][0]['file'] = '../seed.zip'; self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'safe basenames'):
            restore(self.vault, self.output)

    def test_zip_path_cannot_escape_output(self):
        self.seed('runtime/../../escape.bin')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            restore(self.vault, self.output)
        self.assertFalse((self.root / 'escape.bin').exists())

    def test_unexpected_zip_payload_is_rejected(self):
        self.seed('unknown.bin')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            restore(self.vault, self.output)


if __name__ == '__main__':
    unittest.main()
