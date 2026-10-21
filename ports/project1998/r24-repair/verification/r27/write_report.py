import base64,hashlib,html,json
from pathlib import Path

r=Path(__file__).resolve().parents[2];out=r.parents[1]/'deliverables';copy=r/'r27-report';copy.mkdir(exist_ok=True)
load=lambda p:json.loads((r/p).read_text())
build=load('android/evidence/build-r27-001/BUILD_RECEIPT.json')
ui=load('evidence/r27/ui/final002/runtime/ko-checks.json')
suite=load('evidence/r25/suite/r27-final001/RESULT.json')
comparison=load('evidence/r27/XUNIT-COMPARISON.json')
legacy=load('evidence/r25/items-ui/r27-final001/RECEIPT.json')
preservation=load('evidence/r27/R26-PRESERVATION.json')
assert build['status']=='BUILD_PASS' and ui['status'].startswith('PASS') and legacy['status'].startswith('PASS')
assert comparison['status']=='PASS_NO_NEW_FAILURES' and all(row['status']=='PASS' for row in suite['results'] if row['name']!='original-xunit')
assert not preservation['changed_content']
apk=out/'Project1998-r27-items-update-arm64.apk';assert hashlib.sha256(apk.read_bytes()).hexdigest()==build['sha256']
result={'schema':'P1998_R27_ITEM_FIX_1','status':'PASS_SCOPED_ITEM_FIXES_WITH_INHERITED_FAILURES',
    'apk':build,'ui':ui,'legacy_item_ui':{'checks':legacy['check_count'],'status':legacy['status'],'other_characters_unchanged':legacy['other_characters_unchanged']},
    'xunit':comparison,'full_regression':suite,'r26_preservation':preservation,'physical_android':'NOT_RUN_NO_CONNECTED_DEVICE',
    'actual_user_progress_save':'NOT_AVAILABLE; only isolated synthetic profiles used','user_save_writes':0,
    'previous_r26_world_reviews':'Retained; not solved or relabelled by this inventory update'}
for p in [out/'Project1998-r27-results.json',copy/'Project1998-r27-results.json']:p.write_text(json.dumps(result,ensure_ascii=False,indent=2))
escape=html.escape
rows=''.join('<tr><td>'+escape(x['name'])+'</td><td>'+escape(x['status'])+'</td><td>'+escape(x.get('observed_status')or'원시 실행 기록 확인')+'</td></tr>' for x in suite['results'])
checks=''.join('<li>'+escape(x['name'])+' — '+x['status']+'</li>' for x in ui['checks'])
failed='\n\n'.join(name+'\n'+message for name,message in comparison['current']['failures'].items())
image=base64.b64encode((r/'evidence/r27/ui/final002/runtime/r27-single-inspection.png').read_bytes()).decode()
report=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Project1998 r27 — 가방 정보·더블 터치</title><style>body{{font-family:system-ui,sans-serif;background:#171613;color:#eee4cf;margin:0;line-height:1.65}}main{{max-width:1000px;margin:auto;padding:24px}}h1,h2{{color:#efc57d}}table{{width:100%;border-collapse:collapse;font-size:.92rem}}td,th{{padding:10px;border:1px solid #62533a;text-align:left;vertical-align:top}}code,pre{{overflow-wrap:anywhere;white-space:pre-wrap}}img{{width:100%;height:auto;border:1px solid #62533a}}.note{{background:#3d3020;padding:16px;border-left:4px solid #dfaf64}}li{{margin:7px 0}}</style>
<main><h1>Project1998 r27<br>가방 한 번 정보 · 두 번 장착·먹기</h1>
<p>r26 최종본에서 이어서 사용자 지적 2건을 수정했습니다. 기존 패키지·서명·저장 경로와 r25/r26 저장 안전성·누적 상태 최적화를 유지했습니다.</p>
<div class="note"><b>판정: 이번 가방 보수의 PC 실행·저장 검증 및 APK 제작 통과.</b><br>전체 회귀에는 기존 실패 66개가 그대로 남았습니다. 물리 Android 설치·단말 입력·발열과 실제 진행 캐릭터 시험은 NOT_RUN입니다. 이전 미해결 지도·조건 검토를 이번 PASS로 합산하지 않습니다.</div>
<h2>달라진 조작</h2><table><tr><th>조작</th><th>결과</th></tr>
<tr><td>가방 항목 한 번 누르기</td><td>별도 사용·먹기·장착 선택 창 없이 상세 정보 표시. 게임 상태와 아이템 수량을 바꾸지 않음.</td></tr>
<tr><td>같은 항목을 빠르게 두 번 누르기</td><td>400ms 이내의 짧은 두 번 입력으로 원래 서버의 장착 / 음식 먹기 / 기타 사용을 한 번 실행. 정보를 오래 읽은 뒤에는 빠르게 두 번 다시 누르면 됨.</td></tr>
<tr><td>다른 항목·페이지·탭, 드래그·길게 누르기·메뉴·포커스 변경</td><td>이전 더블 입력 후보를 취소. 변경된 아이템을 잘못 소비하지 않음.</td></tr>
<tr><td>놓기·건네기</td><td>정보 아래 버튼에서 기존 동작 이용. 꾸미기·재료 주머니 등 고유 대화와 확인 절차는 유지.</td></tr></table>
<h2>표시 정보</h2><p>소형/대형 공격력, 방어 AC(낮을수록 피해 감소), 명중·공격 보정, 최대 HP/MP와 힘·지력·민첩 보정, 마법 방어·재생 보정, 필요 레벨·힘·직업·성별·승급, 현재/최대 내구도와 비율, 수리 여부·귀속·거래 제한, 현재 같은 장비 칸과의 차이를 표시합니다. 음식 회복량 등은 실제 ItemParams.csv·item_verbs.lua에서 가져옵니다. 알 수 없는 정의의 숫자를 임의로 만들지 않습니다.</p>
<img alt="최종 PC 실행 화면 — 가방 선택 즉시 정보와 착용 조건·내구도 표시" src="data:image/png;base64,{image}">
<h2>수정과 저장 안전성</h2><p>기존 화면 행에는 이름·아이콘·수량만 있었고, 모든 가방 항목이 전체 동작 선택 창을 열었습니다. 이제 기존 ItemDef와 보유 InvItem에서 불변 정보를 만들고, 기존 FULL SQLite 커밋이 성공한 뒤에만 화면에 게시합니다. 변경되지 않은 가방은 같은 정보 객체를 재사용합니다. UI는 Session 잠금이나 캐릭터 JSON, 전체 월드 수집·직렬화를 호출하지 않습니다.</p>
<p>두 입력 사이에 수량·내구도·소유자·보호·이름·아이템 정의·슬롯이 바뀌면 원래 핸들러에 들어가기 전 동일 Session 잠금 안에서 취소하고 저장을 실행하지 않습니다. 착용 조건·직업 제한·귀속 판정과 장비 교체는 원래 서버가 수행합니다. 저장 필드와 DB 스키마를 추가하지 않았습니다.</p>
<p>r26 동결 입력과 비교한 콘텐츠 <b>{preservation['content_files_compared']:,}개는 변경 0개</b>입니다. 원래 아이템 처리, CharacterStore, 지연 복구와 월드 캡처 최적화 핵심 파일의 바이트도 유지했습니다.</p>
<h2>실제 실행 결과</h2><p>최종 새 UI <b>{len(ui['checks'])}개 PASS</b>, 새 원본 정의·변경 거부·저장 실패·잠금 검사 <b>11개 PASS</b>. 기존 실제 아이템 UI <b>{legacy['check_count']}개 PASS</b>. 부모 합성 저장과 다른 캐릭터 2개는 보존되었습니다. 사용자 저장 변경은 0회입니다.</p>
<table><tr><th>xUnit</th><th>실행</th><th>PASS</th><th>FAIL</th></tr><tr><td>r26 기준</td><td>2,065</td><td>1,999</td><td>66</td></tr><tr><td>r27 최종</td><td>2,076</td><td>2,010</td><td>66</td></tr></table><p>신규 실패 0개, 기존 실패 이름·메시지 변경 0개입니다. 66개를 PASS로 처리하지 않았습니다.</p>
<table><tr><th>시험군</th><th>결과</th><th>관측 범위</th></tr>{rows}</table>
<details><summary>새 UI 21개 세부 검사</summary><ul>{checks}</ul></details>
<details><summary>남아 있는 기존 xUnit 실패 66개 — 이름과 메시지</summary><pre>{escape(failed)}</pre></details>
<h2>검증 범위와 실행 이력</h2><p>수정 전 실제 PC 터치로 추가 창을 재현한 FAIL 기록을 보존했습니다. 도구 정리로 사라진 동일 버전 SDK·Godot·Android 도구를 원래 고정 체크섬으로 복구했습니다. 첫 시험 준비의 컴파일/표시 환경 실패와, 장착 뒤 사라진 가방 칸을 다시 누르려던 시험 오류도 보존하고 바로잡았습니다. 최종 시험은 실제 indexed touch 및 mouse 입력 → Godot HUD → 원래 PlaySession/Session → SQLite 경로입니다. 호스트 시험을 새 APK의 실기기 PASS로 표시하지 않습니다.</p>
<h2>설치 파일</h2><p><b>{escape(apk.name)}</b> · {build['bytes']:,} bytes · arm64-v8a<br>버전 {escape(build['version_name'])} · code {build['version_code']}<br>패키지 <code>{escape(build['package'])}</code><br>기존 저장 폴더 <code>project1998_g1b_v4</code><br>서명 SHA256 <code>{build['certificate_sha256']}</code><br>APK SHA256 <code>{build['sha256']}</code></p>
<p>새 APK 내장 데이터·실제 소스 동결 입력, 패키지·기존 인증서, ZIP CRC와 정렬 검사를 통과했습니다. 소스·시험 ZIP에는 빌드 영수증과 실행 기록·재현 도구를 포함하며, 개인키·실제 사용자 저장·테스트 DB·전체 SDK는 포함하지 않습니다.</p>
<p>정본 STATE: <code>verification/r27/STATE.json</code><br>최종 UI: <code>evidence/r27/ui/final002/</code><br>전체 회귀: <code>evidence/r25/suite/r27-final001/</code><br>실패 비교: <code>evidence/r27/XUNIT-COMPARISON.json</code><br>APK: <code>android/evidence/build-r27-001/BUILD_RECEIPT.json</code></p>
</main></html>'''
for p in [out/'Project1998-r27-report.html',copy/'Project1998-r27-report.html']:p.write_text(report,encoding='utf-8')
print(json.dumps({'status':result['status'],'apk':apk.name,'ui_checks':len(ui['checks']),'legacy_checks':legacy['check_count'],'source_inputs':build['source_input_count'],'new_xunit_failures':len(comparison['new_failure_names'])}))
