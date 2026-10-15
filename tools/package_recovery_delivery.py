#!/usr/bin/env python3
"""Reconstructed strict delivery gate. Missing native evidence blocks promotion.

Inputs are read-only CI artifacts. A PASS here combines existing attestations;
it does not execute a game or certify physical Galaxy hardware.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import zipfile
from fetch_recovery_artifact import ArtifactError,checked_members,digest,safe_extract_zip,safe_relative,write_json

PLAYER_PACKAGE='org.irewon.baram.singleplayer'
CERTIFICATE='f8cf43158c663e80b3e15aaa82681ea328be009ea900c7c5ea68e8a6ddec608a'
MIN_VERSION=1792054707
CORE_CHECKS={'new_character_is_level1_commoner','level1_has_no_unlearned_attack_or_teleport_skills',
 'actual_village_guide_reaches_hunting_field','normal_animated_attack_kills_actual_monster','normal_kill_awards_experience',
 'actual_random_drop_picked_up_via_key','hunt_quests_reach_commoner5_without_auto_job','explicit_normal_NPC_choice_changes_job_at5',
 'compass_learned_with_exact_source_item_cost','normally_learned_skill_casts_and_spends_source_MP',
 'compass_gate_selection_changes_actual_map','normal_rat_rewards_reach_mage6','attack_spell_learned_at6_with_real_acorn_cost',
 'natural_level6_attack_spell_use','complete_playthrough_saved_to_normal_save_format','restart_expected_state_written_and_reread'}
RESTART_CHECKS={'fresh_process_read_saved_character','fresh_process_preserves_entire_character',
 'fresh_process_preserves_monsters_and_drops','fresh_process_preserves_rng'}
OS_CHECKS={'OS_new_character_level1_commoner_no_unearned_skills','OS_selected_monster_attack_awards_real_experience',
 'OS_real_drop_tap_approaches_and_increases_inventory','OS_touch_menu_opens_spatial_world_map',
 'replace_install_preserves_save_bytes','600_seconds_OS_input_session','no_runtime_engine_errors'}

class GateError(Exception):
 def __init__(self,status,code):super().__init__(code);self.status=status;self.code=code

class Gate:
 def __init__(self):self.checks=[]
 def require(self,ok,code,details=None):
  self.checks.append({'name':code,'status':'PASS' if ok else 'FAIL','details':details or {}})
  if not ok:raise GateError('FAIL',code)
 def read(self,path):
  path=Path(path)
  if not path.is_file():raise GateError('BLOCKED','MISSING_EVIDENCE:'+path.name)
  if path.stat().st_size>32*1024**2:raise GateError('FAIL','OVERSIZED_EVIDENCE:'+path.name)
  try:return json.loads(path.read_text(encoding='utf-8'))
  except (ValueError,UnicodeError):raise GateError('FAIL','INVALID_JSON:'+path.name) from None
 def all_pass(self,report,required=(),label='report'):
  rows=report.get('checks',[])
  self.require(report.get('status')=='PASS' and bool(rows) and all(isinstance(c,dict) and c.get('status')=='PASS' for c in rows),label+'_all_checks_pass')
  self.require(set(required)<={c.get('name',c.get('id')) for c in rows},label+'_required_checks_present')

def frozen_inputs(value):
 rows=value.get('files',[])
 if not rows or not isinstance(rows,list):raise GateError('BLOCKED','FROZEN_SOURCE_INPUTS_MISSING')
 names=[]
 for row in rows:
  safe_relative(row['path']);names.append(row['path'])
  if not row['path'].startswith('game/') or not re.fullmatch('[0-9a-f]{64}',row.get('sha256','')):raise GateError('FAIL','FROZEN_SOURCE_ROW_INVALID')
 if len(names)!=len(set(names)):raise GateError('FAIL','FROZEN_SOURCE_DUPLICATE')
 encoded=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 if hashlib.sha256(encoded).hexdigest()!=value.get('sha256'):raise GateError('FAIL','FROZEN_SOURCE_FINGERPRINT_INVALID')
 return value['sha256']

def cert_from_private_path(path):
 from cryptography.hazmat.primitives.serialization import pkcs12
 from cryptography.hazmat.primitives import hashes
 config=json.loads(Path(path).read_text(encoding='utf-8'))
 _key,cert,_chain=pkcs12.load_key_and_certificates(base64.b64decode(config['pkcs12_base64'],validate=True),config['password'].encode())
 if cert is None:raise GateError('BLOCKED','LOCAL_SIGNING_CERTIFICATE_MISSING')
 return cert.fingerprint(hashes.SHA256()).hex()

def check_signature_log(path,expected):
 if not Path(path).is_file():raise GateError('BLOCKED','SIGNATURE_ATTESTATION_MISSING:'+Path(path).name)
 raw=Path(path).read_text(encoding='utf-8')
 values=re.findall(r'certificate SHA-256 digest:\s*([0-9a-fA-F]{64})',raw)
 return [v.lower() for v in values]==[expected]

def game_report(gate,path,platform,source,content,required,label):
 r=gate.read(path);gate.all_pass(r,required,label)
 gate.require(r.get('platform')==platform,label+'_actual_platform')
 gate.require(r.get('game_build')==source and r.get('content_version')==content,label+'_same_frozen_source_and_content')
 gate.require(r.get('time_scale')==1,label+'_normal_timers')
 if 'natural_level6_attack_spell_use' in required:
  p=r.get('player',{})
  gate.require(p.get('job')=='주술사' and isinstance(p.get('level'),(int,float)) and p['level']>=6 and 'validation_fixture' not in p,label+'_naturally_earned_mage6')
 return r

def validate_windows(gate,directory,temporary,source):
 candidates=list(directory.glob('*.zip'))
 if len(candidates)!=1:raise GateError('BLOCKED','ONE_WINDOWS_PLAYER_ZIP_REQUIRED')
 archive=candidates[0];safe_extract_zip(archive,temporary/'windows')
 manifests=list((temporary/'windows').rglob('PACKAGE_MANIFEST.json'))
 if len(manifests)!=1:raise GateError('FAIL','WINDOWS_MANIFEST_AMBIGUOUS')
 root=manifests[0].parent
 gate.require(all(root in p.parents for p in (temporary/'windows').rglob('*') if p.is_file()),'windows_all_members_inside_manifest_root')
 m=gate.read(manifests[0]);build=m.get('build',{})
 gate.require(build.get('commit')==source,'windows_expected_source')
 content=build.get('content_version','');gate.require(bool(re.fullmatch('[0-9a-f]{64}',content)),'windows_content_identity')
 expected={}
 for row in m.get('files',[]):
  relative=safe_relative(row['path']).as_posix()
  gate.require(relative not in expected,'windows_manifest_unique_'+str(len(expected)))
  expected[relative]=row
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='PACKAGE_MANIFEST.json'}
 gate.require(set(expected)==actual,'windows_manifest_exact_membership')
 for name,row in expected.items():
  p=root/name
  gate.require(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'windows_member_hash_'+str(len(gate.checks)))
 exe=root/'바람의나라.exe'
 if not exe.is_file():raise GateError('BLOCKED','WINDOWS_EXE_MISSING')
 with exe.open('rb') as stream:
  header=stream.read(64)
  gate.require(len(header)==64 and header[:2]==b'MZ','windows_PE_header')
  offset=struct.unpack_from('<I',header,60)[0];gate.require(64<=offset<=4*1024**2,'windows_PE_offset')
  stream.seek(offset);coff=stream.read(26)
  gate.require(len(coff)==26 and coff[:4]==b'PE\0\0' and struct.unpack_from('<H',coff,4)[0]==0x8664 and struct.unpack_from('<H',coff,24)[0]==0x20b,'windows_actual_x64_PE')
 verification=gate.read(root/'실행검증.json')
 gate.require(m.get('verification')==verification,'windows_manifest_attestation_matches_file')
 for key in ('status','windows_native_execution','windows_windowed_startup','windows_message_pump','game_function_automation'):
  gate.require(verification.get(key)=='PASS','windows_'+key)
 gate.require(verification.get('source_sha')==source,'windows_verification_source')
 runs=verification.get('runs',[])
 gate.require(bool(runs) and all(r.get('status')=='PASS' and r.get('platform')=='Windows' and r.get('game_build')==source for r in runs),'windows_all_runs_native_and_same_source')
 gate.require(any(r.get('execution_mode')=='WINDOWED_EXE' and r.get('windows_message_pump')=='PASS' and r.get('visible_window_samples',0)>0 and 'windowed_game_frame_rendered' in r.get('checks',[]) for r in runs),'windows_visible_rendered_message_pump')
 gate.require({'native-smoke','recovery-core','recovery-restart'}<={r.get('mode') for r in runs},'windows_required_processes')
 game_report(gate,directory/'evidence/core/recovery-core-report.json','Windows',source,content,CORE_CHECKS,'windows_core')
 game_report(gate,directory/'evidence/core/recovery-restart-report.json','Windows',source,content,RESTART_CHECKS,'windows_restart')
 recovery=gate.read(directory/'recovery-content.json')
 gate.require(recovery.get('status')=='PASS' and recovery.get('active',{}).get('release_id')==content,'windows_content_preparation')
 return archive,m,content

def validate_android(gate,directory,source,content,source_hash,certificate):
 apk=directory/'baram-Android-update.apk'
 if not apk.is_file():raise GateError('BLOCKED','PLAYER_APK_MISSING')
 build=gate.read(directory/'android-build.json');verify_build=gate.read(directory/'android-verification-build.json')
 for label,value,package in [('player',build,PLAYER_PACKAGE),('verification',verify_build,PLAYER_PACKAGE+'.verification')]:
  gate.require(value.get('commit')==source and value.get('content_version')==content,label+'_same_source_and_content')
  gate.require(value.get('package')==package,label+'_exact_package_identity')
  gate.require(isinstance(value.get('version_code'),int) and value['version_code']>MIN_VERSION,label+'_update_version_newer_than_delivered')
  gate.require(value.get('certificate_sha256')==certificate,label+'_preserved_signing_certificate')
  gate.require(frozen_inputs(value.get('source_inputs',{}))==source_hash,label+'_same_frozen_game_inputs')
 gate.require(check_signature_log(directory/'signature.log',certificate),'player_apksigner_attestation')
 gate.require(check_signature_log(directory/'android-verification-signature.log',certificate),'verification_apksigner_attestation')
 gate.require(build.get('runtime_pck_sha256')==verify_build.get('runtime_pck_sha256') and bool(re.fullmatch('[0-9a-f]{64}',build.get('runtime_pck_sha256',''))),'player_and_verification_identical_runtime_pack')
 gate.require(frozen_inputs(build.get('exported_project_source_inputs',{}))==frozen_inputs(verify_build.get('exported_project_source_inputs',{})),'android_same_exported_game_sources')
 gate.require(digest(apk)==build.get('sha256') and apk.stat().st_size==build.get('apk_bytes'),'actual_player_apk_matches_builder_hash')
 with zipfile.ZipFile(apk) as z:
  checked_members(z);names=z.namelist()
  gate.require(any('/arm64-v8a/' in n for n in names) and any('/x86_64/' in n for n in names),'same_player_apk_phone_and_emulator_ABIs')
  runtime=[n for n in names if n.endswith('/runtime.pck')]
  gate.require(len(runtime)==1,'one_embedded_runtime_pack')
  h=hashlib.sha256()
  with z.open(runtime[0]) as stream:
   for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
  gate.require(h.hexdigest()==build['runtime_pck_sha256'],'actual_player_runtime_pack_hash')
  gate.require(not any(re.search(r'(?:probe|runner|render_canvas)\.gd(?:c|\.remap)?$|/native_regression\.gd|/exercise\.gd|initial_save\.json|mobile_probe\.json|verification\.pck',n) for n in names),'player_contains_no_verification_runner')
  if z.testzip() is not None:raise GateError('FAIL','PLAYER_APK_CRC')
 os_report=gate.read(directory/'android-evidence/android-quality-report.json');gate.all_pass(os_report,OS_CHECKS,'android_player_OS_input')
 gate.require(os_report.get('scope')=='EXACT_RELEASE_APK_ANDROID_35_X86_64_OS_INPUT_NOT_GALAXY' and os_report.get('package')==PLAYER_PACKAGE and os_report.get('apk_sha256')==build['sha256'],'actual_Android35_exact_player_artifact')
 recovery=gate.read(directory/'android-recovery-evidence/android-recovery-report.json');gate.all_pass(recovery,(), 'android_separate_recovery_runner')
 gate.require(recovery.get('scope')=='ACTUAL_ANDROID35_VERIFICATION_APK_INPUT_RUNNER_NOT_PLAYER_APK_NOT_PHYSICAL_GALAXY' and recovery.get('package')==PLAYER_PACKAGE+'.verification' and recovery.get('apk_sha256')==verify_build.get('sha256'),'android_verification_apk_attested_identity')
 runs=recovery.get('runs',[])
 gate.require({r.get('mode') for r in runs}=={'recovery-core','recovery-restart'} and all(r.get('status')=='PASS' and r.get('game_build')==source and r.get('content_version')==content for r in runs),'android_core_and_restart_same_source_and_content')
 game_report(gate,directory/'android-recovery-evidence/recovery-core-report.json','Android',source,content,CORE_CHECKS,'android_core')
 game_report(gate,directory/'android-recovery-evidence/recovery-restart-report.json','Android',source,content,RESTART_CHECKS,'android_restart')
 preparation=gate.read(directory/'recovery-content.json')
 gate.require(preparation.get('status')=='PASS' and preparation.get('active',{}).get('release_id')==content,'android_content_preparation')
 return apk,build

def package(args):
 gate=Gate();report={'status':'BLOCKED','scope':'STRICT_NATIVE_EVIDENCE_DELIVERY_GATE','overall_game_complete':False,
 'implementation_origin':'RECONSTRUCTED_PYTHON_ORIGINAL_SOURCE_NOT_RECOVERED','checks':gate.checks,
 'physical_Galaxy':'NOT_RUN','human_Windows_GUI_observation':'NOT_RUN','account_sync':'NOT_RUN'}
 output=Path(args.output).resolve()
 input_roots=(Path(args.android_dir).resolve(),Path(args.windows_dir).resolve())
 report_path=Path(args.report).resolve()
 report_is_safe=report_path not in {Path(args.signing).resolve(),Path(args.ci_run).resolve()} and not any(report_path==root or root in report_path.parents for root in input_roots)
 try:
  if not report_is_safe:raise GateError('BLOCKED','REPORT_MUST_NOT_MODIFY_READ_ONLY_INPUTS')
  if output.exists():raise GateError('BLOCKED','EXISTING_DELIVERY_IS_PRESERVED')
  for input_root in (Path(args.android_dir).resolve(),Path(args.windows_dir).resolve()):
   if output==input_root or input_root in output.parents:raise GateError('BLOCKED','OUTPUT_MUST_NOT_MODIFY_INPUT_ARTIFACTS')
   report_path=Path(args.report).resolve()
   if report_path==input_root or input_root in report_path.parents:raise GateError('BLOCKED','REPORT_MUST_NOT_MODIFY_INPUT_ARTIFACTS')
  gate.require(bool(re.fullmatch('[0-9a-f]{40}',args.source_sha)),'full_frozen_source_commit_required')
  ci=gate.read(args.ci_run)
  if ci.get('conclusion')!='success':raise GateError('BLOCKED','NATIVE_CI_NOT_SUCCESSFUL')
  gate.require(ci.get('head_sha')==args.source_sha,'CI_same_frozen_source')
  jobs={j.get('name'):j for j in ci.get('jobs',[])}
  if not all(jobs.get(n,{}).get('conclusion')=='success' for n in ('android','windows')):raise GateError('BLOCKED','BOTH_NATIVE_PLATFORM_JOBS_REQUIRED')
  gate.require(any('windows' in str(x).lower() for x in jobs['windows'].get('labels',[])),'Windows_job_actual_runner_labels')
  certificate=cert_from_private_path(args.signing)
  gate.require(certificate==CERTIFICATE,'local_signer_matches_delivered_f248')
  output.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='delivery-gate-',dir=output.parent) as temporary:
   temporary=Path(temporary)
   windows,manifest,content=validate_windows(gate,Path(args.windows_dir),temporary,args.source_sha)
   source_hash=frozen_inputs(manifest.get('source_inputs',{}))
   if args.expected_content:gate.require(content==args.expected_content,'explicit_expected_content')
   android,build=validate_android(gate,Path(args.android_dir),args.source_sha,content,source_hash,certificate)
   ready=temporary/'ready';ready.mkdir()
   names=[('Android',android,f'baram-Android-{args.source_sha[:8]}.apk'),('Windows',windows,f'baram-Windows64-{args.source_sha[:8]}.zip')]
   files=[]
   for platform,src,name in names:
    target=ready/name;shutil.copyfile(src,target)
    gate.require(digest(target)==digest(src),platform+'_copied_binary_unchanged')
    files.append({'platform':platform,'file':name,'bytes':target.stat().st_size,'sha256':digest(target)})
   report.update(status='PASS',source_sha=args.source_sha,content_version=content,source_inputs_sha256=source_hash,
                 certificate_sha256=certificate,android_version_code=build['version_code'],files=files,
                 signature_scope='CI_APKSIGNER_ATTESTATION_BOUND_TO_AES_AUTHENTICATED_ARTIFACT_AND_ACTUAL_APK_HASH')
   write_json(ready/'delivery-verification.json',report)
   (ready/'처음읽기.txt').write_text('Android는 기존 앱을 삭제하지 말고 업데이트 설치하세요. Windows ZIP은 모두 압축을 푼 뒤 바람의나라.exe를 실행하세요.\n실제 Galaxy 하드웨어와 계정 동기화는 이번 검증에 포함되지 않았습니다.\n',encoding='utf-8')
   os.replace(ready,output)
 except GateError as error:report.update(status=error.status,reason=error.code)
 except Exception as error:report.update(status='FAIL',reason=error.code if isinstance(error,ArtifactError) else type(error).__name__)
 if report_is_safe:write_json(args.report,report)
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('android-dir','windows-dir','ci-run','source-sha','signing','output','report'):p.add_argument('--'+name,required=True)
 p.add_argument('--expected-content');args=p.parse_args();r=package(args)
 print(json.dumps({'status':r['status'],'reason':r.get('reason'),'scope':r['scope']}));return 0 if r['status']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
