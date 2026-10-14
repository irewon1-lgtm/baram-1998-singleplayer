#!/usr/bin/env python3
"""Create durable private results with pinned resources, launch script and Git history."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from legacy_assets import private_path

ROOT=Path(__file__).resolve().parents[1]
LAUNCH='''#!/bin/sh
set -eu
baram_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export XDG_DATA_HOME="$baram_dir/.local/data"
export XDG_CONFIG_HOME="$baram_dir/.local/config"
export XDG_CACHE_HOME="$baram_dir/.local/cache"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$baram_dir/saves"
if [ -n "${BARAM_AUDIO_DRIVER:-}" ]; then
    exec "$baram_dir/engine/godot" --path "$baram_dir/game" --audio-driver "$BARAM_AUDIO_DRIVER" -- --assets="$baram_dir/private_assets" --save="$baram_dir/saves/character.json" "$@"
fi
exec "$baram_dir/engine/godot" --path "$baram_dir/game" -- --assets="$baram_dir/private_assets" --save="$baram_dir/saves/character.json" "$@"
'''
README='''# 바람의나라 개인용 오프라인 게임

이 ZIP은 개인용 자료다. 원본·추출·파생 그림과 WAV를 공개 GitHub에 올리지 않는다.

Linux x86_64 그래픽 화면에서 압축을 풀고 `chmod +x launch-linux.sh engine/godot` 후
`./launch-linux.sh`를 실행한다. Linux용 Godot 4.6.3 엔진이 포함되어 인터넷과 서버가 필요 없다.
OpenGL/X11이 있는 데스크톱 환경을 사용한다. Windows 실행 파일은 제공·검증하지 않았다.

화살표/WASD 이동, Shift+화살표 제자리 방향, Space 공격, Enter NPC 대화,
G/쉼표 줍기, I 물품, K 배운 기술, E 장착, U 사용, 1~3 기술, F5 저장, F6 복구.
Esc로 창을 닫거나 저장 후 정지하고 Q로 종료한다. 상점은 B 구매·V 판매·R 수리·C 요리.

원본 북미 4.95 지형 38개와 한국 4.91 공유 그림을 사용한다. 옛 8개 제작 맵은 소스에
보존했다. 마을의 길잡이가 주막·대장간·네 직업 수련원·상점 이동을 돕고, 들판에서
쥐굴·뱀굴·곰굴·감옥·토끼굴로 이동한다. 원본 마을 문으로 들어가고 나올 수도 있다.
수련원에서 기술을 배우고 K에서 1~3에 지정한다. 옷/무기 장착은 실제 모습과 계산에 반영된다.
1~30 수치와 99레벨 경험치 계산은 보존되어 있으나 네 직업 30/99 완주와 승급은 미검증이다.
몬스터 일부·기술 효과·음원 역할은 대체 연결이며 원작 동일성이 확인되지 않았다.

첨부 타일 14,835개와 추가 원본 타일 35,269개를 별도 ID로 등록했다. 중복 그림은
원장에서 연결하며 두 ID를 두 고유 그림으로 세지 않는다. 실제 활용·미활용 해결 내역은
docs/development/runs/20261014-assets/asset-game-summary.json와 tile-status-current.json을 읽는다.
원본 5개와 첨부 ZIP은 original_archives에 보존한다. 수치·연구 원본은 Git bundle에도 있다.
다음 개발에서 `git clone -b dev/codex-asset-runtime-20261014 development.bundle recovered-code`로 복구한다.

최신 기준 브랜치 dev/codex-asset-intake-20261014의 80d3da1과 상세 기준서를 읽고
현재 개발 계보에 앞으로 병합했다. 원격 SHA와 상태는 최신 CHECKPOINT와 재조회 기록을 읽는다.
main/reset/force push를 하지 않는다. 전체 연락시트는 private_assets/review/index.html에서 찾는다.
새 캐릭터로 시작하거나, saves가 비어 있을 때 resume_saves/natural_level6.json을
saves/character.json으로 복사해 실제 이전 캐릭터를 이어갈 수 있다. 기존 저장은 먼저 보존한다.
FINAL_VERIFICATION.json이 있으면 압축 해제 후 실제 실행·복구 증거와 입력 해시를 읽는다.
코드 인계 커밋 시점의 CHECKPOINT와 최종 생성된 실행 증거의 작성 시간을 구분한다.
'''


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build(a):
    private=private_path(a.private)
    output=private_path(a.out)
    output.mkdir(parents=True,exist_ok=True)
    staging=output/'baram_playable_PRIVATE_20261014'
    if staging.exists() and not a.refresh_existing:raise ValueError('Existing result directory is preserved; choose a fresh output')
    staging.mkdir(exist_ok=True)
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if branch!=a.branch:raise ValueError('Unexpected development branch')
    tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    for name in tracked:
        p=Path(name)
        if p.parts[0] in ['game','tools','tests'] or name.startswith('docs/development/'):
            dest=staging/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dest)
    shutil.copytree(private/'game-assets',staging/'private_assets',dirs_exist_ok=True)
    shutil.copytree(private/'game-licenses',staging/'licenses',dirs_exist_ok=True)
    (staging/'engine').mkdir(exist_ok=True)
    shutil.copy2(a.godot,staging/'engine/godot')
    originals=staging/'original_archives';originals.mkdir(exist_ok=True)
    recovery=json.loads((ROOT/'docs/development/runs/20261014-resume/input-recovery.json').read_text())
    # Use the already pinned archive ledger, rejecting changed files during packaging.
    pins={'491v.zip':'f11e448db6478b1aca3a7dd47403bdef00cf873b203b14629b0215632190532f',
          'NexusTK_v4.0.3.7z':'db89e2b1ac3dfd3f5668fd7746478507b370ee627b4321d7dec441620ce96b53',
          'NexusTK_V_4.66.7z':'54ca6b8892a2b44ddfaadebc92e1886a770ac07a82b60ceacbfd3e2e44e5774a',
          'nexus495.exe':'486f4684b76658d92eaf84aab77fe9be9489ea01de8264fe90d0040466620aaa',
          'BARAM.PAL':'34bee372e754fc423099193587ae265b731d7f7ff0f083a87cb564179aeb266a'}
    for name,pin in pins.items():
        p=private/'archives'/name
        if sha(p)!=pin:raise ValueError('Original SHA mismatch: '+name)
        shutil.copy2(p,originals/name)
    handoff=Path(a.handoff)
    if sha(handoff)!='f36929c43d775058678a708a1da7a140ea13e0e9243d5f4fc2b5e304fa54500b':raise ValueError('Handoff SHA mismatch')
    shutil.copy2(handoff,originals/'baram_Codex_tile_handoff_PRIVATE.zip')
    evidence=staging/'private_evidence';evidence.mkdir(exist_ok=True)
    for name in ['game-screen-run2','game-screen-run3','game-screen-run4','game-screen-run5','game-screen-resume6','game-screen-classes','game-screen-classes2','review','source-screen-1','content-screen-1','content-screen-2','content-screen-fixed-1','content-screen-fixed-2','content-actions-screen','cure-actions-screen','town-all-screen','town-all-screen-fixed','town-all-screen-resume','town-all-screen-resume2','town-all-screen-final','town-all-screen-last-room','natural-progress-screen','gear-guide-screen','gear-guide-screen-fixed','expansion-unpacked-screen']:
        source=private/name
        if source.exists():shutil.copytree(source,evidence/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('data','cache','config'))
    comparisons=evidence/'comparisons';comparisons.mkdir(exist_ok=True)
    for name in ['town-before-after_PRIVATE.png','light-before-after_PRIVATE.png','outfit-before-after_PRIVATE.png']:
        source=output/name
        if source.is_file():shutil.copy2(source,comparisons/name)
    natural=private/'natural-progress-screen/natural-progress/character.json'
    if natural.is_file():
        saved=json.loads(natural.read_text());payload=json.loads(saved['payload'])
        if 'validation_fixture' in payload['player']:raise ValueError('Natural continuation must not be a prepared test fixture')
        resume=staging/'resume_saves';resume.mkdir(exist_ok=True);shutil.copy2(natural,resume/'natural_level6.json')
    final_proof=private/'expansion-final-verification.json'
    if final_proof.is_file():shutil.copy2(final_proof,staging/'FINAL_VERIFICATION.json')
    final_screen=private/'expansion-unpacked-final'
    if final_screen.is_dir():shutil.copytree(final_screen,evidence/'expansion-unpacked-final',dirs_exist_ok=True,ignore=shutil.ignore_patterns('data','cache','config'))
    (staging/'launch-linux.sh').write_text(LAUNCH);(staging/'launch-linux.sh').chmod(0o755)
    (staging/'READ_ME.md').write_text(README)
    bundle=staging/'development.bundle'
    subprocess.run(['git','bundle','create',str(bundle),branch],cwd=ROOT,check=True,capture_output=True)
    verification=subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,capture_output=True,text=True)
    checkpoint=json.loads((ROOT/'docs/development/CHECKPOINT.json').read_text())
    manifest={'source_branch':branch,'source_commit':commit,
              'source_commit_scope':'GAME_CODE_RECIPES_AND_BUNDLED_HISTORY; GENERATED_LEDGERS_PRIVATE_ASSETS_AND_VERIFICATION_HASHED_IN_FILES',
              'private_only':True,'remote_publication':checkpoint.get('remote_status','PENDING_READBACK'),
              'files':[{'path':str(p.relative_to(staging)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(staging.rglob('*')) if p.is_file() and p.name!='PACKAGE_MANIFEST.json'],
              'git_bundle_verification':verification.stdout+verification.stderr,
              'original_archive_pins':pins,'core_generated_content':{'native_layouts':38,'legacy_authored_layouts_preserved':8,'items':3,'training_skills':1,'quests':2,'outfit_color_parameters':6,'new_independent_bitmaps':0},
              'level30_validation':'CONTROLLED_SKILL_EQUIPMENT_FIXTURES_NOT_NATURAL_FOUR_JOB_PLAYTHROUGH'}
    (staging/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    packages=[]
    for name,full in [('baram_playable_PRIVATE_20261014.zip',True),('baram_assets_resume_PRIVATE_20261014.zip',False)]:
        dest=output/name
        with ZipFile(dest,'w',ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(staging.rglob('*')):
                if not p.is_file():continue
                rel=p.relative_to(staging)
                if not full and (rel.parts[0] in ['engine','original_archives','private_evidence'] or rel.name in ['development.bundle','launch-linux.sh'] or (rel.parts[:2]==('private_assets','review') and rel.suffix=='.png')):continue
                if not full and rel.name=='READ_ME.md':
                    z.writestr(str(Path(staging.name)/rel), '다음 작업용 자산·코드 ZIP입니다. 엔진·원본 압축·Git 전체 이력은 큰 실행 ZIP에 있습니다. Godot 4.6.3이 이미 설치되어 있으면 압축 폴더에서 `godot --path game -- --assets="$(pwd)/private_assets"`로 실행하세요.\n\n'+README)
                    continue
                z.write(p,str(Path(staging.name)/rel))
        with ZipFile(dest) as z:
            bad=z.testzip()
            if bad:raise ValueError('ZIP CRC failed: '+bad)
        packages.append({'path':str(dest),'bytes':dest.stat().st_size,'sha256':sha(dest),'zip_crc':'PASS_FULL_MEMBER_READ',
                         'contains_engine_and_original_archives':full,'files':len(z.namelist())})
    report={'status':'PASS_PACKAGING_NOT_YET_UNPACKED_PLAYTEST','source_commit':commit,'branch':branch,
            'packages':packages,'staging':str(staging),'remote_publication':checkpoint.get('remote_status','PENDING_READBACK')}
    Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--handoff',required=True)
    p.add_argument('--branch',default='dev/codex-asset-runtime-20261014')
    p.add_argument('--godot',default='/usr/local/bin/godot')
    p.add_argument('--report',required=True)
    p.add_argument('--refresh-existing',action='store_true',help='Refresh this task’s own unpublished package after source changes')
    build(p.parse_args())
