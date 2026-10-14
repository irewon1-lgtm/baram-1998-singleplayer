#!/usr/bin/env python3
"""Package one fixed Codex build and active private release; no user saves."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from baram_content import PackageStore,safe_relative

ROOT=Path(__file__).resolve().parents[1]
LAUNCH='''#!/bin/sh
set -eu
baram_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export XDG_DATA_HOME="$baram_dir/.local/data"
export XDG_CONFIG_HOME="$baram_dir/.local/config"
export XDG_CACHE_HOME="$baram_dir/.local/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$baram_dir/saves/v2"
if [ -n "${BARAM_AUDIO_DRIVER:-}" ]; then
  exec "$baram_dir/engine/godot" --path "$baram_dir/game" --audio-driver "$BARAM_AUDIO_DRIVER" -- --assets="$baram_dir/private_assets" --content="$baram_dir/private_content" --save="$baram_dir/saves/v2/character.json" "$@"
fi
exec "$baram_dir/engine/godot" --path "$baram_dir/game" -- --assets="$baram_dir/private_assets" --content="$baram_dir/private_content" --save="$baram_dir/saves/v2/character.json" "$@"
'''
WINDOWS='''@echo off
set "baram_dir=%~dp0"
if not exist "%baram_dir%engine\\godot.exe" (
  echo Godot 4.6.3 Windows executable is required at engine\\godot.exe.
  pause
  exit /b 1
)
"%baram_dir%engine\\godot.exe" --path "%baram_dir%game" --rendering-method gl_compatibility -- --assets="%baram_dir%private_assets" --content="%baram_dir%private_content" --save="%baram_dir%saves\\v2\\character.json" %*
'''
README='''# 개인용 오프라인 실행본

Linux x86_64: 압축 해제 후 `chmod +x engine/godot launch-linux.sh`와
`./launch-linux.sh`를 실행하세요. Godot 4.6.3, 현재 게임 코드와 검증된 활성
콘텐츠·자산이 포함됩니다. 게임 실행에는 인터넷과 서버가 필요 없습니다.

방향키/WASD 이동, Shift+방향키 방향, Space 공격, Enter/F 대화·이동,
G 줍기, I 물품(E 장착/U 사용), O 개별 장비(E 장착/X 해제/N 선택 강화),
K 기술과 1~3 단축키, F5 저장, F6 복구, Esc 메뉴, Q 종료입니다.
길잡이에게 초보 사냥터·실내 이동을 부탁하세요. 기존 마을 근처의
‘추가 지역 길목’에서 Work 지역으로 이동합니다. NPC 메뉴에서 거래·수련·
의뢰·제작·수리·휴식·승급 진행을 이용합니다. 강화는 N을 눌러 선택한
개인용 확장 규칙이며 기본 활성 기능이 아닙니다.

저장은 `saves/v2/character.json`입니다. 과거 저장을 쓰려면 원본을 보존한
사본을 별도 위치에 두고 `./launch-linux.sh --save=/절대경로/사본.json`으로
실행하세요. schema1은 같은 디렉터리의 v2 사본으로 이전하며 원본을
덮어쓰지 않습니다. 지원하지 않는 버전은 거부하고 새 게임으로 바꾸지 않습니다.
일반 백업 한 개와 필요할 때 legacy 원본/손상 원본 각 한 개를 보존합니다.

원작·파생 그림과 소리는 비공개 개인용 자료입니다. 이 ZIP을 공개 저장소에
올리지 마세요. 라이선스는 licenses에 있으며, 원본 설치 압축·미리보기·
사용자 저장·임시 캐시는 포함하지 않았습니다. 원본은 기존 비공개 자료에
보존돼 있습니다. intake_inputs의 고정 패키지와 private_content의 실행 정본은
서로 구분됩니다. 다음 개발에는 development.bundle의 codex/game-core와
integration/content-import/CODEX_STATE.md를 사용하세요.

구현/데이터 연결과 실제 육성 완주는 다릅니다. 네 직업 1~99 및 승급 데이터와
실행 기능은 연결됐지만 네 직업 자연 육성 완주, 전체 맵의 동적 통행,
장시간 안정성, 원작 동일성, 사용자 플레이는 미검증입니다. 새 확장 콘텐츠와
북미 지형 대체는 1998년 한국 원본 확인으로 표시하지 않습니다.

Windows 엔진 취득은 환경 프록시 403으로 차단됐습니다. Windows 실행 파일은
포함되지 않습니다. launch-windows.bat은 engine/godot.exe에 Godot 4.6.3을
제공한 뒤 사용하는 보조 실행 경로이며 Windows 실행 PASS가 아닙니다.
실제 코드/활성 manifest/Work 고정 패키지 대응은 PACKAGE_MANIFEST.json을 보세요.
'''

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(a):
    output=Path(a.out);output.mkdir(parents=True,exist_ok=True)
    stage=output/'baram_codex_core_PRIVATE_20261014'
    if stage.exists():raise ValueError('Existing package is preserved; choose a fresh output')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if branch!='codex/game-core':raise ValueError('Only the Codex integration branch may package')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Commit reviewed code and metadata before packaging the fixed build')
    stage.mkdir()
    paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    for name in paths:
        if name.startswith(('game/','integration/content-import/')) or name in ['tools/baram_content.py','tools/import_work_content.py','tools/rebuild_work_private.py','tools/rebuild_work_layout_members.py','tools/legacy_assets.py','tools/legacy_maps.py','tools/package_core.py']:
            destination=stage/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,destination)
    private=Path(a.assets);target=stage/'private_assets';target.mkdir()
    for directory in ['tiles','source_tiles','sprites','ui','fonts']:
        if (private/directory).is_dir():shutil.copytree(private/directory,target/directory)
    shutil.copy2(private/'actors.json',target/'actors.json')
    actors=json.loads((private/'actors.json').read_text())
    for member in set(actors.get('sound_bindings',{}).values())|{actors.get('font_path','')}:
        if not member:continue
        member=str(safe_relative(member));destination=target/member;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(private/member,destination)
    destination=target/'source_maps/world.json';destination.parent.mkdir(parents=True);shutil.copy2(private/'source_maps/world.json',destination)
    content=PackageStore(a.content,{})
    release=content.load();pointer=content.pointer()
    shutil.copytree(Path(a.content)/'releases'/pointer['release_id'],stage/'private_content/releases'/pointer['release_id'])
    # Deliver exactly the active immutable files; prior recovery copies remain
    # in the development vault, without duplicating all art in the player ZIP.
    delivered=pointer.copy();delivered['previous']=None
    (stage/'private_content/ACTIVE.json').write_text(json.dumps(delivered,indent=2)+'\n')
    shutil.copytree(a.licenses,stage/'licenses');(stage/'engine').mkdir();shutil.copy2(a.godot,stage/'engine/godot')
    (stage/'engine/godot').chmod(0o755)
    for name in ['assets001','assets002','content001','content002','content003','content004']:
        source=Path(a.inputs)/name
        if source.is_dir():shutil.copytree(source,stage/'intake_inputs'/name)
    build_info=dict(commit=commit,branch=branch,content_version=pointer['release_id'],runtime_envelope=release['version'],save_format=2)
    (stage/'game/data/build_info.json').write_text(json.dumps(build_info,indent=2)+'\n')
    (stage/'launch-linux.sh').write_text(LAUNCH);(stage/'launch-linux.sh').chmod(0o755)
    (stage/'launch-windows.bat').write_bytes(WINDOWS.replace('\n','\r\n').encode())
    (stage/'READ_ME.md').write_text(README)
    subprocess.run(['git','bundle','create',str(stage/'development.bundle'),'codex/game-core'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','bundle','verify',str(stage/'development.bundle')],cwd=ROOT,check=True,capture_output=True)
    manifest=dict(private_only=True,build=build_info,imports=release['imports'],
                  original_inputs_retained_outside_execution_zip=True,contains_user_saves=False,
                  windows_engine='BLOCKED_PROXY_403',windows_execution='NOT_RUN',
                  files=[dict(path=str(p.relative_to(stage)),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(stage.rglob('*')) if p.is_file()])
    (stage/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=output/(stage.name+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,stage.name+'/'+str(p.relative_to(stage)))
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('Archive CRC failed')
    report=dict(status='PASS_PACKAGING_NOT_YET_UNPACKED_RUNTIME',archive=str(archive),bytes=archive.stat().st_size,sha256=digest(archive),stage=str(stage),build=build_info)
    Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['out','assets','content','licenses','inputs','report']:p.add_argument('--'+key,required=True)
    p.add_argument('--godot',default='/usr/local/bin/godot')
    build(p.parse_args())
