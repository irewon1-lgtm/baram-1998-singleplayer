Project1998 r27 — 가방 정보와 더블 터치

정본: verification/r27/STATE.json (이전 r25/r26 STATE는 당시 실행 기록)
기준: r26 code30, local abc5096 / remote 55d7cb02cf488b2232d9c81aede8556bbf3d4535
기존 패키지 com.irewon.project1998.g1bv4 / 저장 폴더 project1998_g1b_v4 유지.

가방의 아이템을 한 번 누르면 상세 정보가 즉시 표시됩니다.
동일한 아이템을 400ms 안에 두 번 누르면 원래 서버의 장착·먹기·사용을 한 번 실행합니다.
정보를 확인한 뒤 시간이 지나면, 빠르게 두 번 다시 누르면 됩니다.
별도 사용/먹기/장착 선택 창은 열리지 않습니다. 놓기·건네기는 정보 아래 버튼으로 이용합니다.
장비 수치, 공격력 범위, 방어 AC, HP/MP/능력치 보정, 필요 레벨·힘·직업·성별·승급,
현재/최대 내구도, 수리 여부, 귀속·거래 제한, 현재 장비와의 차이를 표시합니다.
음식의 HP 회복 등 효과는 실제 ItemParams.csv와 item_verbs.lua에 대응합니다.
꾸미기·주머니 등의 원래 확인/대화 절차와 착용 제한은 그대로 적용됩니다.

핵심 변경:
  candidate/Server/Session.OfflineInventoryInspection.cs — 기존 ItemDef와 InvItem의 불변 정보
  candidate/Server/Session.OfflinePersistence.cs — 성공한 FULL SQLite commit 뒤에만 게시
  Host/ClientScene.cs / EmbeddedHost.cs / PlaySession.cs — 원래 wire 목록에 상세 정보 부착
  android/GameHud.Items.cs / GameHud.cs / Main.cs — 즉시 정보, 더블 입력, 원래 핸들러 연결

새 저장 필드나 DB 스키마를 추가하지 않습니다. 동일한 가방은 게시된 정보 객체를 재사용합니다.
UI는 게임의 Session 잠금, Character JSON, 전체 World 수집/직렬화를 호출하지 않습니다.
두 번의 터치 사이에 아이템 수량·내구도·소유자·보호·이름·정의·슬롯이 바뀌면,
원래 핸들러 진입 전 동일한 Session 잠금 아래에서 거부하고 저장도 실행하지 않습니다.

실행 증거:
  evidence/r27/ui/baseline002/runtime/ko-checks.json — 수정 전 추가 창 문제 실제 PC 터치 재현 FAIL
  evidence/r27/ui/baseline002/RESUMED-REPRODUCTION.json — 표시 환경 복구 후 재개 이력
  evidence/r27/ui/green002/ — 첫 17개 실행 PASS
  evidence/r27/ui/final002/ — 최종 21개 실제 PC 터치·마우스·저장/이어하기 PASS
  evidence/r27/xunit-targeted001/ — 새 11개 원본 정의/변경 거부/저장 실패/잠금 검사 PASS
  evidence/r25/suite/r27-final001/ — 최종 전체 회귀 결과 (기존 실패를 별도 보존)
  android/evidence/build-r27-001/ — 최종 APK 내장 데이터·정렬·원래 서명·동결 입력 검사

전체 회귀의 원래 66개 실패를 PASS로 바꾸지 않습니다. 새 실패 여부는 결과 보고서를 확인하세요.
실기기 연결이 없으므로 Android 설치·단말 터치·발열·실제 진행 저장 검사는 NOT_RUN입니다.
이전 r26의 미해결 지도/스크립트·조건 검토를 이번 가방 보수의 PASS로 합산하지 않습니다.
개인키·실제 사용자 저장·테스트 DB·복구한 도구 전체는 제출 ZIP에서 제외합니다.

재현 가능한 도구 복구: python verification/r27/restore_tools.py
도구 경로: <workspace>/toolchain-r27
원래 개인키는 별도로 보관하고 --private-signing 경로로 지정해야 합니다. 새 키를 만들지 마세요.
최종 APK 제작 명령과 SHA256은 r27 보고서 및 android/evidence/build-r27-001/에 있습니다.
