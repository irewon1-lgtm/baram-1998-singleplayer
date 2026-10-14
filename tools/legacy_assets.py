"""Bounded DAT/EPF/PAL decoding; no game resources or semantic guesses included.

Format reference: MIT DizzyThermal/EPFViewer at 2bc585b3ae3310df5de46f7789eada92840fbd59,
FileHandlers/{Dat,Epf,Pal}FileHandler.gd. See docs/development/THIRD_PARTY_NOTICES.md.
This independently written implementation rejects invalid bounds rather than
silently substituting a frame or palette. Only explicit PAL indices are used.
"""
from dataclasses import dataclass
import struct
import zlib
from pathlib import Path


class AssetError(ValueError):
    """Malformed input, unsupported layout, or invalid selection."""


def region(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise AssetError(f"Region out of bounds: offset={offset}, size={size}, total={len(data)}")
    return data[offset:offset + size]


def unpack(fmt: str, data: bytes, offset: int = 0):
    return struct.unpack(fmt, region(data, offset, struct.calcsize(fmt)))


def dat_entries(data: bytes) -> dict[str, tuple[str, int, bytes]]:
    slots, = unpack('<I', data)
    if not 1 <= slots <= 100_000:
        raise AssetError('DAT directory slot count outside supported bounds')
    directory_end = 4 + 17 * (slots - 1) + 4
    region(data, 0, directory_end)
    entries = {}
    for i in range(slots - 1):
        offset = 4 + 17 * i
        start, = unpack('<I', data, offset)
        end, = unpack('<I', data, offset + 17)
        raw_name = region(data, offset + 4, 13).split(b'\0', 1)[0]
        try:
            name = raw_name.decode('ascii')
        except UnicodeDecodeError as exc:
            raise AssetError('Non-ASCII DAT entry name') from exc
        if not name or '/' in name or '\\' in name or name in ('.', '..'):
            raise AssetError('Invalid DAT entry name')
        key = name.casefold()
        if key in entries:
            raise AssetError(f'Duplicate DAT entry: {name}')
        if start < directory_end or end < start:
            raise AssetError(f'DAT payload overlaps directory or has reversed bounds: {name}')
        entries[key] = (name, start, region(data, start, end - start))
    # An empty DAT still has one end-offset slot.
    end, = unpack('<I', data, 4 + 17 * (slots - 1))
    if end < directory_end or end > len(data):
        raise AssetError('DAT final offset outside payload bounds')
    return entries


@dataclass(frozen=True)
class Palette:
    colors: tuple[tuple[int, int, int], ...]
    animation_ranges: tuple[tuple[int, int], ...] = ()


def read_palettes(data: bytes) -> tuple[Palette, ...]:
    """768-byte raw RGB or single/counted DLPalette, keeping range metadata."""
    if len(data) == 768:
        return (Palette(tuple(tuple(data[i:i + 3]) for i in range(0, 768, 3))),)
    if data.startswith(b'DLPalette'):
        count, cursor = 1, 0
    else:
        count, = unpack('<I', data)
        cursor = 4
    if count > 4096:
        raise AssetError('PAL count outside supported bounds')
    palettes = []
    for _ in range(count):
        if region(data, cursor, 9) != b'DLPalette':
            raise AssetError('Expected DLPalette header')
        header = region(data, cursor, 32)
        range_count = header[24]
        if range_count > 127:
            raise AssetError('Negative/unsupported PAL animation range count')
        cursor += 32
        ranges = []
        for _ in range(range_count):
            low, high = region(data, cursor, 2)
            if low > high:
                raise AssetError('Reversed PAL animation range')
            ranges.append((low, high))
            cursor += 2
        color_data = region(data, cursor, 1024)
        # Entries are RGB + reserved byte. Alpha comes from the EPF stencil.
        colors = tuple(tuple(color_data[i:i + 3]) for i in range(0, 1024, 4))
        palettes.append(Palette(colors, tuple(ranges)))
        cursor += 1024
    if cursor != len(data):
        raise AssetError('Unsupported trailing PAL data')
    return tuple(palettes)


@dataclass(frozen=True)
class Frame:
    index: int
    left: int
    top: int
    width: int
    height: int
    indices: bytes
    alpha: bytes

    def rgba(self, palette: Palette, recolor_byte: int = 0) -> bytes:
        if not 0 <= recolor_byte <= 255:
            raise AssetError('Recolor byte outside 0..255')
        result = bytearray()
        for index, alpha in zip(self.indices, self.alpha):
            # Measured in the original NA4.95 binary at 0x428d56/0x428e1c.
            # Outline/skin indices below 0x30 stay unchanged; the 8-bit sum wraps.
            lookup = (index + recolor_byte * 8) & 255 if index >= 0x30 else index
            result.extend((*palette.colors[lookup], alpha))
        return bytes(result)


class Epf:
    def __init__(self, data: bytes):
        count, width, height, unknown, pixel_size = unpack('<hhhhI', data)
        if count < 0 or not 0 <= width <= 4096 or not 0 <= height <= 4096:
            raise AssetError('EPF header count/dimensions outside supported bounds')
        self.count = count
        self.width = width
        self.height = height
        self.unknown = unknown
        self.pixels = region(data, 12, pixel_size)
        self.table = region(data, 12 + pixel_size, 16 * count)

    def frame(self, index: int) -> Frame:
        if not 0 <= index < self.count:
            raise AssetError(f'EPF frame index outside 0..{self.count - 1}: {index}')
        top, left, bottom, right, pixel_offset, mask_offset = unpack('<hhhhII', self.table, index * 16)
        width, height = right - left, bottom - top
        if not 0 <= width <= 4096 or not 0 <= height <= 4096:
            raise AssetError('EPF frame rectangle outside supported bounds')
        if width == 0 or height == 0:
            return Frame(index, left, top, width, height, b'', b'')
        indices = region(self.pixels, pixel_offset, width * height)
        mask = bytearray()
        cursor = mask_offset
        for _ in range(height):
            row = bytearray()
            while True:
                run, = region(self.pixels, cursor, 1)
                cursor += 1
                if run == 0:
                    break
                length = run & 0x7f
                if length == 0 or len(row) + length > width:
                    raise AssetError('EPF stencil run is empty or exceeds row width')
                row.extend(bytes([255 if run & 0x80 else 0]) * length)
            # Omitted suffixes are transparent, not copied from the next row.
            row.extend(bytes(width - len(row)))
            mask.extend(row)
        return Frame(index, left, top, width, height, indices, bytes(mask))


def png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    if not 0 < width <= 4096 or not 0 < height <= 4096 or len(rgba) != width * height * 4:
        raise AssetError('PNG dimensions/data mismatch')
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    rows = b''.join(b'\0' + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def private_path(path: str | Path) -> Path:
    """Resolve symlinks too; original or decoded bytes must stay outside checkout."""
    path = Path(path).resolve()
    root = Path(__file__).resolve().parents[1]
    if path == root or root in path.parents or path in root.parents:
        raise AssetError('Resource directory must be outside the public checkout and its ancestors')
    return path
