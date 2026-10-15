#!/usr/bin/env python3
"""Build one arm64 APK for phones/tablets without deleting original content.

Private signing config is supplied from the existing private vault. Public
cloud config can contain only a publishable key. No deployment PASS is inferred
from export. Verification APK and player APK are distinct.
"""
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import time
import zipfile
from windows_ci import ROOT, command, validate_runtime, write_json, sha256, copy_game_source, source_inputs, validate_cache, verify_frozen_source, game_checkout_commit, VERIFY_MEMBERS, EXCLUDE


# Independently retained delivered f248 signer certificate (public fingerprint).
DELIVERED_CERTIFICATE_SHA256='f8cf43158c663e80b3e15aaa82681ea328be009ea900c7c5ea68e8a6ddec608a'

def public_config(path):
    if not path or not Path(path).exists():return None
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if set(data)!={'url','public_key'} or not data['url'].startswith('https://'):
        raise ValueError('Only HTTPS URL and public publishable key belong in an app')
    key=data['public_key']
    if key.startswith('sb_publishable_'):return data
    try:
        claim=json.loads(base64.urlsafe_b64decode(key.split('.')[1]+'==='))
    except Exception:raise ValueError('Expected a public publishable/anon key')
    if claim.get('role')!='anon':raise ValueError('Admin/service role keys are forbidden in apps')
    return data

def build(args):
    runtime=Path(args.runtime).resolve();out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    metadata,rows=validate_runtime(runtime)
    commit=game_checkout_commit()
    project=out/'project';inputs=copy_game_source(project)
    if game_checkout_commit()!=commit:raise ValueError('Source commit changed while freezing build inputs')
    active=json.loads((runtime/'private_content/ACTIVE.json').read_text(encoding='utf-8')) if (runtime/'private_content/ACTIVE.json').exists() else {'release_id':'legacy-base'}
    write_json(project/'data/build_info.json',{'commit':commit,'content_version':active['release_id']})
    cloud=public_config(args.cloud)
    if args.require_cloud and not cloud:raise ValueError('Cloud connection missing; production delivery blocked')
    if cloud:write_json(project/'data/cloud_public.json',cloud)
    cache=runtime/'runtime_cache'
    if args.cache:cache=Path(args.cache).resolve()
    if not cache.exists():
        command([args.godot,'--headless','--path',project,'--script','build_world_cache.gd','--',
                 '--assets='+str(runtime/'private_assets'),'--content='+str(runtime/'private_content'),'--out='+str(cache)],out/'cache.log')
    validate_cache(cache,runtime,active,project)
    small_cache=out/'android-cache'
    command([args.godot,'--headless','--path',project,'--script',ROOT/'tools/compress_world_cache.gd','--',
             '--cache='+str(cache),'--out='+str(small_cache)],out/'cache-compression.log')
    members=[r['path'] for r in rows]+[{'path':'runtime_cache/'+name,'source':str(small_cache/name)} for name in ['manifest.json','world.bin']]
    write_json(out/'runtime-members.json',members)
    command([args.godot,'--headless','--path',project,'--script',ROOT/'tools/pack_runtime.gd','--',
             '--root='+str(runtime),'--manifest='+str(out/'runtime-members.json'),'--out='+str(project/'runtime.pck')],out/'pack.log')
    cfg=(project/'project.godot').read_text(encoding='utf-8').replace('run/main_scene="res://main.tscn"','run/main_scene="res://android_bootstrap.tscn"')
    cfg=cfg.replace('[rendering]','window/handheld/orientation=0\n\n[rendering]')
    # Godot's Android project validator requires ETC2 import support even when
    # all original PNGs are read losslessly from our raw runtime pack.
    cfg=cfg.replace('[rendering]','[rendering]\ntextures/vram_compression/import_etc2_astc=true')
    cfg=cfg.replace('[application]','[application]\nconfig/icon="res://android_icon.svg"')
    (project/'project.godot').write_text(cfg,encoding='utf-8')
    signing=json.loads(Path(args.signing).read_text(encoding='utf-8'))
    keystore=out/'private-signing.p12'
    if args.verification:
        probes=VERIFY_MEMBERS+['mobile_smoke_probe.gd']
        write_json(out/'verification-members.json',probes)
        command([args.godot,'--headless','--path',project,'--script',ROOT/'tools/pack_runtime.gd','--',
            '--root='+str(project),'--manifest='+str(out/'verification-members.json'),'--out='+str(project/'verification.pck')],out/'verification-pack.log')
        write_json(project/'data/mobile_probe.json',{'exercise':args.probe_mode,'save':'user://verification/saves/v2/character.json','evidence':'user://verification/evidence'})
        if args.initial_save:shutil.copy2(args.initial_save,project/'data/initial_save.json')
    editor_settings=Path(args.editor_settings) if args.editor_settings else Path.home()/'.config/godot/editor_settings-4.6.tres'
    editor_settings.parent.mkdir(parents=True,exist_ok=True)
    java=Path(os.environ.get('JAVA_HOME','/usr/lib/jvm/java-17-openjdk-amd64'))
    editor_settings.write_text('[gd_resource type="EditorSettings" format=3]\n[resource]\nexport/android/android_sdk_path='+json.dumps(str(Path(args.sdk).resolve()))+'\nexport/android/java_sdk_path='+json.dumps(str(java))+'\n',encoding='utf-8')
    version=max(int(time.time()),1792054708)
    verify_frozen_source(project,inputs)
    export_inputs=source_inputs(project)
    preset=f'''[preset.0]
name="Android"
platform="Android"
runnable=true
export_filter="all_resources"
include_filter="*.json,*.pck"
exclude_filter="{EXCLUDE}"
script_export_mode=1
[preset.0.options]
custom_template/debug={json.dumps(str(Path(args.template).resolve()))}
custom_template/release={json.dumps(str(Path(args.template).resolve()))}
gradle_build/use_gradle_build=false
command_line/extra_args="{'--audio-driver Dummy' if args.verification else ''}"
architectures/armeabi-v7a=false
architectures/arm64-v8a={str(not args.verification).lower()}
architectures/x86=false
architectures/x86_64={str(args.verification or args.universal).lower()}
version/code={version}
version/name="0.3.{commit[:8]}"
package/unique_name="org.irewon.baram.singleplayer{'.verification' if args.verification else ''}"
package/name="바람의나라"
package/signed=true
screen/orientation=0
permissions/internet=true
keystore/debug={json.dumps(str(keystore))}
keystore/debug_user={json.dumps(signing['alias'])}
keystore/debug_password={json.dumps(signing['password'])}
keystore/release={json.dumps(str(keystore))}
keystore/release_user={json.dumps(signing['alias'])}
keystore/release_password={json.dumps(signing['password'])}
'''
    preset_path=project/'export_presets.cfg'
    target=out/('baram-Android-verification.apk' if args.verification else 'baram-Android-arm64.apk')
    try:
        keystore.write_bytes(base64.b64decode(signing['pkcs12_base64']));keystore.chmod(0o600)
        preset_path.write_text(preset,encoding='utf-8');preset_path.chmod(0o600)
        command([args.godot,'--headless','--editor','--path',project,'--import','--quit'],out/'import.log')
        command([args.godot,'--headless','--path',project,'--export-debug' if args.verification else '--export-release','Android',target],out/'export.log')
    finally:
        # Signing secret never enters a package; remove temporary plaintext.
        preset_path.unlink(missing_ok=True);keystore.unlink(missing_ok=True)
    signers=list((Path(args.sdk)/'build-tools').glob('*/'+('apksigner.bat' if os.name=='nt' else 'apksigner')))
    signers.sort(key=lambda p:tuple(int(n) for n in re.findall(r'\d+',p.parent.name)))
    if not signers:raise ValueError('Android SDK apksigner missing')
    apksigner=signers[-1]
    signature=command([apksigner,'verify','--verbose','--print-certs',target],out/'signature.log')
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives import hashes
    _key,certificate,_chain=pkcs12.load_key_and_certificates(base64.b64decode(signing['pkcs12_base64']),signing['password'].encode())
    certificate_sha256=certificate.fingerprint(hashes.SHA256()).hex()
    if certificate_sha256!=DELIVERED_CERTIFICATE_SHA256:raise ValueError('Signing key is incompatible with the delivered APK')
    signers_sha=re.findall(r'certificate SHA-256 digest:\s*([0-9a-fA-F]{64})',signature)
    if signers_sha!=[certificate_sha256]:raise ValueError('APK signer differs from the existing preserved key')
    aapt=apksigner.parent/('aapt2.exe' if os.name=='nt' else 'aapt2')
    badging=command([aapt,'dump','badging',target],out/'apk-badging.log')
    package='org.irewon.baram.singleplayer'+('.verification' if args.verification else '')
    if not re.search(r"^package: name='"+re.escape(package)+r"'",badging,re.M):raise ValueError('APK package identity mismatch')
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise ValueError('APK CRC failure')
        if not args.verification and any(re.search(r'(?:probe|runner|render_canvas)\.gd(?:c|\.remap)?$|/native_regression\.gd|/exercise\.gd|initial_save\.json|mobile_probe\.json|verification\.pck',n) for n in z.namelist()):
            raise ValueError('Development files leaked into player APK')
        if not any('arm64-v8a/' in n for n in z.namelist()) and not args.verification:raise ValueError('ARM64 missing')
        if any('x86_64/' in n for n in z.namelist()) and not args.verification and not args.universal:raise ValueError('Unexpected emulator ABI in ARM-only APK')
        runtime_members=[n for n in z.namelist() if n.endswith('/runtime.pck')]
        if len(runtime_members)!=1 or hashlib.sha256(z.read(runtime_members[0])).hexdigest()!=sha256(project/'runtime.pck'):
            raise ValueError('APK embedded runtime pack differs from the verified build input')
        unpacked=sum(i.file_size for i in z.infolist())
    # Exact original source/pack membership is checked before packing, never
    # claim byte equivalence merely because the app contains some textures.
    for row in rows:
        if sha256(runtime/row['path'])!=row['sha256']:raise ValueError('Original runtime changed')
    result={'status':'BUILT_NOT_EXECUTION_PASS','commit':commit,'content_version':active['release_id'],'source_inputs':inputs,'exported_project_source_inputs':export_inputs,
        'package':package,'version_code':version,'certificate_sha256':certificate_sha256,'runtime_pck_sha256':sha256(project/'runtime.pck'),
        'apk':str(target),'sha256':sha256(target),'apk_bytes':target.stat().st_size,
        'apk_uncompressed_member_bytes':unpacked,'original_private_files':len([r for r in rows if r['path'].startswith('private_')]),
        'original_private_bytes_preserved':True,'android_emulator':'NOT_RUN','galaxy_phone_and_tab_s10_fe':'NOT_RUN',
        'cloud_configured':bool(cloud),'production_delivery':'BLOCKED_UNTIL_END_TO_END_PASS',
        'installed_size_bytes':None,'cold_start_ms':None,'memory_pss_bytes':None}
    write_json(out/'android-build.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['runtime','godot','template','sdk','signing','out']:p.add_argument('--'+key,required=True)
    p.add_argument('--cache');p.add_argument('--cloud');p.add_argument('--require-cloud',action='store_true');p.add_argument('--verification',action='store_true');p.add_argument('--editor-settings')
    p.add_argument('--universal',action='store_true',help='One signed ARM64+x86_64 player APK for exact-artifact emulator testing')
    p.add_argument('--probe-mode',default='recovery-core');p.add_argument('--initial-save')
    build(p.parse_args())
