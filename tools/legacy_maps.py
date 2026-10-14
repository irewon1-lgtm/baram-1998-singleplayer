"""Strict reader for the observed 4.x map, tile-table and static-object formats.

No external implementation is included. Dimensions are a separate, attributed
input: the shipped .map bytes have no header. TBL bases select sheets; they must
never be replaced with a global index offset or a 0x3fff rendering mask.
"""
import struct
from dataclasses import dataclass
from legacy_assets import AssetError, region


@dataclass(frozen=True)
class TileTable:
    count: int
    palettes: tuple
    base: int
    kind: int


def tile_table(data, frame_count, palette_count):
    count, pals, base, kind = struct.unpack('<IIHB', region(data, 0, 11))
    if count != frame_count or pals != palette_count or len(data) != 11 + count * 2:
        raise AssetError('4.x tile-table header/count does not match EPF/PAL')
    words = struct.unpack('<' + 'H' * count, data[11:])
    indices = tuple(w & 0x7fff for w in words)
    if any(i >= pals for i in indices):
        raise AssetError('4.x tile-table references a missing palette')
    return TileTable(count, indices, base, kind)


def static_objects(data, tile_count):
    count, = struct.unpack('<I', region(data, 0, 4))
    if not 1 <= count <= 100000:
        raise AssetError('Static-object count outside supported bounds')
    objects, cursor = [], 4
    for index in range(count):
        flags, height = region(data, cursor, 2)
        cursor += 2
        words = struct.unpack('<' + 'H' * height, region(data, cursor, 2 * height))
        cursor += 2 * height
        metadata = region(data, cursor, 5)
        cursor += 5
        if any(w > tile_count for w in words):
            raise AssetError(f'Static object {index} references a missing TileC frame')
        objects.append(dict(id=index, collision=(flags & 15) if index else 0, flags=flags,
                            frames=[w - 1 if w else None for w in words],
                            raw_frame_words=list(words), metadata_hex=metadata.hex()))
    # The verified KR491/NA495 tables end with one empty sentinel's flag/height.
    if data[cursor:] != b'\x0f\x00' or objects[0]['frames']:
        raise AssetError('Unknown static-object trailer or nonempty null object')
    return objects


def ground_id(word, tables, prefix='KR491'):
    if word == 0:
        return ''
    group = 'B' if word >= tables['B'].base else 'A'
    index = word - tables[group].base
    if not 0 <= index < tables[group].count:
        raise AssetError(f'Ground word {word:#06x} outside {group} table')
    return f'{prefix}/{group}:{index}'


def map_cells(data, width, height, tables, objects):
    if not 1 <= width <= 512 or not 1 <= height <= 512 or len(data) != width * height * 4:
        raise AssetError('Headerless map byte count does not match supplied dimensions')
    cells = []
    for i in range(width * height):
        word, obj = struct.unpack_from('<HH', data, i * 4)
        tile = ground_id(word, tables)
        if obj >= len(objects):
            raise AssetError(f'Map cell {i} static object {obj} outside table')
        cells.append(dict(tile=tile, object_id=obj, ground_word=word,
                          collision=15 if word == 0 or word >= tables['B'].base else objects[obj]['collision']))
    return cells
