"""Build an evidence-grounded r28 report and extend, rather than replace, the world ledger."""
import base64, hashlib, html, json, zipfile
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[2]
W = R.parents[1]
OUT = W / 'deliverables'
REPORT = R / 'r28-report'
REPORT.mkdir(exist_ok=True)
def read(p): return json.loads((R / p).read_text())
def write(p, d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

build = read('android/evidence/build-r28-001/BUILD_RECEIPT.json')
apk = OUT / 'Project1998-r28-update-arm64.apk'
assert build['status'] == 'BUILD_PASS' and sha(apk) == build['sha256']
assert build['package'] == 'com.irewon.project1998.g1bv4' and build['version_code'] == 32
assert build['certificate_sha256'] == 'ecea13778e2466b3e568f45bfe1facb6fd708bdd0ed3f6ae2a4c305da2ebb030'
assert build['content_files'] == 8056 and not build['test_fixture_packaged']
frozen = read('verification/r28/RELEASE-PRODUCTS.json')['source']
changed = [p for p,h in frozen.items() if sha(R/p) != h]
assert not changed, changed
ui = read('evidence/r28/ui/final002/RECEIPT.json')
prior_ui = read('evidence/r27/ui/r28-final-regression002/RECEIPT.json')
suite = read('evidence/r25/suite/r28-final002/RESULT.json')
comparison = read('evidence/r28/XUNIT-COMPARISON.json')
catalog = read('evidence/r28/catalog/final001/RESULT.json')
assert ui['check_count'] == 28 and ui['check_status'].startswith('PASS')
assert prior_ui['check_count'] == 21 and prior_ui['check_status'].startswith('PASS')
assert comparison['status'] == 'PASS_NO_NEW_FAILURES'
assert all(x['status']=='PASS' for x in suite['results'] if x['name']!='original-xunit')
old_issues = read('r26-report/Project1998-r26-results.json')['nine_issues']
features = [
    ['NPC 대화 뒤로가기', 'PC 실제 UI PASS', '상점·하위 대화의 닫기/뒤로가기는 이전 메뉴로 돌아갑니다. 최상위에서 뒤로가기를 누르면 대화를 끝냅니다. 구매·보상 선택을 다시 실행하지 않으며, 안전하지 않은 Lua 앞부분은 재실행하지 않습니다.'],
    ['가방 좌우 스와이프', 'PC 실제 UI PASS', '가방 영역을 좌우로 밀어 페이지를 바꿉니다. 큰 이전/다음 버튼과 페이지 표시도 유지합니다. 세로 이동·취소·경계 제스처는 아이템 사용을 일으키지 않으며, 스와이프 후 남은 더블 탭을 지웁니다.'],
    ['동일 아이템 99개 묶음', 'PC UI·저장 검사 PASS', '도토리 100개는 99+1칸으로 나눕니다. 이름·소유자·내구도·수리·보호 상태가 모두 같은 것만 합칩니다. 장착·소모는 원래 처리기로 한 개씩 처리하고 수량과 상태를 보존합니다.'],
    ['상세 지도와 길 안내', 'PC 실제 UI·전수 메타데이터 검사 PASS', '현재 국가/지역·지도·좌표, 원본 지형 확대/축소·전체 보기, 길드·NPC·상점·입구 좌표와 검색을 제공합니다. 부여 주술사 길드 입구 (126,35)를 원본 연결과 대조했습니다. 길 안내의 첫 출입구까지 기존 자동이동을 사용하며 지도 전환 시 멈춥니다.']
]
limits = [
    '물리 Android 설치·실기기 입력·실제 사용자 진행 저장·레벨별 재실행 성능·CPU/RAM/GC/발열 비교: NOT_RUN. PC 합성 캐릭터 결과를 실기기 PASS로 바꾸지 않았습니다.',
    '전체 xUnit 2093개 중 2027 PASS, 66 FAIL. 기존 r27의 66개와 이름 및 실패 메시지가 같습니다. 새 실패 0개입니다. 전체 게임·성능이 모두 통과했다고 주장하지 않습니다.',
    '기존 전체 지도 원장은 7948지도/10533 유효 출입구 행을 기록합니다. 과거 호스트 완전 왕복 3333행, 검토·제외 7200행은 그대로 남습니다. 전 지도 육안 검수/조건별 실제 진행 완료가 아닙니다.',
    'r28 길 안내 메타데이터는 7948지도/9241표시점 전부 검사했습니다. 원본 좌표 문제 22건은 검토 대상으로 남겨 두었습니다. 이번 UI 통과가 그 22건 또는 기존 7200행의 해결을 뜻하지 않습니다.',
    '이미 99개를 넘는 옛 묶음이 있고 빈 칸이 부족하면 원본 수량을 보존합니다. 칸이 확보되면 분리합니다. 개별 내구도·충전량 등이 달라지는 물품은 한 개를 분리할 빈 칸이 필요할 수 있습니다.',
    '부두막/부뚜막이라는 등록 목적지는 원본 데이터에 없습니다. 주막 검색 결과와 안내를 표시하며 임의 장소를 새로 만들지 않았습니다.',
    '원본과 다른 상점 외형 재구성 38칸 및 기존 문/던전 검토 상태는 r26 원장에 명시되어 있습니다. r28은 game-data 8056파일을 변경하지 않았습니다.'
]
attempts = [
    'r27 실제 NPC 하위 메뉴 닫기가 대화를 끊는 문제를 baseline002/003에서 재현했습니다. baseline001은 시험 코드 컴파일 오류로 NOT_RUN입니다.',
    '원래 묶음 정책은 새 99개 기준 검사에서 10 FAIL/1 PASS였습니다. 최종 17개 신규 묶음 안전성 검사가 통과했습니다.',
    '초기 UI 시도에서 가방 패널 좌표, 지도 창 높이, 경로 시험 대기 시간이 드러났습니다. 실제 좌표/창 높이/기존 길찾기 첫 출입구 선택을 고쳤으며 최종 final002의 28개 검사가 통과했습니다.',
    '이전 아이템 UI의 정확한 JSON 재저장 비교에서 불필요한 리스트 순서 변경을 발견했습니다. 이미 정돈된 가방은 원본 순서와 객체를 그대로 유지하도록 고쳤고 21개 기존 검사와 재실행 보존 검사가 통과했습니다.',
    '첫 전체 회귀는 67개 xUnit 실패로, 기존 66개 외에 TickSweepSkipTests의 시스템 알림 한 개 차이가 있었습니다. r27/최종본의 격리 시험은 통과했고 최종 전체 재실행에서는 66개만 실패했습니다. 초기 현상의 원인을 확정하지 않습니다.',
    '옛 가방 시험의 원래 stack-cap 기대값은 사용자의 99+1 요구에 맞춰 수량·컨테이너 보존 검증을 유지한 채 갱신했습니다. 이전 UI는 의도적으로 유지되는 NPC 상위 메뉴를 실제 닫은 후 홈 메뉴로 이동하게 갱신했습니다.',
    '누락된 286개 자산 검사 경로는 이미 포함된 동일 자산 목록 r24-release-report/ASSETS-286.json을 사용하도록 시험 참조를 고쳤습니다. 게임 자산은 바꾸지 않았습니다.'
]
result = {
    'schema':'P1998_R28_DELIVERY_1', 'generated_utc':datetime.now(timezone.utc).isoformat(),
    'status':'SIGNED_APK_READY_WITH_EXPLICIT_INHERITED_FAILURES_AND_DEVICE_NOT_RUN',
    'build':build, 'features':features, 'limits':limits, 'attempt_history':attempts,
    'final_ui':{'new':28,'preserved_r27':21,'legacy_items':676,'environment':'PC actual Godot, synthetic characters'},
    'safety':{'bag_cases':17,'preserved_inspection_cases':11,'isolated_sweep_guard':1,'backup_restore_cases':6},
    'full_xunit':{'executed':2093,'passed':2027,'inherited_failed':66,'new_failed':0,'comparison':'evidence/r28/XUNIT-COMPARISON.json'},
    'regression':suite, 'map_catalog':catalog, 'original_nine_issues_inherited_scope':old_issues,
    'preservation':read('evidence/r28/PRESERVATION.json'),
    'tested_runtime_source_matches_export_source':True,
    'physical_android':'NOT_RUN','user_save_writes':0,
    'commits':{'core':'c5f9f0f','ui_map':'9816bd5','save_order':'e626a17','remote_runtime':'92e29544aef16a374175145603c5a6d8152272a5'}
}
write(REPORT/'Project1998-r28-results.json', result)
esc=lambda x:html.escape(str(x))
def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def ul(xs): return '<ul>'+''.join('<li>'+esc(x)+'</li>' for x in xs)+'</ul>'
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 r28 수정·검증 결과</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1120px;margin:32px auto;padding:0 20px;color:#202b37;background:#f7f9fc}h1,h2{line-height:1.25;color:#183950}table{width:100%;border-collapse:collapse;background:white;margin:20px 0}td,th{border:1px solid #cad4df;padding:11px;text-align:left;vertical-align:top}th{background:#e9f0f7}code{overflow-wrap:anywhere}img{display:block;max-width:100%;height:auto;background:#161c22}figure{margin:24px 0;padding:12px;background:white}li{margin:8px 0}.notice{background:#fff1cf;padding:16px;border-left:5px solid #c28800}small{overflow-wrap:anywhere}</style><h1>Project1998 r28 업데이트</h1><p>NPC 대화 복귀, 가방 스와이프, 99개 묶음, 현재 위치와 길드·상점을 찾는 상세 지도를 반영한 ARM64 업데이트 APK입니다. 최신 r27에서 이어서 r25의 거래·저장 안전성과 r26 이동·누적 상태 최적화를 보존했습니다.</p>'''
page += '<p class="notice">기존 서명으로 APK 제작·정렬·패키지 검사를 통과했습니다. 실제 Android 설치 및 사용자 진행 캐릭터 성능/발열 검사는 NOT_RUN입니다. 기존 66개 회귀 실패와 전체 지도 미해결 검토를 숨기지 않습니다.</p>'
page += '<h2>이번 네 가지 수정</h2>'+table(['항목','실행 결과','동작과 보존 범위'],features)
page += '<h2>설치 및 동일성</h2><p>기존 앱 위에 설치하는 업데이트입니다. 앱 삭제나 새 키 재서명을 사용하지 않았습니다. PC 시험은 복제한 합성 저장에서 수행했고 사용자 원본 저장에 쓴 횟수는 0입니다.</p>'
page += table(['검사','결과'],[['파일',apk.name],['크기',f'{apk.stat().st_size:,} bytes'],['SHA-256',build['sha256']],['패키지',build['package']],['버전',f"{build['version_name']} / code {build['version_code']}"],['기존 인증서 SHA-256',build['certificate_sha256']],['저장 폴더','user:// → project1998_g1b_v4'],['내장 데이터','8056파일 r27과 동일 / archive '+build['content_archive_sha256']],['최종 소스 대조',f"고정 APK 입력 {build['source_input_count']}개; 시험한 runtime source와 일치"],['APK 검증','원본 키 서명·16K zipalign·ARM64·실제 project.binary 설정·BuildId·테스트 fixture 미포함 PASS']])
page += '<h2>최종 실행 검사</h2>'+table(['검사','결과','근거'],[
    ['새 NPC·스와이프·묶음·지도 UI','28 PASS','evidence/r28/ui/final002'],
    ['단일 탭 정보·더블 탭 장착/소모 보존','21 PASS','evidence/r27/ui/r28-final-regression002'],
    ['신규 묶음 안전성 + 기존 아이템 검사','17 + 11 PASS','evidence/r28/safety-final002'],
    ['기존 아이템/NPC/상점/퀘스트 실제 UI','676 PASS','evidence/r25/items-ui/r28-final002'],
    ['거래·일반 상점·강제 종료 저장·백업 복원','21 / 10 / 2 / 6 PASS','evidence/r25/final-runtime 및 crash/r28-final002'],
    ['기존 콘솔 회귀 / 실제 렌더 검사','18그룹 / 5그룹 PASS','evidence/r24/console-r28-final002 및 evidence/r25/visual/r28-final002-*'],
    ['전체 xUnit','2093 실행 / 2027 PASS / 66 기존 FAIL','이름·메시지 기존과 동일, 신규 실패 0'],
    ['실기기·사용자 진행 저장·발열','NOT_RUN','과거 기기 로그나 PC 결과를 새 APK 실기기 PASS로 사용하지 않음']])
page += '<h2>지도 검사 수량과 미해결 원장</h2><p>기존 r26의 지도별·출입구별 원장을 모든 행 그대로 보존하고 r28 안내 메타데이터 원장을 덧붙였습니다. 7948지도·9241표시점 생성 중 지형 캐시는 0지도/0칸 → 0지도/0칸으로 유지되어 전체 지도를 RAM에 선적재하지 않습니다. 지형은 선택한 지도만 작업 스레드에서 읽습니다.</p>'+table(['범위','검사','수정·통과','미해결·한계'],[
    ['기존 전체 지도','7948개 방향 충돌/정적/축소 그림 연결','과거 실제 수정 영향 지도 4개; 외형 재구성 1지도/38칸','전 지도 수동 육안·전체 진행 PASS 아님'],
    ['기존 유효 출입구','10533행 각각 기록·과거 호스트 실행','3333 완전 왕복 및 바깥 이동 PASS','7200 검토·제외: 정상 접근194, 내부/귀환6687, 범위밖44, 진입/동적막힘275'],
    ['r28 길 안내 메타데이터','7948지도 / 9241표시점','전수 생성·캐시 비적재 검사 PASS; 현재 부여 길드/주막 실제 UI 검증','원본 좌표 검토 22건; 전수 runtime 진행은 NOT_RUN'],
    ['스크립트 이동','과거 소스139파일/호출82곳/입구 목적지215건','기존 원장 보존','전체 조건별 왕복 행렬 NOT_RUN']])
page += '<h2>화면</h2>'
for name,caption in [('r28-bag-swipe-stacks.png','가방: 99개 묶음과 페이지 이동'),('r28-buya-mage-map.png','부여 주술사 길드: 실제 원본 지형·입구·경로'),('r28-local-overview.png','현재 지도 전체 보기와 좌표')]:
    raw=(R/'evidence/r28/ui/final002/runtime'/name).read_bytes()
    page+='<figure><img alt="'+esc(caption)+'" src="data:image/png;base64,'+base64.b64encode(raw).decode()+'"><figcaption>'+esc(caption)+' · 최종 PC 실제 Godot 화면</figcaption></figure>'
page += '<h2>누적 성능 및 저장 안전성 보존</h2><p>사용자 지시로 원래 BGM 중심 4단계를 대체했습니다. r26의 방문 지도 지연 적재·변경 없는 몬스터 상태 재수집 억제·화면 잠금 대기 제거를 유지했습니다. r28 가방 정돈은 원래 단일 FULL 도착 트랜잭션에 포함해 별도 월드 수집/저장을 추가하지 않으며, 이미 정돈된 가방은 순서와 인스턴스를 유지합니다. 저장을 끄거나 동기화/원자성을 낮추지 않았습니다. 실제 레벨1/진행 캐릭터의 동일 지도 재실행·플레이·발열 비교는 NOT_RUN이며 호스트 성능 개선으로 대체하지 않습니다.</p>'
page += '<h2>한계와 남은 검토</h2>'+ul(limits)
page += '<h2>실패 재현과 재시험 기록</h2>'+ul(attempts)
page += '<h2>처음 요청한 9개 항목의 보존된 범위</h2><p>아래는 r26에서 이어받은 결과입니다. r28에서 해당 전체 범위를 새로 완료했다고 표시하지 않았습니다.</p>'+table(['번호','항목','이어받은 상태','근거와 남은 범위'],old_issues)
page += '<p><small>활성 상태: verification/r28/STATE.json. 원본 빌드 드라이버 receipt의 kind/stage 일부는 r27 역사 명칭을 유지하지만 실제 build_id r28, versionCode32, 원본 인증서와 최종 APK SHA는 위 값으로 대조되었습니다. 원본 raw receipt는 변경하지 않았습니다. 공개 배포/main 병합/유료 자원 사용 없음.</small></p></html>'
(OUT/'Project1998-r28-report.html').write_text(page)
(REPORT/'Project1998-r28-report.html').write_text(page)

baseline = W/'baseline-input/Project1998-r26-world-ledger.zip'
target = OUT/'Project1998-r28-world-ledger.zip'
with zipfile.ZipFile(baseline) as src, zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
    for info in src.infolist(): dst.writestr(info,src.read(info.filename))
    for name in ['RESULT.json','guide-maps.csv','guide-points.csv','guide-catalog.json']:
        dst.write(R/'evidence/r28/catalog/final001'/name,'r28-guide/'+name)
    for name in ['RECEIPT.json','runtime/ko-checks.json']:
        dst.write(R/'evidence/r28/ui/final002'/name,'r28-guide/final-ui/'+name)
    dst.writestr('r28-guide/SCOPE.txt','r28 metadata:7948 maps;9241 guide points;22 original coordinate REVIEWs. Terrain cache stays0. Full runtime traversal NOT_RUN_THIS_METADATA_PROBE; physical Android NOT_RUN. world-ledger/* entries retain exact r26 bytes and historical execution dates.3333/10533 old scoped host roundtrips PASS;7200 reviews/exclusions remain. No new world-wide PASS. Read the r28 report.\n')
    dst.write(REPORT/'Project1998-r28-results.json','r28-guide/Project1998-r28-results.json')
with zipfile.ZipFile(baseline) as src, zipfile.ZipFile(target) as dst:
    assert dst.testzip() is None
    assert all(src.read(n)==dst.read(n) for n in src.namelist())
ledger={'status':'PASS_ALL_R26_LEDGER_ENTRIES_PRESERVED_PLUS_R28_GUIDE','original_entries':len(src.namelist()),'entries':len(dst.namelist()),'archive':target.name,'bytes':target.stat().st_size,'sha256':sha(target)}
write(R/'evidence/r28/WORLD-LEDGER-ARCHIVE.json',ledger)
state=read('verification/r28/STATE.json')
state.update(step='5_DELIVERY_PACKAGING',status='SIGNED_APK_PASS_PACKAGING',apk_sha256=build['sha256'],apk='Project1998-r28-update-arm64.apk',signed_apk='BUILD_PASS_ORIGINAL_CERT_CODE32',map_catalog=catalog,remaining=['Source/tests archive and file persistence'])
state['initial_regression_notes'][-1]='Initial full xUnit67 failures; final full2093 tests returns66 inherited failures with exact same names/messages. Isolated sweep guard PASS; initial cause not established.'
write(R/'verification/r28/STATE.json',state)
(R/'README-r28.txt').write_text('Project1998 r28. Active single STATE: verification/r28/STATE.json\nNPC parent navigation; swipe bag; identical compatible item stacks99; detailed region/map/NPC/guild guide.\nOriginal r27 source + r25 storage/transaction safety and r26 navigation/performance retained.\nAPK: versionCode32, com.irewon.project1998.g1bv4, original cert and project1998_g1b_v4 save folder.\nFinal PC actual Godot: new28 PASS, preserved item21 PASS, legacy item676 PASS. Safety17+11 PASS. Full xUnit2093/2027 PASS/66 inherited FAIL;0 new. Backup restore6 PASS. Physical Android NOT_RUN.\nAll8056 game-data files unchanged. Full map7948 guide metadata plus22 source-coordinate reviews; original world ledger3333/10533 roundtrips pass,7200 reviews/exclusions retained. No whole-world or whole-performance PASS.\nRead r28-report/Project1998-r28-report.html. Private signing keys, passwords and save databases are excluded.\n')
print(json.dumps({'apk':{'status':build['status'],'sha256':build['sha256']},'report':str(OUT/'Project1998-r28-report.html'),'ledger':ledger},ensure_ascii=False))
