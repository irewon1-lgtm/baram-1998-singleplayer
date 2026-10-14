#!/usr/bin/env python3
"""Decode selected real frames outside the checkout; emit provenance, never guesses."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from legacy_assets import AssetError, Epf, dat_entries, png_bytes, private_path, read_palettes


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selection(text, count):
    indices = set()
    for part in text.split(','):
        bounds = part.split('-')
        if len(bounds) == 1:
            low = high = int(bounds[0])
        elif len(bounds) == 2:
            low, high = map(int, bounds)
        else:
            raise AssetError('Use comma-separated frame numbers or inclusive ranges')
        if low < 0 or high < low or high >= count or high - low >= 256:
            raise AssetError('Frame selection outside file bounds or 256-frame batch limit')
        indices.update(range(low, high + 1))
        if len(indices) > 256:
            raise AssetError('Maximum 256 frames per explicit batch')
    return sorted(indices)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', required=True, help='EPF file or legacy DAT')
    parser.add_argument('--container-sha256', required=True)
    parser.add_argument('--epf', help='EPF entry name when container is DAT')
    parser.add_argument('--palette', required=True, help='PAL entry name in same DAT or external PAL path')
    parser.add_argument('--palette-sha256', required=True, help='Expected selected PAL payload SHA256')
    parser.add_argument('--palette-index', type=int, required=True)
    parser.add_argument('--recolor-byte', type=int, default=0, help='Explicit NA4.95 ramp byte; table palette index stays independent')
    parser.add_argument('--frames', required=True, help='Explicit zero-based frames, e.g. 0-3,8')
    parser.add_argument('--version', required=True, choices=['KR-4.91', 'NA-4.03', 'NA-4.66', 'NA-4.95', 'OWN_FIXTURE'])
    parser.add_argument('--out', required=True, help='Private PNG output directory outside checkout')
    parser.add_argument('--report', required=True, help='Metadata JSON, may be inside checkout')
    args = parser.parse_args()
    report = dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), version=args.version,
                  source=str(Path(args.container).resolve()), expected_container_sha256=args.container_sha256,
                  epf=args.epf, palette=args.palette, palette_index=args.palette_index, recolor_byte=args.recolor_byte,
                  rights='OWN_FIXTURE' if args.version == 'OWN_FIXTURE' else 'NO_DISTRIBUTION_PERMISSION_VERIFIED',
                  decoded_render_status='NOT_RUN', screen_status='NOT_RUN', semantic_identification_status='NOT_RUN',
                  public_resource_bytes_included=False, frames=[])
    try:
        output = private_path(args.out)
        data = Path(args.container).read_bytes()
        report['container_sha256'] = sha(data)
        if sha(data) != args.container_sha256:
            raise AssetError('Container SHA256 mismatch; refusing to decode')
        entries = dat_entries(data) if args.epf else {}
        if args.epf:
            try:
                _, epf_offset, payload = entries[args.epf.casefold()]
            except KeyError as exc:
                raise AssetError('Requested EPF absent from DAT') from exc
            report['epf_offset'] = epf_offset
        else:
            payload = data
        if args.palette.casefold() in entries:
            _, palette_offset, palette_data = entries[args.palette.casefold()]
            report['palette_offset'] = palette_offset
        else:
            palette_data = Path(args.palette).read_bytes()
        report.update(epf_sha256=sha(payload), palette_sha256=sha(palette_data))
        if sha(palette_data) != args.palette_sha256:
            raise AssetError('Palette SHA256 mismatch; refusing to decode')
        palettes = read_palettes(palette_data)
        if not 0 <= args.palette_index < len(palettes):
            raise AssetError('Palette index outside file bounds; no fallback permitted')
        palette = palettes[args.palette_index]
        report['palette_animation_ranges'] = palette.animation_ranges
        report['palette_animation_status'] = 'STATIC_EXPLICIT_PALETTE_NO_ANIMATION'
        epf = Epf(payload)
        report['declared_frames'] = epf.count
        output.mkdir(parents=True, exist_ok=True)
        for index in selection(args.frames, epf.count):
            frame = epf.frame(index)
            row = dict(index=index, left=frame.left, top=frame.top, width=frame.width, height=frame.height,
                       status='EMPTY_FRAME', screen_status='NOT_RUN', semantic_status='NOT_RUN')
            if frame.width and frame.height:
                rgba = frame.rgba(palette, args.recolor_byte)
                png = png_bytes(frame.width, frame.height, rgba)
                destination = output / f'frame_{index:06d}.png'
                if destination.is_symlink():
                    raise AssetError(f'Symlink output refused: {destination}')
                if destination.exists() and destination.read_bytes() != png:
                    raise AssetError(f'Existing different output: {destination}; use a fresh output directory')
                destination.write_bytes(png)
                row.update(status='PASS_PIXEL_DECODE_PNG_ONLY', png_path=str(destination), png_sha256=sha(png),
                           rgba_sha256=sha(rgba), opaque_pixels=frame.alpha.count(255))
            report['frames'].append(row)
        report['decoded_render_status'] = 'PASS_SELECTED_PIXELS_PNG_ONLY'
        exit_code = 0
    except (OSError, ValueError) as exc:
        report.update(decoded_render_status='FAIL', error=type(exc).__name__ + ': ' + str(exc))
        exit_code = 1
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('version', 'decoded_render_status', 'screen_status', 'semantic_identification_status')}
                     | {'selected_frames': len(report['frames']), 'error': report.get('error')}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
