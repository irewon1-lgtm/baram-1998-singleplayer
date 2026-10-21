"""Assemble the final Korean evidence report from executed receipts, never inferred PASS."""
import base64,datetime,hashlib,html,json,sqlite3
from pathlib import Path
R=Path(__file__).resolve().parents[2];OUT=R.parents[1]/'deliverables'
def read(path):return json.loads((R/path).read_text())
def esc(value):return html.escape(str(value))
def table(headers,rows):return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>'for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>'for v in row)+'</tr>'for row in rows)+'</tbody></table>'
receipt=read('android/evidence/build-r26-003/BUILD_RECEIPT.json');assert receipt['status']=='BUILD_PASS'and receipt['version_code']==30
apk=Path(receipt['apk']);assert hashlib.sha256(apk.read_bytes()).hexdigest()==receipt['sha256']
suite=read('evidence/r25/suite/r26-final002/RESULT.json');xunit=read('evidence/r26/XUNIT-COMPARISON.json')
assert xunit['current_failed']==66 and not xunit['new_failure_names']and not xunit['changed_failure_messages']
world=json.loads((OUT/'world-ledger/SUMMARY.json').read_text());pair=read('evidence/r26/growth-pair/abba001/RESULT.json')
continuity=read('evidence/r24/runtime/continuity-final003/RESULT.json');assert continuity['status']=='PASS'
compat=read('evidence/r24/runtime/reader-r25-final001/RESULT.json');assert compat['status']=='PASS'
preserved=read('evidence/r26/CONTENT-PRESERVATION.json')
issues=[
 [1,'끊김·입력 반응','부분 수정·호스트 재현 PASS','화면의 Session 잠금 대기를 제거. 진행 월드 저장의 중복 JSON 생성·변경 없는 몬스터 직렬화를 줄임. 실기기 FPS·발열은 NOT_RUN.'],
 [2,'보이는 입구의 입장','부분 검사·수정','부여330 Kan 상점 외형 재구성과 실제 입력 왕복 PASS. 모든 보이는 건물/동굴의 외형과 문 의미가 일치한다는 검수는 미완료.'],
 [3,'빈 땅 상점 입구','수정·실제 PC UI PASS','330 (110,133)/(111,133) →331 좌표 유지. 원본 동도시 대장간 그림을 이용한38칸 재구성. 정확한 과거 Kan 외형 복구라고 주장하지 않음.'],
 [4,'한 번 터치 자동이동','구현·범위 한정 PASS','기존 Turn/Step 처리기와 방향 비용 A* 사용. 독립 Dijkstra 비교200개 격자 및 실제 Godot 한 번 탭·최신 목적지·메뉴 취소·지도 전환·출구 후 이동 검사. 모든 기기 제스처 조합은 NOT_RUN.'],
 [5,'전체 지도 전수조사','원장·전수 구조/행 검사 완료','등록7948지도, 유효 출입구10533행 모두 개별 기록·실행. 축소 그림1325종을 재사용해7948 ID에 연결. 이는 전체 수동 육안 검수/게임 진행 PASS가 아님.'],
 [6,'보이지 않는 벽','전수 정적 검사·미해결 검토 존재','방향 충돌·문·도착 좌표·NPC·조건 자료를 원장에 결합. 입구 외형38칸 외 정상 벽/입장 조건은 해제하지 않음. 전 지형의 시각적 벽 판정은 미완료.'],
 [7,'쥐·박쥐굴 탈출/옆 문','공통 입력 보수·부분 확인','원래0x15마다 지도 세대를 갱신해 전환 전 대기 입력과 자동이동을 폐기. 부여6층 왕복 호스트 시험은 통과한 기록이 있으나 구릉 쪽은 동적 몬스터 막힘이 남음. 사용자의 현재 던전은1002로 단정하지 않음.'],
 [8,'다른 던전 입장·층·귀환','부분 PASS·검토 남음',f"최종 원래 처리기 왕복+바깥 이동 {world['host_complete_roundtrips']}/10533행 PASS. 나머지{world['host_reviews_or_exclusions']}행은 조건/경로/동적 막힘/범위 밖 원본 행 검토.3개 원본 보스 방의 범위 밖 좌표 방어 및 정확한 r25 손상 좌표 복구 추가."],
 [9,'BGM 성능 비교','사용자 지시로4단계에서 제외','지시 변경 전에 추가했던 BGM 별도 설정은 유지. 변경 뒤 BGM 비교 작업을 진행하지 않음. 기존 PC 결과는 Android MIDI·발열 개선 근거가 아님. 원본 음악 삭제0.']]
replacement=[
 ['1','동일 지도 신규/진행 비교','합성 범위 PASS / 실제 기존 캐릭터 NOT_RUN','330 같은 시작 좌표에서 Lv1·Lv70와 추가 물체화 지도0/32/128 비교. 실제 사용자 진행 저장은 제공된 자료에 없음.'],
 ['2','캐시·몬스터·월드·저장·RAM·CPU·GC·입력 계측','호스트 측정 PASS','모든 수치의 원본 JSON 제공. 앱은5초 간격 최대128개 샘플과 계속되는 프레임·행동 계측을 내보냄. CPU/RAM API 실패 시 실패 원인 기록.'],
 ['3','매 행동 반복 수집·직렬화·저장','보수·보존 검사 PASS','전체 JSON DOM 재구성과 불변 몬스터의 재직렬화를 제거.73개 단순 멤버를 정확히 비교하고 가변 목록/사전은 원래 직렬화 경로 사용. 재사용4096마리 상한. 매 행동의 전체 SQLite 원자 커밋/FULL/리비전 검사는 유지. 전체 월드 문자열과 DB 기록 비용 자체는 남음.'],
 ['4','변경 없는 방문 지도 복구 적재','보수·검사 PASS','빈 이력128개는 지형을0개 적재. 변경 칸이 있는 지도만 원래 기준 위에 복구. 방문 이력·치수·경계 검증은 유지. 월드의 실제 몬스터 복구를 생략하거나 삭제하지 않음.'],
 ['5','저장·몬스터·퀘스트·아이템 보존','실행 범위 PASS','강제 종료 전/후 원자성, 백업 복구, 원래 r25 리더의 새 월드 필드 동등성, 바닥 아이템 소유/예약·몬스터 HP·소지품·신앙 퀘스트 재로그인 검사. 사용자 실제 저장 쓰기0.'],
 ['6','실기기 재실행·진행·발열 비교','BLOCKED / NOT_RUN','adb 연결 기기0. 이전 기기 로그나 호스트 수치를 새 APK 실기기 PASS로 사용하지 않음. 실제 기존 캐릭터/기기 열화 원인의 전부를 규명했다고 주장하지 않음.']]
measure=[]
for tag,label in [('before002','수정 전'),('after003','수정 후')]:
 for case in ['history0-level1','history0-level70','history32-level70','history128-level70']:
  path=R/'evidence/r26/growth'/tag/case/'RESULT.json'
  if not path.exists():measure.append([label,case,'복구 실패','NOT_RUN','NOT_RUN','NOT_RUN','NOT_RUN']);continue
  d=json.loads(path.read_text());measure.append([label,case,round(d['cold_open_ms'],1),round(d['input']['p95_ms'],2),round(d['input']['allocated_per_action']/1e6,2),d['world']['retained_monsters'],round(d['coldMemory']['rss_bytes']/1048576,1)])
performance_rows=[[x['order']+1,x['kind'],round(x['cold_ms'],1),round(x['p95_ms'],2),round(x['median_ms'],2),round(x['cpu_ms'],1),round(x['allocation_per_action']/1e6,2)]for x in pair['rows']]
counts={k:world[k]for k in ['registered_maps','raw_warp_rows','effective_warps_including_invalid_source','host_warp_rows_exercised','host_complete_roundtrips','host_reviews_or_exclusions','maps_with_all_outgoing_host_roundtrips','human_whole_map_review','facade_modified_maps','facade_authored_cells','specific_maps_affected_by_repairs','spawn_origin_protection_maps','scripted_entrance_destination_cases','scripted_unique_source_tiles','maps_with_remaining_table_warp_reviews']}
summary={'status':'PARTIAL_NOT_WHOLE_TASK_COMPLETE','apk':receipt,'nine_issues':issues,'replacement_stage4':replacement,
 'world_coverage':counts,'xunit':{k:v for k,v in xunit.items()if k!='failures'},'full_suite':suite,
 'physical_android':'NOT_RUN','physical_blocker':'NO_CONNECTED_ADB_DEVICE','actual_user_progress_save':'NOT_AVAILABLE',
 'new_critical_save_defects_detected_in_executed_tests':0,'unknown_or_unexecuted_scopes_are_not_pass':True,
 'source_data_preservation':preserved,'performance_abba':pair,'first_apk_code29':'SUPERSEDED_BY_FINAL_CODE30'}
(OUT/'Project1998-r26-results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
text='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Project1998 r26 실행 결과</title><style>body{max-width:1200px;margin:32px auto;padding:0 20px;color:#202830;background:#f6f8fa;font:16px/1.65 system-ui}h1{font-size:30px}table{border-collapse:collapse;width:100%;margin:20px 0;background:white}th,td{border:1px solid #c7cfd8;padding:10px;vertical-align:top;text-align:left}th{background:#e6edf3}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e8edf2;padding:16px;font-size:13px}img{max-width:100%;height:auto}strong{color:#163d59}.notice{background:#fff2d5;padding:18px;border-left:5px solid #bb7a00}code{overflow-wrap:anywhere}</style><h1>Project1998 r26 — 실제 수정·검사·업데이트 APK</h1>'''
text+='<p class="notice"><strong>기존 서명·패키지의 versionCode30 업데이트 설치 후보입니다. 전체9개 문제 해결 완료 또는 새 APK 실기기 검증 완료가 아닙니다.</strong> 미실행 범위와 지도별 검토를 아래에 분리했습니다. 기존 앱/저장을 삭제하는 방식은 사용하지 않았습니다.</p>'
text+='<p>요청 변경에 따라4단계를 <strong>심각한 누적 성능 저하 우선 보수</strong>로 교체했습니다. 같은 지도에서 레벨 숫자만 바꾸는 경우보다, 저장된 방문·물체화 지도와 몬스터가 증가할 때 비용이 크게 증가했습니다. 발열이나 BGM만으로 원인을 단정하지 않았습니다.</p>'
text+=table(['산출물','확인'],[['최종 APK',apk.name],['APK SHA256',receipt['sha256']],['기존 서명 SHA256',receipt['certificate_sha256']],['패키지',receipt['package']],['업데이트 버전',f"{receipt['version_name']} / code30 (r25 code28, 1차 code29)"],['기존 논리 저장 폴더','project1998_g1b_v4 / 동일 user:// 설정'],['빌드 검증','엄격 소스 동결·내장8056파일/바이너리·기존 서명·정렬·arm64·실행 리소스 확인'],['실기기 설치·발열','NOT_RUN — 연결 Android 기기 없음']])
text+='<p><strong>9개 항목의 결과</strong></p>'+table(['번호','항목','결과','실행 범위와 남은 일'],issues)
text+='<p><strong>교체된4단계의6개 지시</strong></p>'+table(['번호','요구','결과','근거와 한계'],replacement)
text+='<p><strong>동일 지도 호스트 비교</strong> — 각 측정은 새 OS 프로세스, 같은 부여330 좌표, 같은 입력160개와 원래 틱20회, 실제 SQLite 커밋입니다. 레벨·이력은 명시적으로 만든 합성 캐릭터입니다. history128은 추가 물체화 지도128개와 별도의 빈 방문 이력을 포함하며, 기존 사용자 캐릭터라고 표시하지 않았습니다.</p>'
text+=table(['구분','합성 사례','재실행 초기화 ms','입력 p95 ms','할당 MB/행동','보존 몬스터','초기 RSS MiB'],measure)
text+='<p>history32의 수정 전 실패는 원본 Monkey avenger의 방4164 출현 좌표(24,32)가20×30 지형 밖이어서 발생했습니다. 정확한 원본 출현 방 서명에만 좌표 복구를 적용했고1,309마리 및 나머지 상태 필드가 보존됨을 비교했습니다. 알 수 없는 잘못된 좌표는 계속 거부합니다.</p>'
text+='<p><strong>동일 저장의 순서 교차 재검사</strong> — 전→후→후→전. 원본 DB/WAL/SHM 바이트는 변경하지 않고 각 회차 복사본을 사용했습니다. p95는327–417ms에서43–76ms, 행동당 할당은약59.1MB에서18.8MB로 감소했습니다. 원래 커밋 횟수나 내구성은 줄이지 않았습니다. 이 수치는 Android FPS·온도 개선의 실측값이 아닙니다.</p>'
text+=table(['순서','바이너리','초기화 ms','p95 ms','중앙값 ms','160행동 CPU ms','MB/행동'],performance_rows)
text+='<p><strong>전체 지도/출입구 검사와 미해결</strong></p>'+table(['분류','수'],list(counts.items()))
text+=table(['최종 원래 처리기 실행 상태','테이블 워프 행'],list(world['host_status_counts'].items()))
text+='<p>테이블 워프와 별도로 조건부 스크립트 문 '+str(world['scripted_unique_source_tiles'])+'개 출발 칸과 '+str(world['scripted_entrance_destination_cases'])+'개 목적지/계층 후보를 기록했습니다. Mythic·Event·직업/성향 방·Arena·Forever Tree 및 모든 C#·Lua 이동 호출 위치와 월드맵/게이트웨이 설정도 별도 원장에 포함합니다. 이 별도 스크립트 문 전체의 조건별 왕복 실행은 NOT_RUN이며, 10,533행 워프 시험의 PASS 수에 섞지 않았습니다.</p>'
text+='<p>7,200행을 모두 결함으로 세지 않았습니다. 직접 역방향 문이 없는 경로, 원래 조건 거부, 동적 몬스터 막힘, 일반 길 접근을 만들지 못한 행, 원본 범위 밖 좌표 등이 함께 포함됩니다. 전체 원장은 각 행의 목적지·조건·실제 실행 상태·미해결 이유를 보존합니다. 모든 조건의 부정/경계값 조합, 사용자 저장의 문 상태, 전체 수동 시각 검수는 NOT_RUN입니다. 축소 그림 생성만으로 통과 처리하지 않았습니다.</p>'
text+='<p><strong>저장·회귀</strong> — 원래 xUnit2,065개 중1,999개 통과,66개 실패. r25 기준과 실패 이름/메시지가 정확히 같고 새 실패0입니다. 따라서 전체 회귀 PASS로 재표시하지 않았습니다. 거래/취소/SQLite 실패 주입, 실제 프로세스 강제 종료 전후,18개 콘솔 회귀 묶음,676개 실제 아이템 UI 검사,백업 복구6검사는 통과했습니다. 이동·저장 관련 기존 실패도 조사했습니다.</p>'
text+=table(['관련 기존 실패','추가 조사'],list(xunit['related_failure_investigation'].items()))
text+='<p>86개 직렬화/게으른 지형 복구 검사,12개 아이템·몬스터·기존 방 좌표 연속성 검사,3개 현재 신앙 메뉴/정상 재로그인 검사도 통과했습니다. 새 월드 스냅샷을 원래 r25 DLL로 복구했을 때130개 물체화 지도와4,134마리 및 전체 월드 필드가 동등했습니다. 실제 사용자 저장에 쓰기는0회였습니다.</p>'
text+='<p><strong>원본 보존과 재구성</strong> — 원본 데이터8,056파일 중 변경은 MapCells.csv1개, 추가/삭제0개. 원래.map7,956파일, 아이템·NPC·퀘스트·워프 테이블을 유지했습니다. 부여 Kan 외형의38칸은 보존된 같은 도시 대장간 미술을 이용한 재구성입니다. 원본 누락 외형을 복원했다고 보고하지 않습니다. 지도 치수나 정상 벽·조건을 전부 풀지 않았고, 콘텐츠 수량을 늘리지 않았습니다.</p>'
image=R/'evidence/r26/ui/input008/runtime/r26-shop-outside.png'
text+='<p>최종 소스의 실제 Godot 상점 출입 후 화면:</p><img alt="최종 실제 상점 출입 후 화면" src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'">'
text+='<p><strong>재현과 인계</strong> — 전체 소스·시험 ZIP의 verification/r26/STATE.json이 단일 현재 상태입니다. README-r26.txt, 교체된 CONTRACT.md, 단계별 커밋 패치와 실행 JSON을 함께 제공했습니다. 지도 검사기는 개발용으로 분리했으며 앱 시작 시 전 지도를 검사하지 않습니다. 수정 중의 컴파일/시험 하네스 실패도 지우지 않고 원인과 재시험 기록을 남겼습니다. main 병합·공개 배포·새 서명키 생성은 하지 않았습니다.</p>'
text+='<details><summary>정확한 최종 범위 JSON</summary><pre>'+esc(json.dumps({k:v for k,v in summary.items()if k not in ['apk','nine_issues','replacement_stage4','full_suite','source_data_preservation']},ensure_ascii=False,indent=2))+'</pre></details></html>'
(OUT/'Project1998-r26-report.html').write_text(text)
print(json.dumps({'report':str(OUT/'Project1998-r26-report.html'),'status':summary['status'],'apk_sha256':receipt['sha256'],'world':counts},ensure_ascii=False))
