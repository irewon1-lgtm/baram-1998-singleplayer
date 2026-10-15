#!/usr/bin/env python3
"""Supplement static ZIP/7z inventory with hash-pinned existing DAT/CAB readers.

No graphics frame decoding, installer execution, or game launch. Private bytes
are written only to --private-work; public outputs contain identities and facts.
Run inventory_archives.py first, then this file with the existing tool directory.
"""
import argparse, collections, hashlib, importlib, io, json, sys, wave, zipfile
from pathlib import Path

VERSION='baram-static-links/1.0'
EXPECTED_TOOLS={'legacy_installers.py':'5dd1d31cd287a01a8da494c315df5479a032a0a18979a30901bee49b558fd382','legacy_assets.py':'f5152ae3473b3e2f2d120b8c1b8679529428d2bd09f9024528d71aa9a9be86e2'}
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return [json.loads(l) for l in p.read_text().splitlines()]
def dump(p,rows):p.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
def kind(n):
    return {'.map':'map','.epf':'sprite','.spr':'sprite','.pal':'palette','.tbl':'table','.tab':'table','.frm':'animation','.elt':'effect_layer','.wav':'audio','.exe':'executable','.dat':'data_container','.snd':'data_container'}.get(Path(n).suffix.lower(),'other')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--private-work',type=Path,required=True);ap.add_argument('--tools',type=Path,required=True);a=ap.parse_args()
    for n,h in EXPECTED_TOOLS.items():
        assert sha((a.tools/n).read_bytes())==h, 'Existing reader fingerprint mismatch: '+n
    sys.path.insert(0,str(a.tools));assets=importlib.import_module('legacy_assets');installers=importlib.import_module('legacy_installers')
    sources=load(a.output/'archive_sources.jsonl');members=[r for r in load(a.output/'archive_members.jsonl') if r.get('parser_version')!=VERSION]
    source_by={r['source_id']:r for r in sources};seen={r['sha256']:r['member_id'] for r in members};private=a.private_work;private.mkdir(parents=True,exist_ok=True)
    checks=[]
    def add(sid,path,b,depth,offset=None):
        h=sha(b);mid=sid+'-M-'+sha(path.encode())[:12]
        r={'source_id':sid,'member_id':mid,'archive_member':path,'size_bytes':len(b),'sha256':h,'kind':kind(path),'depth':depth,'inspection':'BYTES_READ_HASHED_EXISTING_STATIC_READER','parser_version':VERSION,'original_id_candidate':Path(path).stem if Path(path).stem.isdigit() else None,'mapping_candidates':[]}
        if h in seen:r['same_bytes_as_member_id']=seen[h]
        else:seen[h]=mid
        if offset is not None:r['parent_byte_offset']=offset
        if r['kind']=='audio':
            with wave.open(io.BytesIO(b),'rb') as w:r['wave']={'channels':w.getnchannels(),'rate_hz':w.getframerate(),'sample_width':w.getsampwidth(),'frames':w.getnframes(),'duration_seconds':round(w.getnframes()/w.getframerate(),6)}
        if r['kind']=='executable':r['execution']='NOT_RUN_STATIC_ONLY'
        members.append(r);return r
    # CAB decompression uses existing measured v4 reader. Do not launch installers.
    z=zipfile.ZipFile(source_by['LIB-010']['local_materialization_path']);cab=z.read('Install/DATA1.CAB');base='KR_4.91_491v.zip!Install/DATA1.CAB'
    for meta,b in installers.installshield4(cab):
        if b is None:continue
        p=base+'!'+meta['path'];r=add('LIB-010',p,b,2,meta['offset']);r['compressed_size_bytes']=meta['compressed_bytes']
        (private/meta['name']).write_bytes(b)
        if meta['name'].lower().endswith(('.dat','.snd')):
            es=assets.dat_entries(b);r['container_status']='LISTED_HASHED_EXISTING_READER';r['entry_count']=len(es)
            for _,(n,off,raw) in es.items():add('LIB-010',p+'!'+n,raw,3,off)
    cabrow=next(r for r in members if r['source_id']=='LIB-010' and r['archive_member']==base)
    cabrow['container_status']='LISTED_HASHED_EXISTING_READER'
    if cabrow.get('container_error'):cabrow['resolved_initial_reader_error']=cabrow.pop('container_error')
    # Reuse v125 extraction manifest: verify each declared slice of identical DAT.
    rawdat=zipfile.ZipFile(source_by['LIB-009']['local_materialization_path']).read('winbaram.dat')
    mf=json.loads(zipfile.ZipFile(source_by['LIB-032']['local_materialization_path']).read('v125/MANIFEST.json'))
    v125_ok=0
    for e in mf['files']:
        b=rawdat[e['offset']:e['end']];assert len(b)==e['bytes'] and sha(b)==e['sha256'],e['name']
        r=add('LIB-009','KR_1.25_winbaram.zip!winbaram.dat!'+e['name'],b,2,e['offset']);r['reuse_basis']='LIB-032 v125/MANIFEST.json offsets and hashes verified against LIB-009 winbaram.dat';v125_ok+=1
    checks.append({'check':'v125_original_manifest_slices','checked':v125_ok,'failures':0,'scope':'BYTES_ONLY_NO_ANIMATION_SEMANTICS'})
    # Manifest bytes and all declared members must agree. No runtime binding implied.
    for sid in ['LIB-036','LIB-037','LIB-038','LIB-040']:
        zz=zipfile.ZipFile(source_by[sid]['local_materialization_path'])
        manifests=[n for n in zz.namelist() if n.endswith('PRIVATE_MANIFEST.json')]
        for mn in manifests:
            mf=json.loads(zz.read(mn));good=0
            for f in mf.get('files',[]):
                raw=zz.read(f['path']);assert sha(raw)==f['sha256'] and len(raw)==f['size_bytes'],sid+f['path'];good+=1
            checks.append({'check':'private_manifest_files','source_id':sid,'manifest_member':mn,'checked':good,'failures':0})
    # Actual source EPF/PAL hashes in existing atlas metadata now close back to CAB.
    original={Path(r['archive_member'].split('!')[-1]).name.lower():r for r in members if r['source_id']=='LIB-010' and r['depth']==3}
    epf_links=[]
    for sid,prefix in [('LIB-036','kr491/'),('LIB-040','kr491-ui/')]:
        zz=zipfile.ZipFile(source_by[sid]['local_materialization_path'])
        for n in zz.namelist():
            if not (n.startswith(prefix) and n.endswith('.json')):continue
            o=json.loads(zz.read(n))
            if 'source_file' not in o:continue
            src=original[o['source_file'].lower()];pal=original[o['palette_file'].lower()]
            assert src['sha256']==o['source_epf_sha256'],n+' source EPF mismatch'
            assert pal['sha256']==o['palette_sha256'],n+' source PAL mismatch'
            epf_links.append({'source_id':sid,'atlas_member':n,'source_member_id':src['member_id'],'palette_member_id':pal['member_id'],'frames':len(o['frames']),'generator_claim':o.get('generator'),'direction_claim':o.get('directions'),'frame_timing':'NOT_IN_ATLAS_METADATA','clipped_pixels_claim':o.get('clipped_pixels'),'native_raster_comparison_claim':o.get('native_raster_comparison')})
    sound_original={r['sha256'] for r in members if r['source_id']=='LIB-010' and r['archive_member'].startswith(base+'!NWind.snd!')}
    sounds=[r for r in members if r['source_id']=='LIB-036' and r['kind']=='audio']
    assert all(r['sha256'] in sound_original for r in sounds)
    checks.append({'check':'kr491_shared_epf_pal_source_links','checked':len(epf_links),'failures':0})
    checks.append({'check':'kr491_shared_sound_original_hashes','checked':len(sounds),'failures':0,'meaning':'file IDs and PCM metadata only; skill/event mapping and playback timing unknown'})
    # Save source counts updated for supplemental nested members. Historical accuracy stays UNKNOWN.
    for s in sources:
        s['inventory_member_count']=sum(r['source_id']==s['source_id'] and r['depth']>0 for r in members)
        if s['source_id']=='LIB-010':
            note='InstallShield DATA1.CAB static extraction resolved with hash-pinned existing reader; NWind.dat203/NWind.snd163 entries; target-era map geometry not present in installer'
            s['notes']=list(dict.fromkeys(s['notes']+[note]))
    dump(a.output/'archive_sources.jsonl',sources);dump(a.output/'archive_members.jsonl',members)
    (private/'STATIC_LINK_CHECKS.json').write_text(json.dumps({'checks':checks,'epf_links':epf_links},ensure_ascii=False,indent=2))
    # Public evidence consists of summaries and immutable member references only.
    bypath={(r['source_id'],r['archive_member']):r for r in members}
    facts=[
      ('DOC-KR491-001','VERSION.TXT','21','4.91 풀버전과 12월14일 표기는 확인되나 연도는 기재되지 않았다. 동봉 문서 전체를 같은 연도 자료로 취급하지 않는다.'),
      ('DOC-KR491-002','지도매뉴얼/초보자용메뉴얼-1.txt','69–72','신규 평민·Lv5 직업 선택을 설명한다. 같은 문단의 도사 추가 예정 문구 때문에 4.91 동봉 문서 안에 과거 시점 자료가 섞였음이 드러난다.'),
      ('DOC-KR491-003','지도매뉴얼/주술사 가이드.txt','23–34;160–167','Lv1 주막 시작, 서문 부근 토끼·다람쥐, 주술사 Lv6 파이어볼·Lv10 무장이라는 후보 근거다. 좌표·밀도·현행 정확한 수치를 확정하지 않는다.'),
      ('DOC-KR491-004','지도매뉴얼/도사레벨별마법안내서.txt','25–33;45–53','도사 Lv5 초기 기술과 Lv6 회복·Lv12 파이어볼을 구분한다. 주술사 문서와 같은 공격기술의 학습레벨이 달라 공통 기술표를 강제할 수 없다.'),
      ('DOC-KR491-005','지도매뉴얼/국내성위치가이드.txt','56–74;90–97','전사·주술사·도적·도사 길드 위치와 국내성 사대문 위치가 각각 적혀 있다. 비영사천문은 직업 취득 후 배워 사대문으로 이동한다고 설명한다. 서문 좌표 원문의 구두점은 불명확하다.'),
      ('DOC-KR491-006','지도매뉴얼/초보자용메뉴얼-1.txt','214–230','길드별 위치와 레벨에 맞는 기술 목록·재료 확인·학습 절차를 설명한다. 여기의 길드 좌표는 국내성위치가이드와 달라 별도 시대/맵 후보로 보존해야 한다.'),
      ('DOC-KR491-007','지도매뉴얼/주술사 가이드.txt','128–131;153–158','비영사천문에서 서 방향을 고르면 서문에 도착한다는 동작과, 사망 후 성황령·성황당 부활 절차를 설명한다. village 하나로 이동시키는 규칙의 근거가 아니다.'),
      ('DOC-KR491-008','지도매뉴얼/도사레벨별마법안내서.txt','133–139','도사 Lv35 귀환의 주막 이동·마력 소모가 적혀 있다. 비영사천문과 귀환을 별도 기술 규칙으로 관리할 근거이며 연도 채택은 잠정이다.'),
      ('DOC-KR491-009','지도매뉴얼/국내성위치가이드.txt','2–8','주막은 물품/돈 보관과 특정 재고, 푸줏간은 고기/가죽 거래로 설명한다. 모든 NPC에 같은 재고와 서비스를 붙일 근거가 없다.'),
      ('DOC-KR491-010','README.TXT','148–159','아이템 I·마법 + 목록의 오른쪽 표시와 소지량 초과 시 줍기 거절을 설명한다. 사용자 사진의 네 탭 모양/촬영연도는 별도 근거다.'),
    ]
    lines=['# 개인 원본 정적 조사 근거 — P0/P1','',
      '기준: AGENTS.md, MASTER_PLAN v1.0, STATE.json, STEP01_WORK_INSTRUCTIONS.md를 읽었다. 새 게임/기준 클라이언트/서버/원본 EXE는 실행하지 않았다. 목록·바이트·메타데이터 검사만 수행했다. 원본·추출 자산 바이트와 매뉴얼 전문은 공개 결과에 포함하지 않는다.','',
      '## 범위와 실제 식별','',
      f'- 개인 파일 {len(sources)}개, 원본 최상위 파일을 포함한 내부 바이트 레코드 {len(members):,}개, 고유 SHA-256 {len({r["sha256"] for r in members}):,}개. 동일 해시는 같은 계보로 취급하며 발견 경로를 유지한다.',
      '- LIB-001~038 최초 ID를 유지했고 추가 인계 4개는 LIB-039~042로 부여했다. 업무와 무관한 CSO_ONE_통합.html 및 전송 중간 파일은 읽거나 목록화하지 않았다.',
      '- 기존 PRIVATE_ASSET_INVENTORY의 원본 13개는 최종 정본의 크기·SHA가 모두 일치했다. NA_ALL 최초 materialization은 26,476,544바이트/916bbf6e5976b5288ac6390ff338be8af82f3da4caa456ab117006aa39baa5a4로 불완전했으나, 원본을 덮어쓰지 않고 별도 재확보한 218,174,017바이트/d41b644303581f7dfc05ef627d99820f8ccce3152637c9be533f0465dbbcb885 정본을 사용했다. 양쪽 경로·지문은 LIB-015에 기록했다.',
      '- NA_ALL 명칭은 5.0 이전이라고 되어 있으나 내부에는 5.32/5.33도 존재한다. 파일명만으로 목표 시대 채택 금지.',
      '- KR1.25: ZIP에서 실제 MAP 218개, winbaram.dat, 실행파일을 확인했다. 한국어 도움말은 이 묶음에서 발견되지 않았다. KR4.91: 외부 ZIP의 한글 매뉴얼 TXT 11개, 지도 이미지·중첩 ZIP과 CAB를 읽었다. ZIP의 구형 이름 바이트를 CP949로 복원했으며 TXT도 CP949로 해독했다.','',
      '## 해독·재사용 결과','',
      '- LIB-010 DATA1.CAB는 InstallShield v4 ISc( 형식이다. host libarchive는 이 포맷을 해독하지 못했다. MIT unshield 소스(tree 0d1e7cbac7986fbd5aa050da8249a27428fee057)를 정적 도구로 빌드해 목록 4개는 확인했으나 추출 0개였다. 기존 저장소의 hash-pinned legacy_installers.py(c919cf1bdffe0e318d4058dc3fc17be4a2844203)를 재사용해 CAB 4파일을 정적 추출함으로써 필요한 데이터는 해결했다. 게임·설치 EXE 실행은 없었다.',
      '- NWind.dat 70,116,637바이트 / f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7: 203개 내부 항목(EPF133/PAL36/TBL20/FRM1 등). NWind.snd 4,558,322바이트 / 003534e57b426971900f7ec39f5e65d3662fa5f32672cd0564d04680e31e300c: WAV163개. CAB와 DAT에는 KR4.91 MAP가 없다. 이것은 이 설치 묶음 내부의 관측이며 전체 한국 지도 부재의 증명이 아니다.',
      '- KR491 캐릭터·이펙트·아이템·UI 아틀라스의 원본 EPF/PAL 연결 131세트(공유84+회수UI47)는 원본 DAT의 실제 각 SHA와 일치했다. PNG를 재해독하지 않고 기존 변환 결과를 재사용할 입력 동일성을 확인했다. 원작 렌더링 정확성/방향/시간 검증은 NOT_RUN이다.',
      '- 공유 WAV163개는 NWind.snd 원본 파일과 각각 바이트 SHA가 일치했다. 레코드에 원본 숫자 ID·채널·샘플레이트·길이를 기록했다. 기술/사건의 소리 선택·재생 시점·음량·반복 조건은 아직 미확인이다.',
      '- KR1.25 기존 추출 manifest의 45개 파일은 winbaram.dat의 원본 offset/end 슬라이스와 SHA가 모두 일치했다. 프레임을 다시 전수 해독하지 않았다. 동작 의미와 목표 시대 대응은 별도 검증 대상이다.',
      '- 공유·지역·회수UI private manifest 986개 선언 파일의 SHA/크기를 전수 대조했다. 정상 바이트 보존 검사이며 게임 동작이나 역사적 정확성 PASS가 아니다.',
      '- 지역 묶음 LIB-038 manifest는 source를 Pinned NA495 layouts라고 명시한다. LIB-037 확장도 같은 성격의 레이아웃을 포함한다. 한국 이름 부착만으로 한국 지형으로 채택하지 않는다.',
      '- 회수UI dlglogin/dlgnew01 등은 원본 EPF/PAL SHA와 일치하지만 metadata에 clipped_pixels/clipped_runs와 native_raster_comparison NOT_RUN이 있다. 이미지 회수와 실제 원본 렌더러 일치 판정은 구분한다.','',
      '## 실제로 읽은 한국어 문서의 기능 근거','',
      '모두 LIB-010 동봉 문서다. 문서 바이트/내용 관측과 1998~2001 게임 규칙의 채택은 구분한다. 문서 자체 작성연도는 UNKNOWN이며 서로 다른 시대 설명이 섞여 있다. 아래는 전문 인용이 아닌 요약이다.','',
      '|근거 ID|원본 member ID|라인|해결하는 칸과 제한|SHA-256|','|---|---|---|---|---|']
    for fid,path,loc,summary in facts:
        r=bypath[('LIB-010','KR_4.91_491v.zip!'+path)]
        lines.append(f'|{fid}|{r["member_id"]}<br>{path}|{loc}|{summary}|{r["sha256"]}|')
    lines+=['','## P2용 대표 원본 연결','',
      '|파일|member ID|SHA-256|준비한 정보 / 남은 확인|','|---|---|---|---|']
    target=['Body.epf','Body.pal','Body.tbl','Head.epf','Head.tbl','Sword.epf','Sword.tbl','Item.epf','Item.tbl','Effect.epf','Effect.tbl','Effect.frm','EffLayer.tbl','EffRange.tbl','DrwOrder.tbl','MonsFrm.tbl','DlgLogin.epf','DlgNew01.epf','Str_Kor.res']
    for n in target:
        r=original.get(n.lower())
        if r:lines.append(f'|{n}|{r["member_id"]}|{r["sha256"]}|원본 경로/바이트 고정. 의미·렌더링·실행은 P2에서 확인|')
    lines+=['','## 미활용·미조사와 다음 행동','',
      '- 해독 실패: KR/NA 설치 보조 _SYS1.CAB/_USER1.CAB는 host libarchive 미지원이며 주 데이터와 별도 기록한다. 필요한 런타임 파일이 P2 기준 조합에서 확인될 때만 기존 reader를 확장한다.',
      '- 정적 내부 미조사: NA 단독 EXE, NA4.66 nxuswind.exe, NA_ALL 8개 EXE의 payload는 이번 목록화에서 실행/추출하지 않았다. 이름·크기·SHA와 일부 installer marker만 기록했다. 같은 SHA의 4.95/프랑스 실행파일은 별도 독립 자료로 중복 계산하지 않는다.',
      '- ID 미식별: 프레임 원본 ID와 팔레트는 연결되지만 기술명→효과ID→소리ID→시점 연결은 후속 표/관찰로 채워야 한다. 자료 있음과 완성 기술을 구분한다.',
      '- 버전 불일치: KR1.25 지도, KR4.91 그래픽·문서, NA495 지형과 후대 지형은 각각 보존한다. 다른 도시좌표/도사 추가 예정 문구의 충돌을 평균내지 않는다.',
      '- 지원 코드 없음: 새 게임은 미구현이므로 모든 자산의 새 런타임 BOUND/EXERCISED는 NOT_RUN이다.',
      '- 의도적 미사용: 목표시기 밖 클라이언트와 개인정보 포함 가능 기존 save/build evidence를 새로운 게임 데이터로 넣지 않는다. 원본은 개인 보관한다.',
      '- 패키징·캐시 원인: 같은 원본 지문만으로 기존 변환 코드가 올바르다고 확정하지 않는다. 입력+파서+설정+팔레트/ID mapping 지문을 P2 산출에 포함하고 캐시 변조·누락 시험을 설계한다.',
      '- 다음 재개: 한국 원본 후보 MAP를 별도 포맷으로 읽어 독립 참고 지도/도구와 구조 대조 → 한국491 텍스트 효과/레이어/캐릭터표의 frame ID 연결 → 로그인·생성 UI 후보의 clipping 영향을 독립 비교. 이 문서는 P2를 실행한 결과가 아니다.','',
      '## 수행한 정적 검사의 결과','',
      '```json',json.dumps(checks,ensure_ascii=False,indent=2),'```','',
      '재현: 먼저 inventory_archives.py로 ZIP/7z를 목록화하고 link_archive_metadata.py를 실행한다. --tools는 기존 커밋의 두 파서로 hash gate를 통과해야 하며, --private-work는 공개 checkout 밖으로 지정한다. 새 게임 시험 결과는 전부 NOT_RUN이다.','']
    (a.output/'archive_evidence.md').write_text('\n'.join(lines))
    print(json.dumps({'sources':len(sources),'members':len(members),'unique_hashes':len({r['sha256'] for r in members}),'checks':checks},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
