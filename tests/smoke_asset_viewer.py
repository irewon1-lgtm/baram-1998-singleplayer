#!/usr/bin/env python3
"""Own-fixture EPF -> PNG -> real X11 Godot viewport and left/right input check."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
from test_legacy_assets import ROOT, write_fixture


def run(args):
    directory = Path(args.private_dir).resolve()
    sys.path.insert(0, str(ROOT / 'tools'))
    from legacy_assets import private_path
    private_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    metadata = write_fixture(directory)
    commands = []
    report = dict(executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='OWN_FIXTURE_INSPECTOR_ONLY_NOT_ORIGINAL_ASSETS_OR_GAMEPLAY',
                  status='NOT_RUN', commands=commands, checks=[],
                  expected='12 viewport pixel centers preserve palette, stencil and pivot; inspector right/left keys work',
                  source_sha256={str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                                 for file in [ROOT / 'tools/legacy_assets.py', ROOT / 'tools/render_legacy_assets.py',
                                              ROOT / 'tools/asset_viewer/viewer.gd', Path(__file__).resolve(),
                                              ROOT / 'tests/test_legacy_assets.py']})
    xserver = None
    read_fd = write_fd = None
    try:
        command = [sys.executable, str(ROOT / 'tools/render_legacy_assets.py'), '--container', str(directory / 'sample.dat'),
                   '--container-sha256', metadata['container_sha256'], '--epf', 'sample.epf', '--palette', 'sample.pal',
                   '--palette-sha256', metadata['palette_sha256'], '--palette-index', '0', '--frames', '0-2',
                   '--version', 'OWN_FIXTURE', '--out', str(directory / 'images'), '--report', str(directory / 'decode.json')]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        commands.append(dict(argv=command, exit_code=result.returncode))
        (directory / 'decoder.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Fixture decode failed; inspect decoder.log')
        environment = dict(os.environ)
        for variable, folder in [('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')]:
            environment[variable] = str(directory / folder)
            (directory / folder).mkdir(exist_ok=True)
        environment['LIBGL_ALWAYS_SOFTWARE'] = '1'
        # Xvfb cannot create the standard socket directory as an unprivileged user.
        # Create it when absent; never change an existing directory's permissions.
        Path('/tmp/.X11-unix').mkdir(mode=0o1777, exist_ok=True)
        read_fd, write_fd = os.pipe()
        command = [args.xvfb, '-displayfd', str(write_fd), '-screen', '0', '960x640x24', '-nolisten', 'tcp']
        commands.append(dict(argv=command, scope='PRIVATE_DISPLAY_NOT_PUBLIC_SERVICE'))
        with (directory / 'xvfb.log').open('w') as logfile:
            xserver = subprocess.Popen(command, pass_fds=(write_fd,), stdout=logfile, stderr=subprocess.STDOUT, env=environment)
        os.close(write_fd); write_fd = None
        if not select.select([read_fd], [], [], 15)[0]:
            raise RuntimeError('Xvfb did not report readiness within 15 seconds')
        display = os.read(read_fd, 32).decode().strip()
        if not display.isdecimal():
            raise RuntimeError('Xvfb failed to allocate a display; inspect xvfb.log')
        environment['DISPLAY'] = ':' + display
        command = [args.godot, '--path', str(ROOT / 'tools/asset_viewer'), '--display-driver', 'x11',
                   '--rendering-method', 'gl_compatibility', '--audio-driver', 'Dummy', '--',
                   '--report=' + str(directory / 'decode.json'), '--capture=' + str(directory / 'viewport.png'),
                   '--screen-report=' + str(directory / 'screen.json'), '--exercise', '--exit']
        with (directory / 'godot.log').open('w') as logfile:
            result = subprocess.run(command, env=environment, stdout=logfile, stderr=subprocess.STDOUT, timeout=45)
        commands.append(dict(argv=command, exit_code=result.returncode))
        log = (directory / 'godot.log').read_text()
        if result.returncode or 'ERROR:' in log or 'SCRIPT ERROR:' in log:
            raise RuntimeError('Godot execution failed; inspect godot.log')
        screen = json.loads((directory / 'screen.json').read_text())
        report['godot_screen'] = screen
        if screen.get('screen_status') != 'PASS_INSPECTOR_VIEWPORT_CAPTURE_ONLY' or screen.get('key_navigation_status') != 'PASS_INSPECTOR_RIGHT_LEFT_INPUT_ONLY':
            raise RuntimeError('Screen capture or actual inspector key event check did not pass')
        # Pillow is an independent PNG reader, not the EPF decoder under test.
        from PIL import Image
        image = Image.open(directory / 'viewport.png').convert('RGB')
        background = image.getpixel((130, 170))
        # Expected fixture pixels are literals. Do not compute them with the decoder.
        expected = [(255, 0, 0), (0, 255, 0), None, (255, 255, 255),
                    None, (0, 0, 0), (0, 0, 0), None,
                    (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]
        for index, color in enumerate(expected):
            point = (152 + index % 4 * 8 + 4, 184 + index // 4 * 8 + 4)
            expected_color = color if color is not None else background
            observed = image.getpixel(point)
            report['checks'].append(dict(pixel=index, screen_point=point, expected=expected_color, observed=observed,
                                         result='PASS' if observed == expected_color else 'FAIL'))
        if any(check['result'] != 'PASS' for check in report['checks']):
            raise RuntimeError('Viewport palette/stencil/pivot pixels differ from expected fixture')
        report['status'] = 'PASS_OWN_FIXTURE_VIEWPORT_AND_INSPECTOR_INPUT_ONLY'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, ImportError) as exc:
        report.update(status='FAIL', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        for descriptor in [read_fd, write_fd]:
            if descriptor is not None:
                os.close(descriptor)
        if xserver is not None and xserver.poll() is None:
            xserver.terminate()
            try:
                xserver.wait(timeout=5)
            except subprocess.TimeoutExpired:
                xserver.kill(); xserver.wait(timeout=5)
        report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'pixel_checks': len(report['checks']), 'error': report.get('error')}))
    return 0 if report['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True, help='Fresh external directory for own fixture and screenshots')
    parser.add_argument('--report', required=True, help='Metadata-only results')
    parser.add_argument('--godot', default='godot')
    parser.add_argument('--xvfb', default='Xvfb')
    raise SystemExit(run(parser.parse_args()))
