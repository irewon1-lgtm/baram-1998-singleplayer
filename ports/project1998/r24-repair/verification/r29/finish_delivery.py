"""Produce the seven-issue report only from completed, scoped r29 execution receipts."""
import base64,hashlib,html,json
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R.parents[1];OUT=W/'deliverables';REPORT=R/'r29-report'
REPORT.mkdir(exist_ok=True)
def read(p):return json.loads((R/p).read_text())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
build=read('android/evidence/build-r29-001/BUILD_RECEIPT.json');apk=OUT/'Project1998-r29-update-arm64.apk'
assert build['status']=='BUILD_PASS' and sha(apk)==build['sha256']
assert build['version_code']==33 and build['package']=='com.irewon.project1998.g1bv4'
assert build['certificate_sha256']=='ecea13778e2466b3e568f45bfe1facb6fd708bdd0ed3f6ae2a4c305da2ebb030'
suite=read('evidence/r25/suite/r29-final002/RESULT.json');comparison=read('evidence/r29/XUNIT-COMPARISON.json')
assert comparison['status']=='PASS_NO_NEW_FAILURES'
assert all(x['status']=='PASS' for x in suite['results'] if x['name']!='original-xunit')
for p in ['evidence/r24/runtime/r29-continuity-final002/RESULT.json','evidence/r24/runtime/r29-totem-final001/RESULT.json','evidence/r25/visual/r29-emergency-final001/RESULT.json','evidence/r29/ui/final002/RECEIPT.json','evidence/r24/runtime/r29-swap-green001/RESULT.json','evidence/r27/ui/r29-preserved001/RECEIPT.json','evidence/r28/ui/r29-preserved001/RECEIPT.json']:
    assert read(p)['status'].startswith('PASS'),p
source=read('verification/r29/RELEASE-PRODUCTS.json')['source']
assert all(sha(R/p)==digest for p,digest in source.items())
issues=[
    [1,'기술 길게 누르기 정렬','PC 렌더·실제 터치·원래 서버 저장 PASS','약0.5초 길게 누르고 손을 뗀 다음 옮길 기술 위치를 누르면 두 기술의 위치를 교환합니다. 페이지를 바꿔 선택할 수도 있습니다. 원래 pane1 0x30 처리기와 FULL 저장을 사용하므로 캐릭터별 실제 기술 순서가 재실행 후에도 남습니다. 정렬 중에는 시전하지 않습니다.'],
    [2,'채팅 5줄','실제 PC 렌더 PASS','최근50개 메시지를 폭에 맞춰 줄바꿈하고 마지막5줄을 표시합니다. 글꼴·줄 간격·표시 높이를 조정했습니다. 다섯 메시지가 실제로5줄 보이는 것을 확인했습니다.'],
    [3,'가방·장비·기술 탭','실제 PC 렌더·기존 UI 회귀 PASS','두루마리 그림 아래로 옮겼고 테두리·배경·글자색을 양피지 팔레트에 맞췄습니다. 원본 그림을 대체하지 않았습니다.'],
    [4,'지도·말하기·메뉴·문열기·저장·채팅·줍기·공격','실제 PC 렌더 PASS','각 칸에 불투명한 배경과 테두리를 넣고 어두운 글자와 일정한 간격을 적용했습니다. 폰트는 원본 한글 가변 글꼴의 굵기100 대신 HUD에550을 지정했습니다.'],
    [5,'이동 중 글자 깜박임','범위 한정 PC 픽셀 비교 PASS','매 이동의 잠깐 처리중 상태가 버튼 Disabled를 반복 전환하던 경로를 제거했습니다. 동작 제한은 기존 입력/서버 잠금 경로에 유지했습니다. 같은 지형에서 이동좌표·처리중 상태를 반복 적용한 실제 렌더에서 탭·행동 칸 픽셀 변화0건을 확인했습니다.'],
    [6,'무기·방패 장비 칸','실제 플레이 화면 PASS','원래 장비 슬롯1(무기)·3(방패)에 칸을 추가하고 현재 장착품의 원래 아이콘과 이름을 표시합니다. 두 슬롯의 실제 장착 데이터와 대조했으며, 터치하면 기존 장비 보기/해제 경로를 사용합니다.'],
    [7,'장비·기술 글자색과 배치','실제 PC 렌더·플레이 화면 PASS','기술 행의 일반/가리킴/누름 글자색을 일정한 짙은 갈색으로 맞췄습니다. 장비·기술 상세 창도 양피지 배경과 어두운 글자로 맞췄습니다. 위치 안내를 한 줄로 정리해 상태창과 겹치지 않게 했습니다.']
]
limitations=[
    '실제 Android 설치·SM-X526N GPU 화면·물리 터치·발열·실제 사용자 진행 캐릭터 비교는 NOT_RUN입니다. PC 화면과 합성 저장 결과를 실기기 PASS로 쓰지 않았습니다.',
    '전체 xUnit 결과는2093 실행/2027 PASS/66 FAIL입니다. 기존 r28의66개 실패와 이름·메시지가 동일하며 신규 실패0개입니다. 모든 시험 또는 게임 전체가 PASS인 것은 아닙니다. 실패별 원문은 evidence/r29/XUNIT-COMPARISON.json에 있습니다.',
    '원래 세계의7948지도·10533출입구 원장과3333행 완전 왕복/7200행 검토·제외, r28 안내 좌표22건 검토는 그대로 남습니다. 이번 일곱 UI 항목 보수가 이전 세계 검토를 모두 해결했다는 뜻은 아닙니다.',
    '기술 정렬은 두 개의 배운 기술 위치를 교환합니다. 기술을 새로 주거나 빈 슬롯을 만들지 않습니다. 지도/기술 목록 변경·대화·메뉴·취소·포커스 상실은 선택을 끝내며, 서버도 이전 지도와 기술 이름을 다시 검증합니다.',
    '현재 채팅 창은 최신5줄을 보여줍니다. 새로 과거 대화 스크롤 기능을 추가한 작업은 아닙니다. 원래 입력 문자 규칙은 유지했습니다.'
]
history=[
    '수정 전 실제 PC UI red002:11 FAIL/2 기존 동작 PASS. 길게 눌러도 cast가 나갔고 최근 채팅1개만 표시했으며, 무기/방패 칸과 구획이 없었습니다. red001의 화면 너비/뷰포트 불일치는 시험 오류로 별도 보존했습니다.',
    '서버 경로 red001은 시험 using 누락으로 컴파일 실패(NOT_RUN). red002는 터치 경계에 원래 정렬 API가 없음을 FAIL로 확인했습니다. 최종 원래 처리기·재실행·강제 SQLite 쓰기 실패 복구10개를 통과했습니다.',
    'green001에서 실제 채팅 가시 줄이4개이고 탭의 계산된 최소 높이가 커지는 문제를 발견했습니다. 채팅 높이와 부모 편입 후 크기를 고쳤습니다. 이동 안정성 시험은 원래 비활성인 페이지 경계를 기준 상태로 보존하도록 시험 자체를 바로잡았습니다.',
    'green002에서14개 화면 검사가 통과했고 final001은 실제 고정 영역 픽셀 비교를 더해15개가 통과했습니다. 실제 플레이 touch→Main→원래0x30→FULL 저장→재실행10개도 통과했습니다.'
]
recovery=read('evidence/r24/runtime/r29-recovery-green003/RESULT.json')
assert recovery['status'].startswith('PASS') and len(recovery['checks'])==17 and all(c['status']=='PASS' for c in recovery['checks'])
mapcheck=read('evidence/r24/runtime/r29-map1014-final001/RESULT.json')
assert mapcheck['processed']==10 and mapcheck['totals']=={'PASS_SCOPED_HOST_COMPLETE_ROUNDTRIP_WITH_OUTSIDE_MOVE':10}
incident=read('evidence/r29/EMERGENCY-DIAGNOSIS.json')
limitations.insert(0,'제공된 JSON은 진단 파일이며 실제 전체 저장 DB는 없습니다. 사용자 기기의 totogo 복구 적용은 NOT_RUN입니다. APK 업데이트 후 totogo 이어하기에서 기존 저장의 지도1014 (0,17), 레벨17 조건이 맞으면 전체 백업을 먼저 만들고 위치만 부여330 (29,143)으로 복구합니다. 레벨·경험치·돈·장비·기술·가방·퀘스트와 월드/런타임 보존은 별도 시험 저장으로 검증했습니다.')
history.extend(['지도1014의 실제 원래 이동에서 남쪽 울타리를 아래로 통과한 후 (0,17)과(1,17)에 갇히는 현상을 재현했습니다. 원래 그림의 울타리 두 칸 Pass0→3만 재구성 보수했으며 문이나 정상 길을 삭제하지 않았습니다.', '복구 red002는 갇힘 및 복구 경로 미구현을 FAIL로 기록했습니다. green001의 합성 미래 스키마 거부를 확인한 후, 지원하지 않는 스키마는 쓰기 전에 거절하도록 보수했습니다. 최종 green003의 자동 로그인/백업 복원/위치 외 원문 보존/실패 시 보존17개와 지도1014 출입구10개 전 과정을 통과했습니다.', '전체 회귀 첫 실행에서 장비 오른손 빈 칸의 한글 잘림을 발견했습니다. 기존 투구/반지는 원본 그림의 칸 이름을 사용하고 새 무기/방패 칸만 별도 이름을 표시하도록 고쳤습니다. final002 전체 실제 UI 재실행을 최종 근거로 사용합니다.'])
preserved=read('evidence/r29/PRESERVATION.json')
result={'schema':'P1998_R29_SEVEN_HUD_REPAIRS_1','generated_utc':datetime.now(timezone.utc).isoformat(),'status':'SIGNED_UPDATE_READY_WITH_INHERITED_FAILURES_AND_DEVICE_NOT_RUN','build':build,'issues':issues,'limitations':limitations,'attempt_history':history,'suite':suite,'xunit':{'executed':comparison['current']['executed'],'passed':comparison['current']['passed'],'inherited_failures':comparison['current']['failed'],'new_failure_names':comparison['new_failure_names'],'changed_failure_messages':comparison['changed_failure_messages']},'emergency':{'diagnosis':incident,'recovery_checks':recovery,'map1014_connections':mapcheck,'actual_user_save_applied':'NOT_RUN'},'related_failure_rechecks':{'stable_floor_creature_and_timers':read('evidence/r24/runtime/r29-continuity-final002/RESULT.json'),'current_named_totem_menu_and_reopen':read('evidence/r24/runtime/r29-totem-final001/RESULT.json'),'original_xunit_status':'ALL66_STILL_FAIL; no unsafe numeric-owner restoration or old-menu-index workaround'},'new_checks':{'position_backup_and_automatic_login':17,'map1014_roundtrips':10,'hud_render_and_input':15,'actual_play_touch_and_reopen':10,'original_swap_save_and_rollback':10},'preserved_ui':{'r27_items':21,'r28_npc_bag_map':28,'legacy_items':676},'preservation':preserved,'world_ledger':read('evidence/r29/WORLD-LEDGER.json'),'physical_android':'NOT_RUN','user_save_writes':0,'nine_issues_inherited_with_explicit_r29_addendum':read('r26-report/Project1998-r26-results.json')['nine_issues'],'runtime_checkpoint':'3419afdb665fd06f173281076448e18d93b471c0'}
write(REPORT/'Project1998-r29-results.json',result)
e=lambda x:html.escape(str(x))
def table(headers,rows):return '<table><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def ul(xs):return '<ul>'+''.join('<li>'+e(x)+'</li>' for x in xs)+'</ul>'
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 r29 UI 보수 결과</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1120px;margin:32px auto;padding:0 20px;background:#f5f4ef;color:#30291f}h1,h2{line-height:1.25}table{width:100%;border-collapse:collapse;margin:20px 0;background:#fff}td,th{padding:12px;border:1px solid #d0c2aa;text-align:left;vertical-align:top}th{background:#e9ddc6}.notice{padding:16px;background:#fff0c5;border-left:5px solid #a97a22}img{display:block;max-width:100%;height:auto}figure{margin:24px 0;background:white;padding:12px}li{margin:10px 0}small{overflow-wrap:anywhere}</style><h1>Project1998 r29 · 긴급 위치 복구와 일곱 가지 UI 보수</h1><p>r28 최종 소스에서 이어서 기술 정렬·채팅·버튼·장비 표시를 수정했습니다. 기존 패키지·인증서·저장 폴더 및 r25 거래/저장 안전성을 유지했습니다. 게임 데이터8056파일 중8055개를 그대로 보존하고 MapCells.csv의 지도1014 울타리 두 칸 충돌만 수정했습니다.</p><p class="notice">기존 서명의 ARM64 업데이트 APK이며 totogo 자동 위치 복구가 포함되어 있습니다. 실제 Android 설치·물리 기기 검증은 NOT_RUN이며, 기존66개 회귀 실패와 전체 지도 미해결 검토는 남아 있습니다.</p>'''
page+='<h2>totogo 긴급 복구</h2><p class="notice">기존 앱 위에 업데이트 설치한 뒤 totogo 이어하기를 실행하세요. 실제 기기 저장의 지도1014 (0,17), 레벨17 조건이 맞을 때에만 자동 복구합니다. 백업이 실패하면 위치를 쓰지 않고 진입을 멈춥니다. 기존 앱 삭제나 새 캐릭터 생성은 필요 없습니다. 이 환경에서 사용자의 실제 DB를 수정한 것은 아니며 기기 적용은 NOT_RUN입니다.</p>'
page+=table(['대상','처리'],[['진단','P1998-G6-result-20261022-205340.json 전체 분석; 현재1014 (0,17), 레벨17, 경험치47186, 돈61'],['복구 위치','부여성330 (29,143)'],['순서','정상 인증 → SQLite 전체 백업/무결성 확인/파일 flush → 위치5필드만 바이트 수정 → 기존 FULL 트랜잭션 → 원문·리비전 대조 → 정상 진입'],['보존','위치 외 캐릭터 원문, 월드/런타임 tuple, 다른 캐릭터 동일. 원래 저장 전용 잠금·CAS·watermark 유지.'],['백업 위치','기존 앱 데이터 폴더/backups/totogo-before-position-recovery-날짜-식별자.zip'],['재발 방지','지도1014 남쪽의 보이는 울타리(0,16),(1,16) Pass0→3 재구성. 원래 그림/지도ID/출입구/조건 유지.'],['검사','별도 저장의17개 복구 검사 PASS; 연결10개 일반길→입장→내부→귀환→바깥 이동 PASS. 실제 사용자 기기 적용 NOT_RUN.']])
page+='<h2>일곱 항목의 결과</h2>'+table(['번호','문제','실행 결과','수정된 동작'],issues)
page+='<h2>기술 정렬 사용법</h2><p>기술 탭에서 바꿀 기술을 약0.5초 꾹 누르고 손을 뗍니다. 선택 표시와 ‘옮길 위치 선택’ 안내가 나오면 목적 기술을 누릅니다. 다른 페이지도 선택할 수 있습니다. 두 기술이 교환되고 원래 저장 트랜잭션에 반영됩니다. 바깥/다른 탭/메뉴를 누르면 취소합니다.</p>'
page+='<h2>설치 파일 대조</h2>'+table(['검사','결과'],[['파일',apk.name],['SHA-256',build['sha256']],['크기',f'{apk.stat().st_size:,} bytes'],['패키지',build['package']],['버전',f"{build['version_name']} / code33"],['인증서',build['certificate_sha256']],['저장 경로','user:// → project1998_g1b_v4'],['원본 데이터','8056파일 중8055개 동일; MapCells.csv 울타리2칸 / '+build['content_archive_sha256']],['APK 검사','실제 Godot export·기존 키 서명·16K 정렬·project.binary·ARM64·테스트 fixture 미포함 PASS'],['소스 일치',str(build['source_input_count'])+'개 APK 고정 입력을 source ZIP 내부 파일과 해시 대조']])
page+='<h2>실행한 검사</h2>'+table(['검사','관측 결과','원본 근거'],[['새 HUD 렌더·터치·픽셀 비교','15 PASS','evidence/r25/visual/r29-emergency-final001'],['실제 플레이 터치·교환·취소·재실행','10 PASS','evidence/r29/ui/final002'],['원래 서버 교환·FULL 저장·강제 쓰기 실패 복구','10 PASS','evidence/r24/runtime/r29-swap-green001'],['r27 단일 탭 정보·더블 탭 사용','21 PASS','evidence/r27/ui/r29-preserved001'],['r28 NPC 복귀·가방99·스와이프·지도','28 PASS','evidence/r28/ui/r29-preserved001'],['기존 아이템/NPC/상점/퀘스트 실제 UI','676 PASS','evidence/r25/items-ui/r29-final002'],['전체 xUnit','2093 실행 /2027 PASS /66 기존 FAIL','신규/메시지 변경0; XUNIT-COMPARISON.json'],['기존 콘솔 / 실제 렌더','18그룹 /5그룹 PASS','console-r29-final002 / visual/r29-final002-*'],['저장 거래·상점·크래시·백업 복원','21/10/2/6 PASS','final-runtime 및 crash/r29-final002'],['실기기·사용자 진행 저장·발열','NOT_RUN','합성 캐릭터·실제 PC Godot 결과와 구분']])
page+='<h2>저장·진행 관련 기존 실패의 재확인</h2><p>바닥 아이템의 기존2개 실패는 안정된 계정 식별자 없이 숫자 소유자1을 복원하려는 시험과 관련됩니다. 숫자 ID의 다른 캐릭터 재사용을 허용하지 않았습니다. 이번 소스에서 실제 안정 계정으로 소유권 재결합·아이템 전체 필드·몬스터 피해/소유권/독/받은 물건·정지/활성 시간6개를 재검사했습니다. 토템의 기존 실패는 로그아웃 전에 옛 대화 순번에서 발생하며, 현재 이름으로 메뉴 선택→정확한 공물 지불→퀘스트/토템 저장 재실행3개를 검사했습니다. 별도 검사가 통과해도 원래66개 FAIL은 FAIL로 유지합니다. 별도 옛 방4164 DB fixture가 필요한 검사는 NOT_RUN으로 남겼습니다.</p>'
page+='<h2>최종 실행 화면</h2>'
for path,caption in [('evidence/r29/sonhi-valley-original.png','원래 지도1014 지형: 남쪽 울타리 뒤 갇힘 구역을 원본 그림과 대조'),('evidence/r29/ui/final002/runtime/r29-actual-equipment.png','실제 플레이: 원래 장착품의 무기·방패 슬롯과 버튼 배치'),('evidence/r29/ui/final002/runtime/r29-actual-skills-page2.png','실제 터치로 다른 페이지의 기술 위치를 교환'),('evidence/r25/visual/r29-emergency-final001/r29-equipment-chat.png','PC 렌더: 채팅5줄과 구획·장비 칸'),('evidence/r25/visual/r29-emergency-final001/r29-spell-selected.png','길게 누른 기술 선택 표시와 옮길 위치 안내')]:
    page+='<figure><img alt="'+e(caption)+'" src="data:image/png;base64,'+base64.b64encode((R/path).read_bytes()).decode()+'"><figcaption>'+e(caption)+'</figcaption></figure>'
page+='<h2>보존과 미해결 범위</h2>'+ul(limitations)+'<h2>재현·실패·재시험 기록</h2>'+ul(history)
page+='<h2>원래 아홉 항목의 이어받은 범위</h2><p>이번 보수에서 아래 과거 검토를 새 전체 PASS로 바꾸지 않았습니다. 지도1014 관련10개 경로의 새 재검사와 울타리2칸 보수는 r29 원장 추가 기록에 있습니다. r28에서 전달한 전체 지도·출입구 원장은 그대로 유효한 과거 범위의 기록으로 유지합니다. 누적 성능의 실기기 비교도 NOT_RUN입니다.</p>'+table(['번호','항목','이전 상태','근거와 미해결'],read('r26-report/Project1998-r26-results.json')['nine_issues'])
page+='<p><small>활성 STATE: verification/r29/STATE.json. 사용자 저장 쓰기0. 새 키 생성/기존 앱 삭제/main 병합/공개 배포/유료 자원 사용 없음. 전체 실패별 원문과 raw 실행 결과는 소스·시험 ZIP에 있습니다.</small></p></html>'
(REPORT/'Project1998-r29-report.html').write_text(page);(OUT/'Project1998-r29-report.html').write_text(page)
(R/'README-r29.txt').write_text('Project1998 r29 complete source/tests. Active STATE: verification/r29/STATE.json\nSeven HUD repairs from latest delivered r28; original certificate/package/save folder retained.\nHold a spell0.5s, release, tap another occupied spell position to swap. Other pages supported. Original0x30 and FULL save, no new spellbook storage.\nNew checks: position recovery17, map1014 complete road/interior/return routes10, HUD15, actual gameplay10, original handler/save/rollback10 PASS. Emergency on-device totogo migration runs before normal arrival only at map1014 (0,17), level17; backup first, five position fields only. Actual user-save application NOT_RUN; diagnostic is not a full database. Preserved r27 item21, r28 usability28, legacy item676 PASS. Full xUnit2093/2027 PASS/66 unchanged FAIL. Physical Android NOT_RUN. 8055/8056 game-data files unchanged. MapCells.csv only adds two visible-fence collision overrides on map1014. Old map reviews and progressed-character thermal tests remain explicitly unresolved/NOT_RUN.\nRead r29-report/Project1998-r29-report.html. Keys, passwords and save databases excluded.\n')
s=read('verification/r29/STATE.json');s['emergency']['user_device_recovery']='NOT_RUN';s.update(step='4_DELIVERY_PACKAGING',status='SIGNED_APK_AND_FINAL_REGRESSION_QUALIFIED_WITH_EXPLICIT_SCOPE',apk_sha256=build['sha256'],full_xunit=result['xunit'],remaining=['Source/tests ZIP and final file persistence']);write(R/'verification/r29/STATE.json',s)
print(json.dumps({'apk_status':build['status'],'apk_sha256':build['sha256'],'report':str(OUT/'Project1998-r29-report.html')},ensure_ascii=False))
