"""Independent static readers for the verified InstallShield4 and Wise payloads.

Layouts were measured from the hash-pinned installers in this repository's
input ledger. InstallShield output DAT hashes reproduce the inherited world
audit. No installer code is run or copied; output belongs in a private folder.
"""
import struct
import zlib
from legacy_assets import AssetError, region, unpack

MAX_OUTPUT = 128 * 1024 * 1024


def cstring(data, offset):
    if not 0 <= offset < len(data):
        raise AssetError('String offset outside metadata')
    end = data.find(b'\0', offset)
    if end < 0:
        raise AssetError('Metadata string has no terminator')
    value = data[offset:end].decode('ascii')
    if value in ('.', '..') or '/' in value or '\\' in value:
        raise AssetError('Unsafe installer path component')
    return value


def installshield4(data):
    """Yield metadata and bytes for active single-volume v4 file records."""
    signature, version, _, descriptor, _, payload_start = unpack('<6I', data)
    if signature != 0x28635349 or version != 0x01000004:
        raise AssetError('Only measured ISc( v4 layout is supported')
    region(data, descriptor, 56)
    table_offset, = unpack('<I', data, descriptor + 12)
    table_size, = unpack('<I', data, descriptor + 20)
    dirs, = unpack('<I', data, descriptor + 28)
    files, = unpack('<I', data, descriptor + 40)
    if not 1 <= dirs <= 4096 or not 1 <= files <= 100_000:
        raise AssetError('Installer directory/file count out of bounds')
    table = region(data, descriptor + table_offset, table_size)
    region(table, 0, 4 * (dirs + files))
    directories = [cstring(table, unpack('<I', table, index * 4)[0]) for index in range(dirs)]
    paths = set()
    for index in range(files):
        offset, = unpack('<I', table, (dirs + index) * 4)
        name_offset, directory, flags, expanded, compressed = unpack('<IIHII', table, offset)
        # v4 retains removed records with flag 8 and deliberately invalid names.
        if flags & 8:
            yield dict(index=index, flags=flags, status='REMOVED_METADATA_SKIPPED'), None
            continue
        if flags != 4 or directory >= dirs or not 0 < expanded <= MAX_OUTPUT:
            raise AssetError('Unsupported active flags/directory/output size')
        name = cstring(table, name_offset)
        if not name:
            raise AssetError('Active installer filename is empty')
        path = directories[directory] + '/' + name if directories[directory] else name
        if path.casefold() in paths:
            raise AssetError('Duplicate installer output path')
        paths.add(path.casefold())
        start, = unpack('<I', table, offset + 38)
        if start < payload_start:
            raise AssetError('Compressed installer file overlaps metadata')
        blob = region(data, start, compressed)
        if not blob.endswith(b'\x00\x00\xff\xff'):
            raise AssetError('Expected v4 raw-DEFLATE sync-flush boundary')
        codec = zlib.decompressobj(-15)
        raw = codec.decompress(blob, expanded + 1)
        if len(raw) != expanded or codec.unused_data or codec.unconsumed_tail:
            raise AssetError('Declared installer output size/stream boundary mismatch')
        yield dict(index=index, name=name, path=path, flags=flags, offset=start,
                   compressed_bytes=compressed, bytes=expanded, status='PASS_STATIC_FILE_EXTRACT'), raw


def wise_streams(data, start):
    """Bounded raw-DEFLATE + little-endian CRC32 chain; every byte must belong."""
    offset = start
    index = 0
    while offset < len(data):
        if index >= 4096:
            raise AssetError('Wise stream count exceeds supported bound')
        codec = zlib.decompressobj(-15)
        raw = codec.decompress(region(data, offset, len(data) - offset), MAX_OUTPUT + 1)
        if not codec.eof or len(raw) > MAX_OUTPUT or codec.unconsumed_tail:
            raise AssetError('Wise stream is truncated or output bound exceeded')
        size = len(data) - offset - len(codec.unused_data)
        expected, = unpack('<I', data, offset + size)
        observed = zlib.crc32(raw) & 0xffffffff
        if observed != expected:
            raise AssetError('Wise stream CRC32 mismatch')
        yield dict(index=index, offset=offset, compressed_bytes=size, bytes=len(raw),
                   crc32=expected, status='PASS_DEFLATE_CRC32_ONLY'), raw
        offset += size + 4
        index += 1
    if offset != len(data):
        raise AssetError('Wise payload chain does not consume entire installer')


def wise_named_records(script, streams):
    """Match names by physical stream bounds, CRC and declared expanded size.

    The name is immediately preceded by its CRC32. The expanded size is 28 bytes
    before the name. Relative stream start/end are 40/36 bytes before it. Derive
    their shared base from uniquely identified streams, then disambiguate equal
    CRCs (common for identical maps) by the physical compressed offsets.
"""
    import re
    from collections import Counter
    candidates = []
    bases = Counter()
    for match in re.finditer(rb'%MAINDIR%\\([^\0]+)\0', script):
        offset = match.start()
        if offset < 48:
            continue
        crc, = unpack('<I', script, offset - 4)
        expanded, = unpack('<I', script, offset - 28)
        start, end = unpack('<II', script, offset - 40)
        choices = [row for row in streams if row['crc32'] == crc and row['bytes'] == expanded
                   and end - start == row.get('compressed_bytes', -1) + 4]
        name = match.group(1).decode('ascii')
        parts = name.split('\\')
        if any(not p or p in ('.', '..') or '/' in p or ':' in p or '*' in p for p in parts):
            continue
        candidates.append(('/'.join(parts), offset, start, end, choices))
        if len(choices) == 1:
            bases[choices[0]['offset'] - start] += 1
    if not bases:
        return
    ranked = bases.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        raise AssetError('Wise script stream base is ambiguous')
    base = ranked[0][0]
    for name, offset, start, end, choices in candidates:
        physical = [row for row in choices if row['offset'] == base + start]
        if len(physical) == 1:
            yield name, physical[0], offset
