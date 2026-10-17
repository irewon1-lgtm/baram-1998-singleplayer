#!/usr/bin/env python3
"""Narrow cold/resume GUI probe, prepared for explicit integration-owner GO.

Two ordinary processes Continue the same byte-copied earned save, each receives
20 seconds of safe town arrow-key input, autosaves, then Save/return-to-menu.
Only XTEST mouse/keys control the application. Runtime definitions and committed
saves are read-only observations. No engine callbacks, grants, combat or trades.
Run under toolchain/run_gui.py. This is Linux automation, not native Windows,
Android, physical input/IME/audio, natural progression or long-play acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p2'))
from gameplay_x11 import X11, checkpoints


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest(directory):
    return [{'file': str(path.relative_to(directory)), 'bytes': path.stat().st_size,
             'sha256': digest(path)} for path in sorted(directory.rglob('*')) if path.is_file()]


def rows(path):
    return checkpoints(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['godot', 'project', 'runtime', 'pack', 'pack-provenance', 'output', 'resume-data', 'xdotool']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--user-dir-name', default='baram_rebuild_p3repair_001')
    parser.add_argument('--resume-user-dir-name', default='baram_rebuild_p3repair_001')
    parser.add_argument('--safe-map', default='gp:map:domestic_city')
    parser.add_argument('--expected-monsters', type=int, default=752)
    parser.add_argument('--candidate-file', type=Path, action='append', default=[])
    parser.add_argument('--run-authorized', action='store_true',
                        help='Integration-owner GO is required before executing this prepared probe')
    args = parser.parse_args()
    if not args.run_authorized:
        parser.error('Prepared source only until integration-owner GO; pass --run-authorized only after GO')
    for name in [args.user_dir_name, args.resume_user_dir_name]:
        if not name or '/' in name or '\\' in name or '..' in name:
            parser.error('Simple custom user directory names required')
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Fresh output directory required; never overwrite evidence: ' + str(output))
    source = args.resume_data.resolve() / args.resume_user_dir_name
    if not source.is_dir():
        raise ValueError('Earned source user directory absent: ' + str(source))
    original_files = manifest(source)
    original_saves = sorted((source / 'gameplay-p3/characters').glob('*.json'))
    if len(original_saves) != 1:
        raise ValueError('Exactly one already earned character primary save is required')
    original_payload = json.loads(original_saves[0].read_text())['payload']
    content = json.loads((args.runtime / 'gameplay_content.json').read_text())
    pack_provenance = json.loads(args.pack_provenance.read_text())
    expected_pack = pack_provenance.get('embedded_pck', {}).get('sha256')
    if (pack_provenance.get('standard_parity_status') != 'PASS'
            or pack_provenance.get('expanded_parity_status') != 'PASS'
            or pack_provenance.get('expanded_parity_failures')
            or len(pack_provenance.get('source_commit', '')) != 40
            or expected_pack != digest(args.pack)
            or pack_provenance.get('runtime_manifest_sha256') != digest(args.runtime / 'runtime.json')
            or pack_provenance.get('content_sha256') != digest(args.runtime / 'gameplay_content.json')):
        raise ValueError('Explicit verified candidate parity/provenance must match exact PCK and full runtime observations')
    runtime_files_before = manifest(args.runtime)
    project_hashes_before = {str(p.relative_to(args.project)): digest(p) for p in sorted(args.project.rglob('*'))
                             if p.is_file() and p.suffix in ['.gd', '.godot', '.tscn']}
    expected_counts = {'maps': 111, 'items': 1105, 'skills': 262, 'monsters': 644, 'npcs': 84}
    actual_counts = {key: len(content[key]) for key in expected_counts}
    if actual_counts != expected_counts:
        raise ValueError('Exact G2 delivery counts are required: ' + json.dumps(actual_counts))
    if original_payload['character']['map_id'] != args.safe_map or original_payload['character']['dead']:
        raise ValueError('Earned save must already be alive in the requested safe town; no travel/return callback is permitted')
    if len(original_payload['monsters']) != args.expected_monsters:
        raise ValueError('Unexpected saved monster count; no IDs may be removed')
    if any(m['alive'] and m['map_id'] == args.safe_map for m in original_payload['monsters'].values()):
        raise ValueError('The selected town contains live monsters; this probe must not become combat')
    output.mkdir(parents=True)
    operator_source = Path(__file__).read_bytes()
    (output / 'operator-source.py').write_bytes(operator_source)
    temporary = Path(tempfile.mkdtemp(prefix='baram-cold-resume-'))
    isolated = temporary / 'data' / args.user_dir_name
    shutil.copytree(source, isolated)
    imported_files = manifest(isolated)
    if imported_files != original_files:
        raise RuntimeError('Byte-identical userdata import failed')
    checkpoint = isolated / 'gameplay-checkpoints.jsonl'
    checkpoint.unlink(missing_ok=True)  # Only the isolated copy of old diagnostics.
    savefile = isolated / 'gameplay-p3/characters' / original_saves[0].name
    env = os.environ.copy()
    env.update(XDG_DATA_HOME=str(temporary / 'data'), XDG_CONFIG_HOME=str(temporary / 'config'),
               XAUTHORITY='', GODOT_SILENCE_ROOT_WARNING='1')
    for key in ['BARAM_GAMEPLAY_RUNTIME', 'BARAM_P2_RUNTIME']:
        env.pop(key, None)
    command = [str(args.godot.resolve()), '--audio-driver', 'Dummy', '--main-pack', str(args.pack.resolve())]
    started = time.monotonic()
    input_path = temporary / 'os-input-timeline.jsonl'
    process = None
    x = None
    recorder = None
    active_phase = None
    phase_results = []
    result = {'schema': 'baram.os-cold-resume/1',
              'scope': 'Exact exported PCK, full G2, two ordinary Linux XTEST processes, each20s safe-town movement/autosave/menu. No callbacks/grants/combat/trades. Not long-play/native/physical/IME/audio proof.',
              'requested_seconds': 40, 'phase_seconds': 20, 'cold_resume_probe': True,
              'checks': [], 'observations': [], 'operator_sha256': hashlib.sha256(operator_source).hexdigest(),
              'exact_pack_sha256': digest(args.pack),
              'runtime_manifest_sha256': digest(args.runtime / 'runtime.json'),
              'content_sha256': digest(args.runtime / 'gameplay_content.json'),
              'associated_candidate_files': [{'file': str(p.resolve()), 'sha256': digest(p)} for p in args.candidate_file],
              'project_source_sha256': project_hashes_before,
              'candidate_provenance': {'file': str(args.pack_provenance.resolve()), 'sha256': digest(args.pack_provenance),
                                       'source_commit': pack_provenance.get('source_commit'), 'document': pack_provenance},
              'runtime_input_file_count': len(runtime_files_before),
              'environment': {'platform': sys.platform, 'display': env.get('DISPLAY'), 'screen': '1600x1000', 'game_viewport': '1100x720', 'recording_fps': 30, 'audio': 'Dummy'},
              'continued_naturally_earned_data': {'directory': str(args.resume_data.resolve()), 'from_user_dir': args.resume_user_dir_name, 'to_user_dir': args.user_dir_name, 'files': original_files, 'method': 'Byte-identical isolated userdata copy; original never written. Not authenticated account sync.'},
              'full_G2_counts': actual_counts, 'isolated_session_directory': str(temporary),
              'analysis_scope': 'Use per-phase first-process and restart-process directories with run_playability_analysis.py. Top-level journey/restart traces are independently retained; do not concatenate process clocks or treat this40s probe as1800s.'}

    def log(kind, **details):
        row = {'kind': kind, 'phase': active_phase, 'wall_unix_ns': time.time_ns(),
               'operator_elapsed_s': round(time.monotonic() - started, 3), **details}
        with input_path.open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        return row

    def observe(name, **details):
        row = log('observation', name=name, **details)
        result['observations'].append(row)
        (output / 'progress.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return row

    def check(identifier, okay, details=None):
        row = {'id': identifier, 'status': 'PASS' if okay else 'FAIL', 'details': details, 'phase': active_phase}
        result['checks'].append(row)
        return bool(okay)

    def ensure(identifier, okay, details=None):
        if not check(identifier, okay, details):
            raise RuntimeError(identifier)

    def run(*items):
        subprocess.run([str(args.xdotool.resolve()), *map(str, items)], env=env,
                       capture_output=True, check=True, timeout=10)

    def key(name):
        run('windowfocus', '--sync', x.window)
        log('key', key=name, hold_s=0, method='single XTEST key press/release, no held-key repeat')
        # Production _input advances once on the non-echo press. Dispatch the
        # release in the same xdotool process so scheduler gaps cannot extend
        # a Python sleep/second-subprocess hold into an unintended exit walk.
        run('key', '--clearmodifiers', '--delay', '0', name)

    def button(text):
        layout = next((row['details'] for row in reversed(rows(checkpoint)) if row.get('stage') == 'ui_layout'), {})
        control = next((row for row in layout.get('controls', []) if row.get('text') == text), None)
        if control is None:
            raise RuntimeError('Visible ordinary control absent: ' + text)
        rect = control['rect']
        if rect[1] < 0 or rect[1] + rect[3] > 720:
            raise RuntimeError('Ordinary control is clipped: ' + text)
        px, py = int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)
        run('windowfocus', '--sync', x.window)
        log('mouse_click', x=px, y=py, button=1, description=text)
        run('mousemove', '--window', x.window, px, py)
        run('click', '1')

    def wait_stage(stage, since=0, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = [row for row in rows(checkpoint)[since:] if row.get('stage') == stage]
            if found:
                return found[-1]
            if process.poll() is not None:
                raise RuntimeError('Process exited before ' + stage)
            time.sleep(.1)
        raise TimeoutError('Checkpoint not observed: ' + stage)

    def payload():
        return json.loads(savefile.read_text())['payload']

    def stable_preserved(before, after):
        return (all(before.get(key) == after.get(key) for key in ['inventory', 'equipment', 'skills', 'hotkeys', 'bank_inventory', 'monsters'])
                and all(before['character'].get(key) == after['character'].get(key) for key in ['id', 'owner_id', 'name', 'nationality', 'guardian', 'appearance', 'job', 'desired_job', 'level', 'xp', 'money'])
                and len(after['monsters']) == args.expected_monsters)

    def safe_direction(current):
        character = current['character']; map_id = character['map_id']
        if map_id != args.safe_map:
            raise RuntimeError('Ordinary input left the safe town')
        definition = content['maps'][map_id]
        blocked = {tuple(cell) for cell in definition.get('blocked', [])}
        blocked.update((int(n['x']), int(n['y'])) for n in content['npcs'].values() if n['map_id'] == map_id)
        blocked.update((int(e['x']), int(e['y'])) for e in definition.get('exits', []))
        blocked.update((int(m['x']), int(m['y'])) for m in current['monsters'].values() if m['alive'] and m['map_id'] == map_id)
        origin = int(character['x']), int(character['y'])
        # Alternate toward the original cell when possible, otherwise pick the
        # first adjacent legal non-exit tile. A single press/release avoids
        # held-key repeat; every actual autosaved result is checked afterward.
        home = (int(original_payload['character']['x']), int(original_payload['character']['y']))
        candidates = [('Up', 0, -1), ('Right', 1, 0), ('Down', 0, 1), ('Left', -1, 0)]
        candidates.sort(key=lambda row: abs(origin[0] + row[1] - home[0]) + abs(origin[1] + row[2] - home[1]))
        for name, dx, dy in candidates:
            destination = origin[0] + dx, origin[1] + dy
            if destination not in blocked and 0 <= destination[0] < definition['width'] and 0 <= destination[1] < definition['height']:
                return name, destination
        raise RuntimeError('No adjacent safe town tile; do not teleport or modify the save')

    def capture(name):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'x11grab', '-video_size', '1600x1000', '-i', env['DISPLAY'], '-frames:v', '1', str(output / (name + '.png'))], env=env, capture_output=True, check=True, timeout=20)
        log('screenshot', name=name)

    def terminate():
        nonlocal process, x
        if x:
            x.close(); x = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        process = None

    def one_phase(name, before):
        nonlocal process, x, active_phase
        active_phase = name
        phase_start = time.monotonic(); since = len(rows(checkpoint)); check_start = len(result['checks'])
        trace = temporary / (name + '-frame-timeline.jsonl')
        env['BARAM_PLAYABILITY_TRACE'] = str(trace)
        game_log = temporary / (name + '.log')
        with game_log.open('wb') as stream:
            process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
            pid = process.pid
            observe('cold_process_started', pid=pid, command=command, trace_file=str(trace))
            wait_stage('ui_layout', since); x = X11(env)
            click_start = len(rows(checkpoint)); button('이어 하기')
            loaded = wait_stage('loaded', click_start)['details']
            ensure(name + '_loaded_exact_saved_character', loaded.get('character') == before['character'], loaded)
            observe('cold_process_loaded', character=loaded['character'], revision=loaded.get('revision'))
            capture(name + '-loaded')
            movement_start = time.monotonic(); last_save_count = len([r for r in rows(checkpoint) if r.get('stage') == 'save'])
            observed_moves = []; observed_autosaves = 0
            while time.monotonic() - movement_start < 20:
                current = payload(); direction, intended = safe_direction(current)
                key(direction)
                deadline = time.monotonic() + 4.5
                while time.monotonic() < deadline:
                    checkpoints_now = rows(checkpoint)
                    if any(r.get('stage') == 'save_failed' for r in checkpoints_now[since:]):
                        raise RuntimeError('Actual application save_failed checkpoint')
                    count = len([r for r in checkpoints_now if r.get('stage') == 'save'])
                    if count > last_save_count:
                        observed_autosaves += count - last_save_count; last_save_count = count
                        break
                    if process.poll() is not None:
                        raise RuntimeError('Ordinary process exited during town movement')
                    time.sleep(.1)
                else:
                    raise TimeoutError('Ordinary autosave was not observed')
                after = payload()
                ensure(name + '_autosave_preserves_owned_progress_' + str(len(observed_moves)), stable_preserved(before, after))
                ensure(name + '_stays_in_safe_town_' + str(len(observed_moves)), after['character']['map_id'] == args.safe_map)
                ensure(name + '_single_OS_press_moves_to_safe_neighbor_' + str(len(observed_moves)),
                       (int(after['character']['x']), int(after['character']['y'])) == intended,
                       {'key': direction, 'expected_cell': intended, 'observed_character': after['character']})
                observed_moves.append({'key': direction, 'intended_cell': intended, 'before_character': current['character'], 'after_character': after['character'], 'revision': after['revision']})
                observe('cold_town_autosave_observed', autosaves=observed_autosaves, movement=observed_moves[-1])
            elapsed = time.monotonic() - movement_start
            ensure(name + '_20s_unaccelerated_movement', elapsed >= 20 and any((r['before_character']['x'], r['before_character']['y']) != (r['after_character']['x'], r['after_character']['y']) for r in observed_moves), {'seconds': elapsed, 'moves': observed_moves})
            ensure(name + '_multiple_ordinary_autosaves', observed_autosaves >= 4, observed_autosaves)
            capture(name + '-before-menu')
            menu_start = len(rows(checkpoint)); button('저장 · 처음으로')
            wait_stage('performance', menu_start); wait_stage('ui_layout', menu_start)
            after = payload()
            ensure(name + '_normal_menu_save_preserves_all752_monsters_and_owned_progress', stable_preserved(before, after))
            ensure(name + '_revision_and_ui_requests_advance', after['revision'] > before['revision'] and after['request_watermarks'].get('ui', 0) > before['request_watermarks'].get('ui', 0))
            phase_checkpoints = rows(checkpoint)[since:]
            saves = [r for r in phase_checkpoints if r.get('stage') == 'save']
            ensure(name + '_actual_save_statuses_and_no_save_failed', saves and all(r.get('details', {}).get('status') == 'SAVED' for r in saves) and not any(r.get('stage') == 'save_failed' for r in phase_checkpoints), saves)
            ensure(name + '_independent_trace_flushed', trace.is_file() and trace.stat().st_size > 0)
            observe('cold_process_saved_to_menu', character=after['character'], revision=after['revision'], seconds=elapsed)
        terminate()
        errors = [line for line in game_log.read_text(errors='replace').splitlines() if 'ERROR:' in line or 'SCRIPT ERROR' in line]
        ensure(name + '_no_engine_errors', not errors, errors)
        phase_results.append({'name': name, 'pid': pid, 'command': command, 'wall_seconds': round(time.monotonic() - phase_start, 3), 'movement_seconds': elapsed, 'checks': result['checks'][check_start:], 'before': before, 'final': after, 'trace': trace, 'game_log': game_log, 'engine_error_lines': errors, 'save_checkpoints': saves,
                              'performance_checkpoints': [r for r in phase_checkpoints if r.get('stage') in ['performance', 'frame_timing']]})
        return after

    try:
        ensure('source_userdata_byte_identical_import', imported_files == original_files)
        ensure('copied_original_primary_save_bytes_exact', digest(savefile) == digest(original_saves[0]))
        recorder_progress = temporary / 'recorder-progress.txt'
        recorder = subprocess.Popen(['ffmpeg', '-loglevel', 'warning', '-progress', str(recorder_progress), '-y', '-f', 'x11grab', '-draw_mouse', '1', '-framerate', '30', '-video_size', '1600x1000', '-i', env['DISPLAY'], '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '29', '-pix_fmt', 'yuv420p', str(temporary / 'ordinary-unedited.mkv')], env=env, stdout=(temporary / 'recorder.log').open('wb'), stderr=subprocess.STDOUT)
        log('video_recording_started', recorder_pid=recorder.pid)
        recording_deadline = time.monotonic() + 10
        raw = temporary / 'ordinary-unedited.mkv'
        while True:
            if recorder.poll() is not None or time.monotonic() >= recording_deadline:
                raise RuntimeError('Raw recorder did not become ready before first application launch')
            progress = rows_text = recorder_progress.read_text() if recorder_progress.is_file() else ''
            fields = {}
            for line in rows_text.splitlines():
                if '=' in line:
                    field, value = line.split('=', 1)
                    if value.strip().isdigit(): fields[field] = int(value.strip())
            # A small black-screen MKV may stay wholly inside AVIO's output
            # buffer. Actual encoded-frame progress, not file size or merely
            # a live process, proves capture readiness before launching Godot.
            if fields.get('frame', 0) > 0:
                break
            time.sleep(.1)
        observe('raw_recorder_ready_before_first_process', encoded_frames=fields['frame'],
                recorder_alive=recorder.poll() is None, progress=progress,
                raw_bytes=raw.stat().st_size if raw.is_file() else 0)
        result['before_restart'] = one_phase('first-process', original_payload)
        result['final'] = one_phase('restart-process', result['before_restart'])
    except Exception as error:
        result['error'] = str(error); observe('operator_stopped', error=str(error))
        try:
            capture('failure')
            if process and process.poll() is None and x:
                button('저장 · 처음으로'); time.sleep(.8)
        except Exception as recovery:
            observe('ordinary_error_recovery_incomplete', error=str(recovery))
    finally:
        terminate()
        if recorder:
            if recorder.poll() is None:
                recorder.send_signal(signal.SIGINT)
                try:
                    recorder.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    recorder.kill(); recorder.wait()
            raw = temporary / 'ordinary-unedited.mkv'; video = temporary / 'ordinary-unedited.mp4'
            try:
                remux = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-c', 'copy', str(video)], capture_output=True, timeout=60)
                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size', '-show_entries', 'stream=r_frame_rate,nb_frames', '-of', 'json', str(video)], capture_output=True, text=True, timeout=30)
                metadata = json.loads(probe.stdout) if probe.returncode == 0 else {}
                result['video_validation'] = {'remux_returncode': remux.returncode, 'ffprobe_returncode': probe.returncode, 'metadata': metadata, 'stderr': probe.stderr or remux.stderr.decode(errors='replace'), 'scope': 'One continuous raw capture across both real processes and intervening menus; stream-copy remux only.'}
                check('unedited_video_readable_and_duration', remux.returncode == 0 and probe.returncode == 0 and float(metadata.get('format', {}).get('duration', 0)) >= 40, result['video_validation'])
                if video.is_file():
                    shutil.copy2(video, output / 'ordinary-unedited.mp4')
                    check('remuxed_video_copied_byte_exact', digest(output / 'ordinary-unedited.mp4') == digest(video))
                    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(video), '-f', 'null', '-'], capture_output=True, timeout=60)
                    decoded_cleanly = decoded.returncode == 0 and not decoded.stderr.strip()
                    decode = {'status': 'PASS_FULL_VIDEO_DECODE' if decoded_cleanly else 'FAIL_FULL_VIDEO_DECODE', 'returncode': decoded.returncode, 'video_sha256': digest(video), 'stderr': decoded.stderr.decode(errors='replace'), 'xerror': True}
                    (output / 'VIDEO_DECODE.json').write_text(json.dumps(decode, ensure_ascii=False, indent=2) + '\n')
                    check('whole_unedited_video_decodes', decoded_cleanly, decode)
            except Exception as error:
                result['video_error'] = str(error); check('unedited_video_finalize', False, str(error))
            # Preserve the original stream even when remux/probe/decode fails.
            if raw.is_file():
                shutil.copy2(raw, output / 'ordinary-unedited.mkv')
                result['raw_video_sha256'] = digest(raw)
                check('raw_original_video_copied_byte_exact', digest(output / 'ordinary-unedited.mkv') == result['raw_video_sha256'])
        active_phase = None
        check('original_userdata_all_bytes_unchanged', manifest(source) == original_files)
        result['original_userdata_final_manifest'] = manifest(source)
        check('exact_pack_bytes_unchanged_after_run', digest(args.pack) == result['exact_pack_sha256'])
        check('candidate_provenance_bytes_unchanged_after_run', digest(args.pack_provenance) == result['candidate_provenance']['sha256'])
        check('runtime_all_input_bytes_unchanged_after_run', manifest(args.runtime) == runtime_files_before)
        check('observed_project_source_bytes_unchanged_after_run',
              {str(p.relative_to(args.project)): digest(p) for p in sorted(args.project.rglob('*'))
               if p.is_file() and p.suffix in ['.gd', '.godot', '.tscn']} == project_hashes_before)
        check('associated_candidate_bytes_unchanged_after_run',
              all(digest(Path(row['file'])) == row['sha256'] for row in result['associated_candidate_files']))
        for path in sorted(temporary.iterdir()):
            if path.is_file() and path.suffix not in ['.mkv', '.mp4']:
                shutil.copy2(path, output / path.name)
        shutil.copytree(temporary / 'data', output / 'data', dirs_exist_ok=True)
        first_trace = temporary / 'first-process-frame-timeline.jsonl'
        restart_trace = temporary / 'restart-process-frame-timeline.jsonl'
        if first_trace.is_file(): shutil.copy2(first_trace, output / 'journey-frame-timeline.jsonl')
        if restart_trace.is_file(): shutil.copy2(restart_trace, output / 'restart-frame-timeline.jsonl')
    result['wall_seconds'] = round(time.monotonic() - started, 3)
    result['performance_checkpoints'] = [r for r in rows(checkpoint) if r.get('stage') in ['performance', 'frame_timing']]
    result['engine_error_lines'] = [line for p in temporary.glob('*-process.log') for line in p.read_text(errors='replace').splitlines() if 'ERROR:' in line or 'SCRIPT ERROR' in line]
    check('both_real_processes_completed', len(phase_results) == 2, [p['name'] for p in phase_results])
    check('no_ordinary_engine_errors', not result['engine_error_lines'], result['engine_error_lines'])
    result['status'] = 'FAIL' if result.get('error') or any(r['status'] != 'PASS' for r in result['checks']) else 'PASS_OBSERVED_SCOPE'
    result['phase_results'] = [{k: v for k, v in p.items() if k not in ['trace', 'game_log', 'before', 'final']} for p in phase_results]
    all_inputs = rows(input_path)
    for phase in phase_results:
        phase_dir = output / phase['name']; phase_dir.mkdir()
        phase_report = {k: v for k, v in result.items() if k not in ['phase_results', 'evidence_files', 'observations', 'performance_checkpoints', 'before_restart', 'final', 'wall_seconds', 'checks']}
        phase_report.update(scope=result['scope'] + ' Independent ' + phase['name'] + '20s trace only; shared whole video covers both processes.', requested_seconds=20, wall_seconds=phase['wall_seconds'], checks=phase['checks'], observations=[r for r in result['observations'] if r.get('phase') == phase['name']], before_restart=phase['before'], final=phase['final'], engine_error_lines=phase['engine_error_lines'], performance_checkpoints=phase['performance_checkpoints'])
        phase_report['status'] = 'PASS_OBSERVED_SCOPE' if all(r['status'] == 'PASS' for r in phase['checks']) else 'FAIL'
        shutil.copy2(phase['trace'], phase_dir / 'journey-frame-timeline.jsonl')
        shutil.copy2(phase['game_log'], phase_dir / 'game.log')
        (phase_dir / 'os-input-timeline.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in all_inputs if r.get('phase') == phase['name']))
        (phase_dir / 'OS_PLAYABILITY.json').write_text(json.dumps(phase_report, ensure_ascii=False, indent=2) + '\n')
    result['analysis_commands'] = [[sys.executable, str(Path(__file__).with_name('run_playability_analysis.py')), str(output / p['name'])] for p in phase_results]
    result['evidence_files'] = [{'file': str(p.relative_to(output)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'OS_PLAYABILITY.json']
    (output / 'OS_PLAYABILITY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'error': result.get('error'), 'wall_seconds': result['wall_seconds'], 'output': str(output)}, ensure_ascii=False), flush=True)
    return 0 if result['status'] == 'PASS_OBSERVED_SCOPE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
