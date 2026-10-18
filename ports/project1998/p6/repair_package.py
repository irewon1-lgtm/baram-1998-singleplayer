"""Package P6 six-defect repair separately from the immutable code6 delivery."""
import argparse,base64,hashlib,html,json,zipfile
from pathlib import Path
from PIL import Image,ImageDraw

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--commit',required=True)
    a=p.parse_args();w=a.workspace.resolve();repo=w/'baram-base';root=w/'p1998-private/p6-fix1';exp=root/'experiment-2';runtime=exp/'runtime';out=w/'deliverables/p6-fix1'
    result=read(repo/'ports/project1998/docs/P6_REPAIR_RESULTS.json')
    names=['p1998-s10fe-p6-fix1-'+n for n in ['results.html','evidence.zip','private-resources.zip','preview.png','delivery.json','SHA256.txt']]
    files=[out/n for n in names];assert not any(f.exists() for f in files)
    apk=out/'p1998-s10fe-p6-fix1.apk';assert sha(apk)==result['build']['sha256']
    secret=(w/'p1998-private/build/signing/password').read_bytes().strip()
    def archive(path,entries):
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            seen=set()
            for f,name in entries:
                if name in seen:continue
                seen.add(name)
                assert not any(x in name.lower() for x in ['keystore','password','signing/'])
                if f.suffix in ['.json','.log','.txt','.html']:assert not secret or secret not in f.read_bytes(),str(f)
                z.write(f,name)
        with zipfile.ZipFile(path) as z:assert z.testzip() is None
    evidence=[]
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.suffix not in ['.json','.log','.png']:continue
        rel=f.relative_to(root)
        if any(part in ['source','runtime','content','editor-data','editor-config','dotnet-wrapper','v2','v1','cache-p5','logs','app-state'] or part.startswith('fixtures-') for part in rel.parts):continue
        if f.name in ['upload-request.json','LIBRARY_WRITEBACK.json']:continue
        evidence.append((f,str(rel)))
    for n in ['P6_REPAIR_RESULTS.json','P6_REPAIR_CONTRACT.json','STATE.json']:evidence.append((repo/'ports/project1998/docs'/n,n))
    archive(files[1],evidence)
    private=[]
    for folder in ['assets','audio','fonts','p6/art']:
        for f in sorted((runtime/folder).rglob('*')):
            if f.is_file() and f.suffix not in ['.uid','.import']:private.append((f,str(f.relative_to(runtime))))
    for n in ['capsule.json','capsule.zip','migration.json','PRIVATE_INPUT_NOTICE.txt']:private.append((runtime/n,n))
    private.append((runtime/'p6/locale.json','p6/locale.json'))
    for f in sorted((exp/'native').rglob('*')):
        if f.is_file():private.append((f,'native/'+str(f.relative_to(exp/'native'))))
    for n in ['REPAIR_ART_AUDIT.json','AUDIO_AUDIT.json','LOCALIZATION_AUDIT.json']:private.append((exp/n,n))
    private.extend([(w/'p1998-private/originals/4x/Inter.dat','originals/4x/Inter.dat'),(w/'p1998-private/originals/4x/NexusTK.snd','originals/4x/NexusTK.snd')])
    archive(files[2],private)
    qa=root/'qa-repair-6'
    images=[('world-960-1536.png','전체 화면과 반투명 조작'),('inventory.png','소지품'),('equipment.png','장착 아이템'),('stats.png','능력치'),('spells.png','기술'),('local-map.png','현재 지도'),('kingdom-map.png','원본 왕국 전도'),('main-game.png','수련 없이 국내성 진입')]
    sheet=Image.new('RGB',(1280,1050),'#17251c');draw=ImageDraw.Draw(sheet)
    for i,(name,label) in enumerate(images):
        im=Image.open(qa/name).convert('RGB');im.thumbnail((310,490));x=(i%4)*320;y=(i//4)*525
        sheet.paste(im,(x+(320-im.width)//2,y+22));draw.text((x+6,y+5),str(i+1),fill='white')
    sheet.save(files[3])
    def figure(f,caption):return '<figure><img src="data:image/png;base64,'+base64.b64encode(f.read_bytes()).decode()+'" alt="'+html.escape(caption)+'"><figcaption>'+html.escape(caption)+'</figcaption></figure>'
    rows=''.join('<tr><td>'+html.escape(c['case'])+'</td><td>'+str(c['checks'])+' PASS</td><td>'+html.escape(c['scope'])+'</td></tr>' for c in result['host_cases'])
    content=''.join(figure(qa/n,label) for n,label in images)
    content+=figure(root/'qa-pickup-1/pickup-pose.png','원본 금전 줍기 성공과 원본 앉는 자세 · 명시한 준비 상태')
    source='https://github.com/irewon1-lgtm/baram-1998-singleplayer/tree/'+a.commit+'/ports/project1998/p6'
    report='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 P6 수정 1</title><style>body{margin:0;background:#132219;color:#e2e8db;font:17px/1.65 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:26px 20px}h1,h2{color:#eed9a2}table{border-collapse:collapse;width:100%;font-size:15px}td,th{border:1px solid #57705b;padding:10px;text-align:left}figure{background:#0a1710;padding:14px;margin:24px 0}img{max-width:100%;max-height:850px;object-fit:contain}code{overflow-wrap:anywhere}a{color:#b8e6dc}.note{background:#33412a;padding:16px}</style><main><h1>PROJECT1998 / P6 수정 1</h1>
<p>기기 화면에서 보고한 여섯 결함의 수정본입니다. 기존 P6 결과와 별도로 보관합니다.</p><p class="note">기존 앱을 삭제하지 말고 업데이트 설치하세요. code7 / 0.0.6-p6-fix1. 같은 패키지·서명·저장 경로를 유지합니다. PC 실행과 APK 빌드는 통과했으며, 이 수정 APK의 실제 갤탭 실행은 미검증입니다.</p>
<ol><li>게임을 화면 전체에 그리고 HUD·반투명 버튼을 위에 겹칩니다. 방향키를 제거하고 터치 이동을 유지합니다. 작은 지도는 카메라를 확대해 빈 띠를 없앱니다.</li><li>원본 C#의 줍기 동작 통지를 받아 원본 몸·머리 76~79번 앉는 자세를 표시합니다. 빈 칸의 줍기 시도도 원본 동작을 따릅니다.</li><li>토끼와 몬스터를 ID별로 0.2초 동안 이동 보간하고 실제 걷는 동안 원본 걸음 프레임을 재생합니다. 표시 위치로 대상을 선택할 수 있습니다.</li><li>지역 안내에 실제 현재 지도·내 위치·NPC·출구를 표시합니다. 확대·이동·지도 터치 이동과 원본 왕국 전도를 제공합니다.</li><li>새 캐릭터와 기존 수련 지역 저장에서 ‘본게임 시작’을 누르면 국내성으로 바로 갑니다. 원본 주막/교관 집 출구의 국내성 좌표 0(87,147)를 사용합니다. 경험치·금전·아이템을 추가로 지급하지 않고 기존 획득 상태를 유지합니다.</li><li>소지품·기술·장착 아이템·능력치 창을 별도로 열 수 있습니다. 원본 두루마리 그림, 아이템 아이콘, 실제 장비를 반영한 인형과 장비/현재 효과를 반영한 능력치를 연결했습니다.</li></ol>
<h2>실행 검증</h2><table><tr><th>검사</th><th>결과</th><th>범위</th></tr>'''+rows+'''</table><p>실제 Godot/Linux 프로세스에서 화면 터치 이벤트, 원본 NPC 보상·착용·해제·회복·이동 기술·줍기·저장·냉시작을 실행했습니다. 화면 좌표는 실제 캔버스 변환을 적용했습니다. 준비 상태는 자연 획득으로 주장하지 않습니다. 이전의 미흡한 화면 검사와 실패 실행도 증거 ZIP에 보존합니다.</p>
<p>47개 지도의 캡슐과 v2 저장 스키마는 동일합니다. 원본 C# 145개 파일은 선언한 경로/출력 관찰 경계를 제거하면 일치합니다. 수련 건너뛰기는 이번에 사용자가 요청한 별도의 오프라인 단계·위치 전환입니다. 일반 출입구·전투·보상·상점·Lua 규칙은 바꾸지 않았습니다.</p>
<h2>실제 실행 화면</h2>'''+content+'''<h2>빌드와 남은 범위</h2><p>패키지 <code>com.irewon.baram.project1998.p3</code> · arm64-v8a / x86_64 · INTERNET 권한 없음.</p><p>APK SHA256 <code>'''+sha(apk)+'''</code><br>서명 SHA256 <code>'''+result['build']['signer_sha256']+'''</code></p><p>올려주신 P6 기기 화면은 이전 버전의 화면/플레이 관찰 증거입니다. 새 수정본의 갤탭 업데이트 설치·손가락 조작·한글 IME·화면 회전·수명 주기·최소 FPS/발열/배터리·16KiB 페이지 지원은 미검증입니다. 기존 47개 지도 범위, 일부 아이콘 공백, 후반 대사·시대 표기 검토, 미구현 MIDI 음악·전체 마법 효과/장비 레이어 등의 경계는 유지합니다. 전체 세계나 모든 원본 창의 픽셀 단위 일치를 주장하지 않습니다.</p><p><a href="'''+source+'''">수정 소스</a></p></main></html>'''
    files[0].write_text(report)
    deliver=[apk,*files[:4]]
    files[4].write_text(json.dumps({'status':'BUILD_PASS_AND_HOST_FINITE_SCOPE_PASS; NOT_RUN_DEVICE_FIX1','source_commit':a.commit,'source_branch':'work/project1998-s10fe-p6-repair-20261018','build':result['build'],'save':result['save'],'files':[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in deliver]},ensure_ascii=False,indent=2)+'\n')
    files[5].write_text(''.join(sha(f)+'  '+f.name+'\n' for f in deliver+[files[4]]))
    print(json.dumps([{'name':f.name,'bytes':f.stat().st_size} for f in [apk,*files]],ensure_ascii=False))

if __name__=='__main__':main()
