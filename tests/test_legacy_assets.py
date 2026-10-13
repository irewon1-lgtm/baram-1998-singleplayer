"""Known-pixel and malicious-boundary cases; OWN_FIXTURE only, never original art."""
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from legacy_assets import AssetError, Epf, dat_entries, png_bytes, private_path, read_palettes


def fixture_epf():
    pixels = bytes(range(1, 13))
    masks = bytes([0x82, 1, 0x81, 0, 1, 0x82, 0, 0x84, 0])
    second_pixels = bytes([15, 16])
    second_mask = bytes([0x82, 0])
    blob = pixels + masks + second_pixels + second_mask
    table = (struct.pack('<hhhhII', -2, -1, 1, 3, 0, 12)
             + struct.pack('<hhhhII', 0, 3, 1, 5, 21, 23)
             + struct.pack('<hhhhII', 0, 0, 0, 0, 25, 25))
    return struct.pack('<hhhhI', 3, 6, 6, 0, len(blob)) + blob + table


def fixture_pal():
    # Two distinguishable palettes, so silent index-0 fallback cannot pass.
    header = b'DLPalette' + bytes(15) + bytes([1]) + bytes(7)
    colors = bytearray(1024)
    colors[4:8] = bytes([255, 0, 0, 0])
    colors[8:12] = bytes([0, 255, 0, 0])
    colors[12:16] = bytes([0, 0, 255, 0])
    colors[16:20] = bytes([255, 255, 255, 0])
    second = bytearray(1024)
    second[4:8] = bytes([0, 0, 255, 0])
    return struct.pack('<I', 2) + header + bytes([1, 3]) + colors + header + bytes([4, 6]) + second


def fixture_dat(entries):
    cursor = 8 + len(entries) * 17
    header = struct.pack('<I', len(entries) + 1)
    payload = b''
    for name, data in entries:
        header += struct.pack('<I', cursor) + name.encode('ascii').ljust(13, b'\0')
        cursor += len(data)
        payload += data
    return header + struct.pack('<I', cursor) + payload


def write_fixture(directory):
    directory.mkdir(parents=True, exist_ok=True)
    epf, pal = fixture_epf(), fixture_pal()
    data = fixture_dat([('sample.epf', epf), ('sample.pal', pal)])
    (directory / 'sample.dat').write_bytes(data)
    return {'container_sha256': hashlib.sha256(data).hexdigest(),
            'palette_sha256': hashlib.sha256(pal).hexdigest(),
            'classification': 'OWN_FIXTURE_NOT_ORIGINAL_ASSET'}


class LegacyAssetsTests(unittest.TestCase):
    def test_dat_exact_entries_case_and_payload(self):
        epf, pal = fixture_epf(), fixture_pal()
        entries = dat_entries(fixture_dat([('SAMPLE.EPF', epf), ('sample.pal', pal)]))
        self.assertEqual(entries['sample.epf'], ('SAMPLE.EPF', 42, epf))
        self.assertEqual(entries['sample.pal'][2], pal)

    def test_dat_truncation_overlap_reversal_and_duplicate(self):
        valid = fixture_dat([('a.epf', fixture_epf())])
        malformed = [b'', valid[:24], valid[:4] + struct.pack('<I', 1) + valid[8:],
                     valid[:21] + struct.pack('<I', 24) + valid[25:],
                     fixture_dat([('a.epf', b'a'), ('A.EPF', b'b')]),
                     fixture_dat([('../a', b'a')])]
        for data in malformed:
            with self.subTest(size=len(data)), self.assertRaises(AssetError):
                dat_entries(data)

    def test_palette_explicit_index_rgb_reserved_alpha_and_ranges(self):
        palettes = read_palettes(fixture_pal())
        self.assertEqual(len(palettes), 2)
        self.assertEqual(palettes[0].colors[1:5], ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)))
        self.assertEqual(palettes[1].colors[1], (0, 0, 255))
        self.assertEqual(palettes[0].animation_ranges, ((1, 3),))
        frame = Epf(fixture_epf()).frame(0)
        self.assertEqual(frame.rgba(palettes[0])[:4], bytes([255, 0, 0, 255]))
        self.assertEqual(frame.rgba(palettes[1])[:4], bytes([0, 0, 255, 255]))

    def test_raw_rgb_palette_and_empty_palette_bank(self):
        palettes = read_palettes(bytes([1, 2, 3]) * 256)
        self.assertEqual(palettes[0].colors[255], (1, 2, 3))
        self.assertEqual(read_palettes(bytes(4)), ())

    def test_malformed_palettes_fail_closed(self):
        pal = fixture_pal()
        for data in [b'', pal[:-1], pal + b'x', struct.pack('<I', 4097),
                     struct.pack('<I', 1) + b'WrongHead' + pal[13:],
                     pal[:36] + bytes([4, 1]) + pal[38:]]:
            with self.subTest(size=len(data)), self.assertRaises(AssetError):
                read_palettes(data)

    def test_epf_pixels_negative_pivot_and_each_mask_row(self):
        frame = Epf(fixture_epf()).frame(0)
        self.assertEqual((frame.left, frame.top, frame.width, frame.height), (-1, -2, 4, 3))
        self.assertEqual(frame.indices, bytes(range(1, 13)))
        self.assertEqual(frame.alpha, bytes([255, 255, 0, 255, 0, 255, 255, 0, 255, 255, 255, 255]))
        self.assertEqual(frame.rgba(read_palettes(fixture_pal())[0])[:16],
                         bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 0, 255, 255, 255, 255]))

    def test_epf_nonzero_offsets_and_empty_frame(self):
        epf = Epf(fixture_epf())
        self.assertEqual(epf.frame(1).indices, bytes([15, 16]))
        self.assertEqual(epf.frame(1).alpha, bytes([255, 255]))
        self.assertEqual(epf.frame(2).indices, b'')

    def test_epf_invalid_frame_indices_and_tables(self):
        for index in [-1, 3]:
            with self.assertRaises(AssetError):
                Epf(fixture_epf()).frame(index)
        for data in [b'', fixture_epf()[:-1], struct.pack('<hhhhI', -1, 1, 1, 0, 0),
                     struct.pack('<hhhhI', 1, 1, 1, 0, 500)]:
            with self.subTest(size=len(data)), self.assertRaises(AssetError):
                Epf(data)

    def test_epf_invalid_pixel_mask_rectangle_and_noop(self):
        # Known short blob: four pixels, explicit stencil and one frame rectangle.
        for mask, pixel_offset, mask_offset, right in [
                (bytes([0x85, 0]), 0, 4, 4), (bytes([0x84]), 0, 4, 4),
                (bytes([0x80, 0]), 0, 4, 4), (bytes([0x84, 0]), 100, 4, 4),
                (bytes([0x84, 0]), 0, 100, 4), (bytes([0x84, 0]), 0, 4, -1)]:
            blob = bytes([1, 2, 3, 4]) + mask
            data = struct.pack('<hhhhI', 1, 4, 1, 0, len(blob)) + blob + struct.pack('<hhhhII', 0, 0, 1, right, pixel_offset, mask_offset)
            with self.subTest(mask=mask), self.assertRaises(AssetError):
                Epf(data).frame(0)

    def test_png_external_container_crc_and_scanlines(self):
        rgba = bytes([255, 0, 0, 255, 0, 255, 0, 0])
        png = png_bytes(2, 1, rgba)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        offset, kinds, compressed = 8, [], b''
        while offset < len(png):
            size, = struct.unpack_from('>I', png, offset)
            kind = png[offset + 4:offset + 8]
            payload = png[offset + 8:offset + 8 + size]
            crc, = struct.unpack_from('>I', png, offset + 8 + size)
            self.assertEqual(zlib.crc32(kind + payload) & 0xffffffff, crc)
            if kind == b'IDAT': compressed += payload
            kinds.append(kind)
            offset += size + 12
        self.assertEqual(kinds, [b'IHDR', b'IDAT', b'IEND'])
        self.assertEqual(zlib.decompress(compressed), b'\0' + rgba)

    def test_resource_output_refuses_checkout_and_ancestors(self):
        for path in [ROOT, ROOT / 'build' / 'original', ROOT.parent, '/']:
            with self.subTest(path=str(path)), self.assertRaises(AssetError):
                private_path(path)

    def test_export_cli_hashes_status_and_invalid_palette(self):
        with tempfile.TemporaryDirectory(prefix='baram-fixture-') as temporary:
            directory = Path(temporary)
            meta = write_fixture(directory)
            report = directory / 'decode.json'
            cmd = [sys.executable, str(ROOT / 'tools/render_legacy_assets.py'), '--container', str(directory / 'sample.dat'),
                   '--container-sha256', meta['container_sha256'], '--epf', 'sample.epf', '--palette', 'sample.pal',
                   '--palette-sha256', meta['palette_sha256'], '--palette-index', '1', '--frames', '0-2',
                   '--version', 'OWN_FIXTURE', '--out', str(directory / 'images'), '--report', str(report)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(report.read_text())
            self.assertEqual([row['status'] for row in data['frames']],
                             ['PASS_PIXEL_DECODE_PNG_ONLY', 'PASS_PIXEL_DECODE_PNG_ONLY', 'EMPTY_FRAME'])
            self.assertEqual(data['screen_status'], 'NOT_RUN')
            self.assertEqual(data['semantic_identification_status'], 'NOT_RUN')
            self.assertEqual(hashlib.sha256((directory / 'images/frame_000000.png').read_bytes()).hexdigest(), data['frames'][0]['png_sha256'])
            cmd[cmd.index('--palette-index') + 1] = '2'
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Palette index outside', json.loads(report.read_text())['error'])
            cmd[cmd.index('--container-sha256') + 1] = '0' * 64
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('SHA256 mismatch', json.loads(report.read_text())['error'])
            cmd[cmd.index('--container-sha256') + 1] = meta['container_sha256']
            cmd[cmd.index('--palette-index') + 1] = '1'
            protected = directory / 'protected.txt'
            protected.write_bytes(b'Preserve existing unrelated bytes')
            output = directory / 'images/frame_000000.png'
            output.unlink()
            output.symlink_to(protected)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Symlink output refused', json.loads(report.read_text())['error'])
            self.assertEqual(protected.read_bytes(), b'Preserve existing unrelated bytes')


if __name__ == '__main__':
    unittest.main()
