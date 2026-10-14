#!/usr/bin/env python3
"""Repair a pinned user Windows ZIP with current startup code, exact private bytes,
no saves, no engine upgrade and a Unicode diagnostics launcher. Native Windows
execution is intentionally NOT_RUN until a Windows machine runs this package.
"""
import argparse, hashlib, json, os, shutil, struct, subprocess, zipfile
from pathlib import Path
from package_windows import safe_path, pe_info, verify_private_equivalence
ROOT=Path(__file__).resolve().parents[1]
PIN='7fe9b59e90410ec6af915797ccbb8e7630855574274c419d00fea0a32895baf2'
TEMPLATE_PIN='91724f15024a3a545e28ccd83134403d31ce2323a38e51c95e4dfa282f732ab6'
# Exporting updates the PE pck section's raw offset/size. The input ZIP is
# SHA-pinned; this prefix preserves its exact engine bytes and PE metadata.
EXPORTED_TEMPLATE_PIN='49381c8db2c312aff3d631f30c724a161e0eaedfb7adb3938c20b4adc198a522'
NAME='바람의나라_Windows64_수정본'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def build(a):
    source=Path(a.source).resolve();out=Path(a.out).resolve()
    if sha(source)!=PIN:raise ValueError('Input Windows ZIP changed')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if not branch.startswith('work/windows-startup-repair-'):raise ValueError('Use isolated repair branch')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    stage=out/NAME;project=out/'export-source'
    if stage.exists() or project.exists():raise ValueError('Previous outputs are preserved; choose a fresh directory')
    stage.mkdir(parents=True)
    with zipfile.ZipFile(source) as z:
        manifest_names=[n for n in z.namelist() if n.endswith('/PACKAGE_MANIFEST.json')]
        if len(manifest_names)!=1:raise ValueError('Expected one package')
        prefix=manifest_names[0].removesuffix('PACKAGE_MANIFEST.json')
        old=json.loads(z.read(manifest_names[0]))
        if not old.get('private_only') or old.get('contains_user_saves') is not False:raise ValueError('Unsafe package scope')
        for row in old['files']:
            rel=str(safe_path(row['path']))
            raw=z.read(prefix+rel)
            if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Original byte mismatch: '+rel)
            if rel.startswith(('private_assets/','private_content/','licenses/')):
                dst=stage/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
        exe=z.read(prefix+'바람의나라.exe')
    equivalence=verify_private_equivalence(old,stage)
    size,magic=struct.unpack('<QI',exe[-12:]);offset=len(exe)-12-size
    if magic!=0x43504447 or exe[offset:offset+4]!=b'GDPC':raise ValueError('Embedded pack footer invalid')
    template=out/'original-template.exe';template.write_bytes(exe[:offset])
    if sha(template)!=EXPORTED_TEMPLATE_PIN:raise ValueError('Packaged Windows engine prefix changed')
    pe_info(template)
    shutil.copytree(ROOT/'game',project,ignore=shutil.ignore_patterns('.godot','export_presets.cfg'))
    cfg=(project/'project.godot').read_text().replace('run/main_scene="res://main.tscn"','run/main_scene="res://windows_bootstrap.tscn"')
    (project/'project.godot').write_text(cfg)
    write_json(project/'data/build_info.json',dict(commit=commit,branch=branch,content_version=old['build']['content_version'],runtime_envelope=2,save_format=2))
    presets='''[preset.0]
name="Windows64"
platform="Windows Desktop"
runnable=true
export_filter="all_resources"
include_filter="*.json"
exclude_filter=""
export_path=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=1
[preset.0.options]
custom_template/debug=""
custom_template/release=TEMPLATE
binary_format/embed_pck=true
binary_format/architecture="x86_64"
debug/export_console_wrapper=0
codesign/enable=false
application/modify_resources=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
'''
    (project/'export_presets.cfg').write_text(presets.replace('TEMPLATE',json.dumps(str(template))))
    (stage/'engine').mkdir()
    env=dict(os.environ)
    for key,folder in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
        p=out/'build-local'/folder;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
    commands=[[a.godot,'--headless','--editor','--path',str(project),'--import','--quit'],[a.godot,'--headless','--path',str(project),'--export-release','Windows64',str(stage/'engine/BaramEngine.exe')],
              [a.cc,'-O2','-Wall','-Wextra','-Werror','-municode','-mwindows','-static-libgcc','-s',str(ROOT/'tools/windows_launcher.c'),'-o',str(stage/'바람의나라.exe'),'-lshell32']]
    for i,command in enumerate(commands):
        r=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180)
        log=r.stdout+r.stderr;(out/f'build-{i}.log').write_text(log)
        if r.returncode or 'SCRIPT ERROR:' in log or '\nERROR:' in log:raise ValueError('Build failed; see build-'+str(i)+'.log')
    pe_info(stage/'engine/BaramEngine.exe');pe_info(stage/'바람의나라.exe')
    readme='''바람의나라 · Windows 실행 수정본

1. ZIP에서 "모두 압축 풀기"를 누릅니다.
2. 새 폴더 안의 "바람의나라.exe"를 더블클릭합니다.
3. 게임 준비 화면이 끝나면 캐릭터를 만들거나 저장한 여정을 계속합니다.

처음 준비하는 동안 진행 내용과 경과 시간이 표시됩니다.
준비가 정지하면 다른 그래픽 방식으로 한 번 자동 재시도합니다.
게임 폴더 안의 engine, private_assets, private_content를 함께 둬야 합니다.
인터넷, Godot, Python, 개발 환경 설치는 필요 없습니다.

방향키/WASD 이동 / Space 공격 / Enter 또는 F 대화
G 줍기 / I 물품 / E 장착 / K 기술 / 1~3 기술
F5 저장 / F6 복구 / Esc 메뉴 / Q 종료

기존 저장 위치는 그대로 유지합니다:
%LOCALAPPDATA%\\BaramSinglePlayer\\saves\\v2\\character.json
새 ZIP에는 사용자 저장 파일이 없으며, 기존 저장을 지우거나 초기화하지 않습니다.

오류가 나면 "실행로그" 폴더가 자동으로 열립니다.
폴더 쓰기가 제한되면 %LOCALAPPDATA%\\BaramSinglePlayer\\logs를 사용합니다.
문제가 계속되면 이 실행로그 폴더를 ZIP으로 압축해 보내면 됩니다.

실제 Windows 11에서 이 수정본으로 플레이하는 검증은 아직 하지 않았습니다.
실행검증.json에 이 환경에서 실제 실행한 범위만 기록했습니다.
전체 원작 복원, 모든 직업 1~99 완주와 전체 맵 통행은 이번 실행 오류 복구의 검증 범위가 아닙니다.
'''
    (stage/'처음읽기.txt').write_text(readme,encoding='utf-8-sig')
    checks=dict(windows_native_execution='NOT_RUN',windows_launcher_native_execution='NOT_RUN',linux_embedded_pck_execution='NOT_RUN',private_equivalence=equivalence,save_format=2,user_pc_action='EXTRACT_ALL_AND_DOUBLE_CLICK_EXE')
    write_json(stage/'실행검증.json',checks)
    result=dict(private_only=True,contains_user_saves=False,original_zip_sha256=PIN,original_build=old['build'],build=dict(commit=commit,branch=branch,content_version=old['build']['content_version'],runtime_envelope=2,save_format=2),original_windows_template_sha256=TEMPLATE_PIN,recovered_exported_template_sha256=EXPORTED_TEMPLATE_PIN,windows_native_execution='NOT_RUN',private_equivalence=equivalence,persistent_save=old['persistent_save'])
    result['files']=[dict(path=str(p.relative_to(stage)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(stage.rglob('*')) if p.is_file()]
    write_json(stage/'PACKAGE_MANIFEST.json',result)
    write_json(out/'build-report.json',dict(stage=str(stage),project=str(project),branch=branch,commit=commit,private_equivalence=equivalence,windows_native_execution='NOT_RUN'))
    print(json.dumps(dict(stage=str(stage),build=commit,private_files=equivalence['files']),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--godot',required=True);p.add_argument('--cc',required=True);build(p.parse_args())
