"""Package the private code8 APK, execution evidence, assets and comparison."""
import argparse,base64,hashlib,html,json,shutil,zipfile
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--commit',required=True);a=p.parse_args()
    w=a.workspace.resolve();repo=w/'baram-base';root=w/'p1998-private/p6-fix2';exp=root/'experiment-1';runtime=exp/'runtime';out=w/'deliverables/p6-fix2'
    result=read(repo/'ports/project1998/docs/P6_REFERENCE_RESULTS.json');compat=read(repo/'ports/project1998/docs/P6_SOURCE_COMPATIBILITY.json');verify=read(root/'PACKAGE_VERIFY.json');assert verify['status']=='PASS'
    apk=out/'p1998-s10fe-p6-fix2.apk';assert sha(apk)==result['build']['sha256']
    names=['p1998-s10fe-p6-fix2-'+n for n in ['results.html','evidence.zip','private-resources.zip','preview.png','delivery.json','SHA256.txt']];files=[out/n for n in names];assert not any(f.exists() for f in files)
    secret=(w/'p1998-private/build/signing/password').read_bytes().strip()
    def archive(path,entries):
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            seen=set()
            for f,name in entries:
                if name in seen:continue
                seen.add(name);assert not any(s in name.lower() for s in ['keystore','password','signing/'])
                if f.suffix in ['.json','.log','.txt','.html']:assert not secret or secret not in f.read_bytes(),str(f)
                z.write(f,name)
        with zipfile.ZipFile(path) as z:assert z.testzip() is None
    evidence=[]
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.suffix not in ['.json','.log','.png']:continue
        rel=f.relative_to(root)
        if any(part in ['source','runtime','content','editor-data','editor-config','dotnet-wrapper','v2','v1','cache-p5','logs','app-state','git-payload'] for part in rel.parts):continue
        if f.name in ['upload-request.json','LIBRARY_WRITEBACK.json']:continue
        evidence.append((f,str(rel)))
    for name in ['P6_REFERENCE_CONTRACT.json','P6_REFERENCE_RESULTS.json','P6_SOURCE_COMPATIBILITY.json','STATE.json']:evidence.append((repo/'ports/project1998/docs'/name,name))
    archive(files[1],evidence)
    resources=[]
    for directory in ['assets','audio','fonts','p6/art']:
        for f in sorted((runtime/directory).rglob('*')):
            if f.is_file() and f.suffix not in ['.uid','.import']:resources.append((f,str(f.relative_to(runtime))))
    for name in ['capsule.json','capsule.zip','migration.json','PRIVATE_INPUT_NOTICE.txt','p6/locale.json']:resources.append((runtime/name,name))
    for f in sorted((exp/'native').rglob('*')):
        if f.is_file():resources.append((f,'native/'+str(f.relative_to(exp/'native'))))
    for name in ['REPAIR_ART_AUDIT.json','REFERENCE_ART_AUDIT.json','AUDIO_AUDIT.json','LOCALIZATION_AUDIT.json']:resources.append((exp/name,name))
    for name in ['4x/Inter.dat','4x/NexusTK.snd','533/Misc.dat']:resources.append((w/'p1998-private/originals'/name,'originals/'+name))
    archive(files[2],resources)
    shutil.copyfile(root/'qa-update-5/equipment-1280-800.png',files[3])
    def figure(path,caption):return '<figure><img src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>'
    source='https://github.com/irewon1-lgtm/baram-1998-singleplayer/tree/'+a.commit+'/ports/project1998/p6'
    rows=''.join('<tr><td>'+html.escape(c['case'])+'</td><td>'+str(c['checks'])+' PASS</td></tr>' for c in result['host']['cases'])
    positions=''.join('<tr><td>'+str(int(n['npc']))+'</td><td>'+str(list(map(int,n['source'])))+'</td><td>'+str(list(map(int,n['position'])))+'</td></tr>' for n in compat['npc_execution'] if n['changed'])
    omissions=''.join('<li>'+html.escape(s)+'</li>' for s in compat['unported_or_not_equivalent'])
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 P6 수정 2</title><style>body{margin:0;background:#211108;color:#eddbb7;font:17px/1.65 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:24px 20px}h1,h2{color:#e9be79}a{color:#efce93}table{border-collapse:collapse;width:100%;font-size:15px}td,th{border:1px solid #966437;padding:8px;text-align:left}figure{margin:24px 0;padding:10px;background:#0d0805}img{max-width:100%;max-height:900px;object-fit:contain}code{overflow-wrap:anywhere}.note{background:#5b3217;padding:16px}</style><main><h1>PROJECT1998 / P6 수정 2</h1><p class="note">기존 앱을 삭제하지 말고 업데이트 설치하세요. code8 / 0.0.6-p6-fix2 · 같은 패키지·서명·저장 경로입니다. PC의 실제 Godot 실행과 APK 빌드는 통과했습니다. 새 APK의 실제 Android/Galaxy 실행은 미검증입니다.</p>
<h2>이번에 수정한 동작</h2><ol><li>참조 화면의 갈색 장식과 말린 두루마리로 오른쪽 고정 UI를 구성했습니다. 소지품·장비·기술·능력치와 이름·직업·레벨·체력·마력·경험치·금전·좌표를 원본 코어 데이터로 표시합니다. 참조 플레이어의 이름이나 수치를 복사하지 않았습니다. 아래에는 원본 미니 메시지와 대화 기록이 따로 표시됩니다.</li><li>‘말하기’를 누르면 실제 NPC를 선택하고, 옆 칸까지 이동한 뒤 원본 대화를 엽니다. NPC 그림을 직접 눌러도 동일합니다. 도적 길드의 제보 위치 (2,15)에서 일반 말하기 버튼으로 NPC 창이 열리는 것을 재현했습니다. 말에만 반응하는 NPC는 원본 질문과 직접 입력을 제공합니다.</li><li>36명 모두 원본 충돌과 배경 가림을 검사하고 문제가 있는 18명의 실제 개체만 가까운 독립된 위치로 옮겼습니다. 원본 지도·NPC CSV·ID·스크립트는 유지했습니다.</li><li>구매 분류·상품·수량·판매 확인까지 원본 상점 흐름을 연결했습니다. F1 메뉴, 한 개/전체 내려놓기, 현재 효과와 말풍선 메시지 기록도 연결했습니다.</li><li>상점 아이콘 누락 32개 중 제공된 원본 5.33 자료에 있는 29개를 복원했습니다. 실제 반지 착용·능력치 증가·해제·내려놓기·줍기를 실행했습니다.</li><li>지역 이동 직후 새 목적지를 누르면 그 명령까지 취소하던 오류를 고쳤습니다. 같은 준비 상태에서 실패했던 전사·도적 교습소 진입을 재시험했고, 네 직업 모두 전직과 유료 기술 학습을 완료했습니다.</li></ol>
<h2>실제 실행 화면</h2>'''
    for path,caption in [('qa-update-5/equipment-1280-800.png','기존 code7 호스트 저장의 이어하기 · 고정 오른쪽 장비 창과 실제 상태'),('qa-update-5/bag-960-1536.png','세로 화면 · 두루마리 비율 유지와 실제 소지품'),('qa-fresh-3/smith-tutorial-dialog.png','새 캐릭터의 원본 대장장이 대화 · 실제 NPC 접근과 보상'),('qa-rogue-2/rogue-native-dialog.png','제보된 도적 길드 좌표를 준비한 명시적 재현 상태 · 실제 NPC 대화'),('qa-class-1-5/class-Warrior.png','명시적 Lv5 준비 상태 · 원본 전직과 기술 학습 후'),('qa-icons-4/restored-ring-equipment.png','명시적 Lv11/원본 반지 준비 상태 · 실제 착용과 +1 능력치')]:text+=figure(root/path,caption)
    text+='''<h2>검증 범위</h2><p>11개 Godot 실행에서 369개 제한된 범위 확인이 PASS입니다. 레벨·상품·금전 등을 준비한 상점/직업/마법/아이콘 사례는 자연 획득으로 주장하지 않습니다. 최종 화면/입력은 update-5와 class-*-5에서 실행했고, 앞서 실행한 변경 없는 원본 동작 증거는 해당 범위만 재사용했습니다. 실패한 실행도 보존했습니다.</p><table><tr><th>실행</th><th>결과</th></tr>'''+rows+'''</table><p>원본 C# 145개 파일은 선언한 경로/출력 관찰 경계를 제거하면 동일합니다. 최종 앱 소스 19개 항목과 동일한 47개 지도 캡슐을 확인했습니다. 실제 이전 수정본 저장의 이름·레벨·경험치·금전·소지품·장비·기술·지도·X/Y 10개 초기 필드가 일치했습니다.</p><p>APK의 동결 입력 '''+str(verify['frozen_inputs'])+'''개에 변동이 없고 원본 지도 47개, 필수 JSON, 가져온 리소스 '''+str(len(verify['imports']))+'''개 및 효과음 184개가 포함됩니다. 마법 사례는 비용/회복 확인과 exit0 후 종료 시 리소스 경고가 남아 있어 원본 로그에 보존했습니다.</p>
<h2>NPC 위치 수정</h2><p>좌표는 원본 정의와 별도의 실제 개체 배치입니다. 이 접근/가림 검사는 모든 퀘스트를 끝까지 완료한 증거가 아닙니다.</p><table><tr><th>원본 NPC ID</th><th>원본 좌표</th><th>수정 좌표</th></tr>'''+positions+'''</table><h2>원본과 아직 일치하지 않는 부분</h2><p>원본은 지도 메타데이터 9,850행, 지도 인덱스 2,031행, NPC 380행입니다. 현재 포트는 47개 지도와 NPC 36개입니다. 원본과 완전히 같거나 누락이 없다고 처리하지 않았습니다. 전체 CSV 유지/필터 결과와 남은 목록은 증거의 P6_SOURCE_COMPATIBILITY.json에 있습니다. 남은 아이콘: light_fox_fur, mining_pick, red_fox_fur.</p><ul>'''+omissions+'''</ul><p>창의 위치·기능·갈색 색감과 장식은 참조에 맞췄지만, 제공된 영문 클라이언트와 원본 한글 클라이언트의 스킨/글꼴이 달라 모든 창의 픽셀 단위 동일성은 보장하지 않습니다. 새 APK의 실제 갤탭 손가락 입력·IME·회전·수명 주기·FPS/발열/배터리도 이번 호스트 검사에 포함되지 않습니다.</p><h2>빌드</h2><p>패키지 <code>'''+result['build']['package']+'''</code> · arm64-v8a / x86_64 · INTERNET 권한 없음.<br>APK SHA256 <code>'''+sha(apk)+'''</code><br>서명 SHA256 <code>'''+result['build']['signer_sha256']+'''</code></p><p><a href="'''+source+'''">수정 소스</a> · 기존 code7 결과물은 유지했습니다.</p></main></html>'''
    files[0].write_text(text)
    deliver=[apk,*files[:4]]
    files[4].write_text(json.dumps({'status':result['status'],'source_commit':a.commit,'source_branch':'work/project1998-s10fe-p6-reference-ui-20261018','build':result['build'],'save':result['save'],'files':[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in deliver]},ensure_ascii=False,indent=2)+'\n')
    files[5].write_text(''.join(sha(f)+'  '+f.name+'\n' for f in deliver+[files[4]]))
    print(json.dumps([{'name':f.name,'bytes':f.stat().st_size} for f in [apk,*files]],ensure_ascii=False))
if __name__=='__main__':main()
