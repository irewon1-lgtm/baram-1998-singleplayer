# Work 콘텐츠 확장 재개 체크포인트

프로토콜: BARAM_PARALLEL_V1 / BARAM_CONTENT_PACKAGE v1.
Work 브랜치: work/content-import. 수정 범위: content-work/**.
체크포인트 작성 직전 관측한 원격 HEAD: d4bd4b17a5307d5c882936c39547d698736d3733.
재개 시 현재 원격 HEAD를 한 번 읽는다. 이 파일에 자기 커밋을 재귀적으로 넣지 않는다.
전체 제작: INCOMPLETE_FIXED_INVENTORY_REMAINS. 세션 종료 후 자동 작업 없음.

## 중단 및 복구

확인된 과거 오류: exec cell41 not found. 채팅 연결 끊김 근본 원인: UNKNOWN.
저장된 결과부터 재개했으며 CONTENT002/003/004와 ASSETS002의 제작·해독·동일 검사를 반복하지 않았다.
원격에서 CONTENT004의 인계 등록과 ASSETS002의 게시가 남아 있어 복구했다.
기존 고정 패키지는 보존했고 main·Codex 실행 코드·원본 픽셀·저장 데이터는 수정하지 않았다.

## 고정 전달

| 패키지 | 정확한 패키지 커밋 | 데이터 준비 |
|---|---|---|
| WK-ASSETS-001 | 1800a3a0d7ffdb4b27212c6dfdd2539a93212d6b | READY_FOR_CODEX |
| WK-CONTENT-001 | d318098bce3c2923516a8b83ad5e2d1fe53d055e | READY_FOR_CODEX |
| WK-CONTENT-002 | 10b4dcfbf1d1c9fff89b36c71ca36429f12e7bda | READY_FOR_CODEX |
| WK-CONTENT-003 | 897495bfd15f9c35fd7d0d9da64c4009232ad33b | READY_FOR_CODEX |
| WK-CONTENT-004 | da6679f563a55dd54cec719eb0903edd8745eca5 | READY_FOR_CODEX |
| WK-ASSETS-002 | 174eb63dad76e36dee83551b02648f7da8f2dcc4 | READY_FOR_CODEX |
| WK-CONTENT-005 | 901a85be123ff0bf80beb09f30fa5ba35b08a276 | READY_FOR_CODEX |
| WK-ASSETS-003 | 7051fd1b2ce68fb62decf6094f8b2d78cf121662 | READY_FOR_CODEX |
| WK-CONTENT-006 | d4bd4b17a5307d5c882936c39547d698736d3733 | READY_FOR_CODEX |

manifest와 의존성 핀은 HANDOFF_INDEX.json 및 각 패키지 manifest에 있다.
CONTENT001의 기존 dependency.commit 표기는 그대로 보존한다. 새 패키지는 package_commit을 사용한다.
두 표기는 같은 정확한 패키지 커밋을 가리키며 인계 목록에서 확인됐다.

CONTENT002: 기존 정의457 보완, 아이템 분류51 교정.
CONTENT003: 지역24군·새 원본 지형322, 몬스터51(보스8)·아이템66·NPC96·상점24·퀘스트62·제작법192.
CONTENT004: 기존 기술 이펙트199 보완, 1차 기술12·아이템12·의뢰4.
ASSETS002: 복구 EPF47·프레임75·PNG47. 비공개 ZIP3,686,257바이트가 보존돼 있으며 acquisition.json에 취득 신원과 해시가 있다.
CONTENT005: 2/3차 기술16·아이템24·의뢰8. 교사 메뉴에서 빠졌던 1차 기술12개도 조건부 services 수정으로 보완.
ASSETS003: 원본 효과 시간표8 복구. 원인은 0ms가 아니라 부호 없는 정규식이 Frame# -1을 누락한 것.
CONTENT006: 복구 효과7과 기존 기술을 조건부 연결. 비용·피해·대상 등 동작 수치는 그대로.

## 실제 검사 범위

기존 CONTENT004 파일23, ASSETS002 패키지/부가 파일15의 원격 blob 일치를 확인했다.
새 CONTENT005/ASSETS003/CONTENT006의 원격 blob 일치 파일은 각각20/14/12, 불일치0.
새 데이터의 schema·guard·참조·숫자·프레임·퀘스트/습득 경로 검사를 실제 실행했다.
CONTENT005는 새 교사 메뉴16 및 영향받는 기존 메뉴238 연결 확인 PASS.
과거 CONTENT004의 기존 PASS는 교사 메뉴까지 확인한 결과가 아니었다. 불변 보고서를 수정하지 않고 trainer-menu-evidence.json에 기존 누락12→보완 결과를 기록했다.
ASSETS003은 시간표139항목과 대기17항목을 그대로 보존했다. 정상 효과2개의 파싱 결과 동일,
잘못된 -2/0ms/허용 범위 밖 음수 사례3개의 차단을 확인했다. 대표 이미지8개만 직접 봤으며 전체 애니메이션 검토는 NOT_RUN.
패키지9개의 manifest 파일과 모든 정확한 의존성 핀 일치 PASS. 이미 통과한 동일 콘텐츠 검사는 재사용.

ASSETS003/CONTENT006은 effect_blank_frame_wait 기능이 필요한 선택 묶음이다.
Frame# -1은 그림을 읽지 않고 원본 delay_ms만큼 시간을 진행한다는 INFERRED 해석이다.
네이티브 클라이언트와의 동작 대조 NOT_RUN. -1을 0번 그림으로 바꾸거나 대기 시간을 버리지 않는다.
지원되지 않으면 이 선택 묶음만 보류하고 CONTENT002~005를 계속 적용할 수 있다.
원본 지형은 북미 NA495를 활용한 한국어 확장 콘텐츠이며 한국1998 실제 지형 증명으로 표시하지 않는다.

Codex 취득·반영·플레이: 확인되지 않음. 이번 codex/game-core의 content-work/receipts 조회가404였다.
실제 반영이 없다는 증명은 아니며, 정확한 패키지 수신증을 확보하기 전 상태를 올리지 않았다.
Work의 비공개 ZIP 취득은 Codex의 취득 증명이 아니다. 모든 게임 실행 항목은 NOT_RUN.

## 남은 고정 목록

자산 정의1047: 콘텐츠 참조417 / 공통 의존5 / 해독됐으나 연결 미완료625.
처음992 정의 중 연결 미완료577. 새로 추가한55 정의 중 UI47과 말 탄 형상 효과99는 연결 미완료.
지도 원본1750 파일: 정의·검사385 / 중복853 / 치수 근거 부족322 / 역할 보류190.
보류190 = 실내 서비스 예비79 + 작은/애매한 역할102 + 팔레트·진단 지형8 + 통행 영역 부족1.
물리 지도는 기존63(고유 지형60) + 새322(고유 소스 해시322). 논리 지도 정의386, 별칭1.
이번 확장 누적 신규 아이템102·퀘스트74·기술28. 프레임/시퀀스/이미지/지형/게임 화면 사용량을 섞지 않고 전체 완성률을 계산하지 않는다.

남은 원본 입력3개: bow.epf(0프레임), line001.epf(빈 파일), 효과72(빈 시간표).
기존 asset-errors.json의58건은 발생 이력. 현재 오류는 catalog/expansion-2/asset-errors-current.json.
복구 PNG9장의 이전 오류, 복구 EPF47, 복구 효과8을 별개로 구분한다.
항목별 원인·다음 작업은 asset-after.jsonl / map-after.jsonl / remaining-reasons.json.
역할만 지정하거나 해독만 한 항목은 콘텐츠 연결 완료로 세지 않는다.

## 다음에 바로 수행

1. 원격 인계 목록9개와 current-summary.json을 읽고 현재 작업 원장부터 시작한다. 기존 추출·동일 검사 반복 금지.
2. 미연결 배우 모델을 목적에 맞는 몬스터/NPC·실제 배치·드롭/사용처·대화/의뢰 묶음으로 다음 새 패키지에 제작한다.
3. 팬3·방패13은 실제 획득 가능한 장비·제작·동작을 연결하고 필요한 기능을 선언한 독립 선택 묶음으로 준비한다.
4. UI에는 정확한 기존 화면·버튼·이벤트 소비자를 연결할 수 있는 기능이 필요하다. 프로토콜 밖 필드를 몰래 만들지 않는다.
   머리85개는 헤어 선택 기능이 확인되기 전까지 투구로 강제 사용하지 않는다. 음향은 구체적인 이벤트 연결 근거부터 확인한다.
5. 실내 예비 지형은 새로운 필요한 역할에 사용한다. 보급소 복제로 숫자를 늘리지 않는다. 치수 미확정322개를 근거 없이 정사각형으로 간주하지 않는다.
6. 다음 미사용 번호는 현재 기준 WK-CONTENT-007 / WK-ASSETS-004. 번호 충돌 확인 후 데이터 제작·짧은 검사·고정·게시·후속 인덱스 등록을 계속한다.
   Codex 수신을 기다리며 대기하지 않고, 고정 패키지/기존 목록을 덮어쓰지 않는다.
