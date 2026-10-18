"""Package verified P6 outputs; source code remains in Git, assets stay private."""
import argparse,base64,hashlib,html,json,shutil,subprocess,zipfile
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--commit',required=True)
    a=p.parse_args();w=a.workspace.resolve();repo=w/'baram-base';root=w/'p1998-private/p6';runtime=root/'experiment-1/runtime';out=w/'deliverables/p6'
    result=load(repo/'ports/project1998/docs/P6_RESULTS.json');apk=out/'p1998-s10fe-p6-korean.apk'
    assert sha(apk)==result['build']['sha256']
    generated=[out/('p1998-s10fe-p6-'+name) for name in ['results.html','evidence.zip','private-resources.zip','preview.png','delivery.json','SHA256.txt']]
    assert not any(f.exists() for f in generated),'Preserve previous delivery; choose new names instead'
    shutil.copyfile(root/'qa-ui-6/02-landscape.png',generated[3])
    secret=(w/'p1998-private/build/signing/password').read_bytes().strip()
    def write_zip(target,entries):
        used=set()
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for file,name in entries:
                if name in used:continue
                used.add(name)
                if file.suffix.lower() in ['.json','.log','.txt','.html']:
                    assert not secret or secret not in file.read_bytes(),('Secret in evidence',file)
                assert not any(x in name.lower() for x in ['keystore','password','signing/'])
                archive.write(file,name)
        with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
    entries=[]
    # Results/logs/images only: no duplicate Git checkout, keys or device saves.
    for file in sorted(root.rglob('*')):
        if not file.is_file() or file.suffix.lower() not in ['.json','.log','.png']:continue
        rel=file.relative_to(root)
        if any(part in ['runtime','source','content','app-state','user-data','editor-config','editor-data','dotnet-wrapper','v1','v2','cache-p5','logs','run'] for part in rel.parts):continue
        if file.name in ['LIBRARY_WRITEBACK.json','upload-request.json']:continue
        if rel.parts[0].startswith('fixtures-') and file.name!='FIXTURES.json':continue
        if rel.parts[0]=='angel-state' and file.name!='FIXTURE.json':continue
        entries.append((file,str(rel)))
    entries += [(repo/'ports/project1998/docs/P6_RESULTS.json','P6_RESULTS.json'),(repo/'ports/project1998/docs/STATE.json','STATE.json')]
    write_zip(generated[1],entries)
    private=[]
    for folder in ['assets','audio','fonts']:
        for file in sorted((runtime/folder).rglob('*')):
            if file.is_file() and file.suffix not in ['.import','.uid']:private.append((file,str(file.relative_to(runtime))))
    for name in ['capsule.json','capsule.zip','migration.json','PRIVATE_INPUT_NOTICE.txt']:
        private.append((runtime/name,name))
    for file in sorted((root/'experiment-1/native').rglob('*')):
        if file.is_file():private.append((file,'native/'+str(file.relative_to(root/'experiment-1/native'))))
    private += [(runtime/'p6/locale.json','locale/locale.json'),(w/'p1998-private/originals/4x/NexusTK.snd','originals/4x/NexusTK.snd'),
                (root/'experiment-1/AUDIO_AUDIT.json','AUDIO_AUDIT.json'),(root/'experiment-1/LOCALIZATION_AUDIT.json','LOCALIZATION_AUDIT.json')]
    write_zip(generated[2],private)
    loc=result['localization']['application'];coverage=''.join('<tr><td>'+label+'</td><td>'+str(loc[key]['regional_fully_korean'])+' / '+str(loc[key]['regional_rows'])+'</td><td>100% 적용 · 의미/시대 REVIEW</td></tr>' for key,label in [('maps','지도 이름'),('items','상점·매입·전리품·시작 아이템'),('spells','공통·네 직업의 중립 기술 이름'),('npcs','NPC 배치 이름'),('mobs','등장 몬스터 이름')])
    cases=''.join('<tr><td>'+html.escape(r['mode'])+'</td><td>'+str(r['checks'])+' PASS</td><td>'+('명시한 준비 상태' if r['fixture'] else '기존 저장에서 이어 실행')+'</td></tr>' for r in result['host_cases'])
    perf=''.join('<tr><td>'+html.escape(v['phase'])+'</td><td>%.1f</td><td>%.1f ms</td></tr>'%(v['average_fps'],v['p95_frame_ms']) for v in result['performance']['phases'])
    def figure(path,caption):
        data=base64.b64encode(path.read_bytes()).decode()
        return '<figure><img src="data:image/png;base64,'+data+'" alt="'+html.escape(caption)+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>'
    images=figure(w/'p1998-private/p5/qa-smoke-3/new-game.png','P5: 시작 지도 / 1280×800')+figure(root/'qa-ui-6/02-landscape.png','P6: 같은 시작 지도와 화면 크기. 이름·상태 막대·글꼴·조작 배치를 개선했습니다. 무작위 체력·몹 배치는 비교 대상이 아닙니다.')
    images+=figure(root/'qa-ui-6/01-korean-input.png','호스트 Unicode 키 입력으로 생성한 한글 이름. 실제 Android IME 조합은 미실행입니다.')
    images+=figure(root/'qa-ui-6/size-540-960.png','540×960 창의 세로 배치와 가방. 배경 입력은 모달이 차단합니다.')
    images+=figure(root/'qa-angel-2/angel-korean-dialog.png','원본 천사 NPC 대사와 한글 완료 응답 연결. 명시한 단계9 준비 상태에서 실행했습니다.')
    source_url='https://github.com/irewon1-lgtm/baram-1998-singleplayer/tree/'+a.commit+'/ports/project1998/p6'
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 P6 검증 결과</title><style>body{font:17px/1.65 system-ui,sans-serif;color:#dae4d9;background:#132219;margin:0}main{max-width:1100px;margin:auto;padding:30px 22px}h1{font-size:34px}h2{margin-top:42px;color:#e1d399}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:10px;border:1px solid #49604f;text-align:left}p{max-width:90ch}.tag{display:inline-block;border:1px solid #76916f;padding:5px 12px;border-radius:8px;margin:5px}code{overflow-wrap:anywhere}a{color:#a7d4cf}img{max-width:100%;max-height:760px;object-fit:contain}figure{margin:22px 0;background:#0c1811;padding:12px}figcaption{color:#afc3b2;font-size:14px}.note{border-left:4px solid #c5aa6b;padding:14px;background:#22342a}</style><main>
<h1>PROJECT1998 / P6</h1><p>한국어 표시·입력, 모바일 UI, 원본 효과음과 저장 품질 보수</p><span class="tag">HOST: 검증 범위 PASS</span><span class="tag">APK: BUILD_PASS</span><span class="tag">GALAXY: 미실행</span>
<p class="note">기존 P5/P4 앱을 삭제하지 말고 P6 APK를 업데이트 설치하세요. 패키지·서명·저장 경로를 유지했습니다. 실제 갤탭 설치·IME·터치·성능의 통과를 뜻하지 않습니다.</p>
<h2>변경된 동작</h2><p>한글 이름을 입력하고 다시 시작해도 표시 이름이 유지됩니다. 상점·장비·기술·지도·NPC 이름을 한국어로 보여 주며 원본 구매 값과 퀘스트 응답은 그대로 전달합니다. 한글 ‘완료’와 동·서·남·북 응답이 실제 C# 규칙으로 연결됩니다. 가로/세로 배치, 긴 글 스크롤, 키보드 회피, 배경 터치 차단, 체력·마력 막대를 보수했습니다. 원본 선택 효과음에는 음량·음소거·백그라운드 정지를 연결했습니다.</p>
<h2>한국어 적용률과 검증률</h2><table><tr><th>유한 범위의 표시 필드</th><th>한국어 적용 행</th><th>정확성 판정</th></tr>'''+coverage+'''</table><p>표는 이번 47개 지도 범위의 이름 필드 적용률입니다. 전 세계 콘텐츠·모든 대사·모든 기술을 실행 검증했다는 뜻이 아닙니다. 후보 번역·조합 번역과 고유명사의 역사적 표기는 REVIEW입니다. 뒤쪽 퀘스트의 대사는 영문이 남을 수 있습니다. 실제 검증은 아래의 메뉴·원본 규칙 실행 사례로 구분합니다. Android IME/실기기 검증률은 NOT_RUN입니다.</p>
<h2>실행 증거</h2><table><tr><th>실제 Godot / Linux 실행</th><th>검사</th><th>범위</th></tr>'''+cases+'''</table><p>저장 중 실제 SIGKILL, SQLite 현재·이전 체크포인트, 완전한 캐릭터·몬스터·전리품 냉시작 복구와 미래/손상 데이터 거부 6건이 통과했습니다. P3의 82개 시험 파일을 보존했습니다. 네 직업·마법·사망·천사 단계는 준비 상태를 명시했습니다. 자연 획득을 주장하지 않습니다. 기존 P5 저장의 전체 캐릭터·revision·identity를 P6에서 보존했습니다.</p>
<p>원본 C# 145개 파일은 선언한 경로·출력 관찰 경계를 제거하면 일치합니다. 47개 지도·가격·기술 비용·Lua·원본 저장 캡슐은 P5와 동일합니다. 기존 원본 출입구 357 PASS와 도달 불가능한 원본 타일 2건을 그대로 구분합니다. 실패했던 실행과 수정 원인도 증거 ZIP에 남겼습니다.</p>
<h2>오디오와 성능</h2><p>원본 WAV 184개를 사용하며 PCM 바이트를 보존했습니다. 원본 선택 효과음의 실제 믹서 출력은 28,672 샘플, peak 약 0.6503으로 확인했습니다. 음소거·중복 재생 방지·정지 동작을 검사했습니다. 실제 Android 스피커는 미검증입니다.</p><table><tr><th>Linux 소프트웨어 렌더링</th><th>평균 FPS</th><th>프레임 시간 p95</th></tr>'''+perf+'''</table><p>각 구간 180프레임, 총 720프레임을 실제 측정했습니다. 평균 FPS를 갤탭의 최소 FPS·발열·배터리 검증으로 바꾸어 해석하지 않습니다. 원본 MIDI BGM의 합성기/음색 뱅크는 제공되지 않아 음악은 미구현입니다. 원본 Windows의 암묵적 동작음·전체 창/장비 레이어·시전 자세/마법 이펙트 일치를 주장하지 않습니다.</p>
<h2>화면 비교</h2>'''+images+'''<h2>업데이트 APK</h2><p>파일: <code>'''+apk.name+'''</code><br>버전: 0.0.6-p6 / code6<br>패키지: com.irewon.baram.project1998.p3<br>INTERNET 권한 없음 · arm64-v8a / x86_64</p><p>SHA256: <code>'''+sha(apk)+'''</code><br>서명 SHA256: <code>'''+result['build']['signer_sha256']+'''</code></p><p><a href="'''+source_url+'''">검증한 P6 소스 커밋</a> · 전체 기록은 증거 ZIP과 전달 JSON을 참고하세요.</p><h2>다음 수락 시험</h2><p>실제 갤럭시탭에서 업데이트 설치, 한글 키보드, 비행기 모드, 손가락 조작, NPC·상점·네 직업·마법·사망/부활, 저장 후 재실행, 뒤로 가기·화면 회전·백그라운드, FPS·발열·배터리를 확인해야 합니다. Android 16KiB 페이지 지원도 미검증입니다. 추가 세계·채집 리소스·일부 아이콘의 P5 경계는 유지합니다.</p></main></html>'''
    generated[0].write_text(text)
    files=[apk,*generated[:4]]
    receipt={'status':'BUILD_PASS_AND_HOST_SCOPE_VERIFIED; NOT_RUN_DEVICE_P6','source_commit':a.commit,'source_url':source_url,'source_branch':'work/project1998-s10fe-p6-20261018','apk_identity':result['build'],'save_policy':result['save'],'files':[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in files],'resources':'private original/converted assets, font, capsule and Android SQLite only; source code in Git; no signing key or user device save'}
    generated[4].write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    generated[5].write_text(''.join(sha(f)+'  '+f.name+'\n' for f in files+[generated[4]]))
    print(json.dumps([{'name':f.name,'bytes':f.stat().st_size} for f in [apk,*generated]],ensure_ascii=False))

if __name__=='__main__':main()
