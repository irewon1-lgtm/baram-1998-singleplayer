# Work 콘텐츠 제작 재개 지점

수정 범위: content-work/**. 프로토콜 BARAM_PARALLEL_V1 / BARAM_CONTENT_PACKAGE v1.
전체 게임 복원 상태: INCOMPLETE. 이번 CONTENT010 원격 게시·등록·적용 기록 대조는 완료했다.
마지막 확인된 패키지 커밋: f7a85eee9615db2d2f977ae5796a867a096bce07. 이 문서는 그 후속 등록 커밋에 저장된다.
세션 종료 후 자동 작업 없음. 고정 패키지는 변경·재생성하지 않는다.

## 고정 패키지 — 13개

| 패키지 | 정확한 패키지 커밋 | 확인된 상태 |
|---|---|---|
| WK-ASSETS-001 | 1800a3a0d7ffdb4b27212c6dfdd2539a93212d6b | Codex 983/992 적용 / 9개 대기 |
| WK-CONTENT-001 | d318098bce3c2923516a8b83ad5e2d1fe53d055e | Codex 적용 기록 확인 / 전체 플레이 미검증 |
| WK-CONTENT-002 | 10b4dcfbf1d1c9fff89b36c71ca36429f12e7bda | Codex 적용 기록 확인 / 전체 플레이 미검증 |
| WK-CONTENT-003 | 897495bfd15f9c35fd7d0d9da64c4009232ad33b | Codex 적용 기록 확인 / 전체 플레이 미검증 |
| WK-CONTENT-004 | da6679f563a55dd54cec719eb0903edd8745eca5 | Codex 적용 기록 확인 / 전체 플레이 미검증 |
| WK-ASSETS-002 | 174eb63dad76e36dee83551b02648f7da8f2dcc4 | Codex 적용 기록 확인 / 전체 플레이 미검증 |
| WK-CONTENT-005 | 901a85be123ff0bf80beb09f30fa5ba35b08a276 | 데이터 준비 / Codex 적용 미확인 |
| WK-ASSETS-003 | 7051fd1b2ce68fb62decf6094f8b2d78cf121662 | 데이터 준비 / Codex 적용 미확인 |
| WK-CONTENT-006 | d4bd4b17a5307d5c882936c39547d698736d3733 | 데이터 준비 / Codex 적용 미확인 |
| WK-CONTENT-007 | 381cfefad15a2fff6356f2e9a0bd3859af3fc703 | 데이터 준비 / Codex 적용 미확인 |
| WK-CONTENT-008 | 2935c1f7cebed5a673dca1660d6bb0fbff0ae35d | 데이터 준비 / Codex 적용 미확인 / 008·010 동시 적용 충돌 |
| WK-CONTENT-009 | c75c3b9352070c02f3013e9afd2079797b754823 | 데이터 준비 / Codex 적용 미확인 |
| WK-CONTENT-010 | f7a85eee9615db2d2f977ae5796a867a096bce07 | 데이터 준비 / Codex 적용 미확인 / 008·010 동시 적용 충돌 |

## CONTENT010 게시 복구 — 완료

- 입력은 기존 drafts/publish-content-010.json과 expected 파일 및 완성된 패키지 그대로 사용했다. 활3·제작법3·NPC 조건부 수정3건.
- manifest SHA256: 59e352d2c2b34bdab160380e2dd00aade99c86b18cfe35ab3b3873f8aec1bb4f.
- 원격 HEAD 199fdf5ae52142d0577f84a32981b1cd50bacc3c, base tree 5898e00dd874e733fe752d191ddbf27e55fbdb8a를 다시 읽었다.
- 이전 실패 tree는 사용하지 않고 새 create_tree 호출로 fb4feb0d61a04d36007933299f7267b92be0d6c2를 만들었다. parent_sha를 명시해 f7a85eee9615db2d2f977ae5796a867a096bce07을 생성했다.
- expected_sha=199fdf5ae52142d0577f84a32981b1cd50bacc3c, force:false로 갱신 성공. 게시 SHA와 응답은 로컬 drafts/resume-content-010에 파일로 기록했고 함수 메모리를 사용하지 않았다.
- 원격 blob 15/15와 로컬 SHA256/크기 대조 PASS. 13개 패키지 파일 및 도구1·ID목록1만 변경. 기존 고정 패키지·content-work 밖 파일·main은 변경하지 않았다. 이미지/비공개 ZIP 추가 없음.
- 고정 검사기와 정확한 의존성으로 데이터 재검사: 레코드9·참조70·프레임선택96·수치114·조건부수정3·manifest파일12 PASS.
- 이전 connection-validation의 제작법3·획득경로3·NPC배치3 PASS는 기존 기록이며 이번에 게임으로 재실행한 것이 아니다.
- 증거: catalog/content010-resume/publication-verification.json, data-validation.json.

## CONTENT008 / CONTENT010 대장장이 충돌 — 확인, 병합안 준비

- 대상: wk.npc.exp2.dry.51.smith, wk.npc.exp2.forest.11.smith.
- 두 패키지가 같은 변경 전 services/dialogue 전체 목록에 서로 다른 메뉴를 추가한다. 각 NPC 2필드, 총 4필드가 충돌한다. 008 뒤 010을 기존 규칙 그대로 적용한 데이터 검사는 FAIL이다. 적용 순서만 바꿔도 해결되지 않는다.
- dry.51: 기존11개 서비스 → 방패+활을 포함한13개. 활 메뉴 service_index 11→12.
- forest.11: 기존12개 서비스 → 방패+활을 포함한14개. 활 메뉴 service_index 12→13.
- 고정 패키지 원본은 보존했다. catalog/content010-resume/npc-merge-proposal.json은 두 패키지 SHA를 고정한 별도 병합안이며 BARAM 패키지나 자동 적용 코드는 아니다.
- 정적 모의검사 PASS: 알려진 상태8, 예상 밖 변경 거부8, 기존/추가 메뉴와 서비스 대응50. 원래 변경 전 조건을 무시하거나 미확인 Codex 수정 위에 덮어쓰는 방안이 아니다.
- 소비자는 두 선택 장비 기능과 의존성을 확인하고, 전체 NPC 필드쌍이 정확히 알려진 상태인 경우에만 명시적 병합을 하나의 원자적 거래로 적용해야 한다. 그 밖의 기존 guard는 모두 유지한다.
- 실제 Codex 가져오기·NPC 메뉴·제작·활 발사·저장 검증은 NOT_RUN. 동시 적용은 소비자의 명시적 병합 처리/실제 시험 전까지 BLOCKED로 유지한다.
- 재현: python content-work/tools/reconcile_content008_010.py. 결과: catalog/content010-resume/npc-conflict-validation.json.

## 별도 Codex 적용 기록 대조

- 관측 브랜치 codex/game-core, 고정 HEAD 938443c538d2edf8db0a68302cc1fb1d48eb39c9. 해당 커밋의 실제 수신증과 source_commit/manifest SHA를 대조했다. 다른 대화나 미게시 작업의 상태는 알 수 없다.
- CONTENT001~004 IMPORTED, ASSETS001 983/992 PARTIALLY_IMPORTED(9개 대기), ASSETS002 47개 IMPORTED. 인덱스의 오래된 NOT_RUN 표시를 해당 수신증으로 바로잡았다.
- ASSETS002는 취득·등록과 UI 이벤트 연결이 별개다. 75프레임의 정상 UI 이벤트 연결은 아직 미완료다.
- CONTENT005/006/007/008와 ASSETS003은 Codex followup-inputs에 READY_NOT_RECEIVED로 기록돼 있다. Work 검사 결과와 Codex 자체 data_validation NOT_RUN을 혼동하지 않는다.
- CONTENT009/010 수신증은 관측한 원격 tree에 없다. 게임 적용 완료로 표시하지 않는다.
- CONTENT010 요구 중 original_bow_firing_pose_attachment, ranged_physical_weapon_attack은 capability 목록에 같은 이름으로 없다. 이름만으로 기능 부재를 단정하지 말고 의미·코드 대조가 필요하다. 몬스터 원거리 공격 지원만으로 플레이어 활 발사 지원을 판정하지 않는다.
- 기존 기본 전투/이동/저장 등의 Codex 실행 기록은 존재하지만 전 패키지·전체 맵·4직업 자연1~99·승급 완주를 증명하지 않는다. 이번 Work에서는 게임을 실행하지 않았다.
- 증거: catalog/content010-resume/codex-receipt-comparison.json과 해당 커밋 integration/content-import/receipts/*.

## 기존 누적과 이번 증가분

009까지 정의 집계: advancement12, class5, drop_group390, economy1, enhancement1, growth401, item675, map386, monster390, npc259, quest123, recipe231, shop62, skill227.
010 신규 정의는 item3·recipe3이고 NPC3건은 기존 정의 수정이다. 정의 기준 item678·recipe234, 다른 종류 수량은 같다. 게임 활성 수량이나 완성률이 아니다.
009 당시 자산 정의1047 = 콘텐츠 참조628 + 공통 의존7 + 연결 미완료412. 010은 남은 활 모델3의 명시적 참조를 추가했다. 그림 수·화면 표시 수·게임 적용 수로 집계하지 않는다.
남은 배우16·음향162·시트128·머리85·효과18은 이전 개별 사유를 유지한다. 활3의 데이터 연결은 생겼지만 소비자 기능/실제 사용 검증은 남는다.
원본 지도1750: 정의385 / 중복853 / 치수 근거 없음322 / 역할 보류190. 논리 정의386에는 별칭1이 포함된다.
원본 입력 보류: bow.epf 0프레임, line001.epf 빈 파일, 효과72 빈 시간표. 없는 화살 그림을 확보했다고 주장하지 않는다.
ASSETS003/CONTENT006의 음수 프레임 대기 해석은 INFERRED이며 native 대조 NOT_RUN.

## 다음 재개 지점

1. Codex는 본 인덱스의 정확한 커밋으로 후속7개(ASSETS003, CONTENT005~010)를 확인한다. 008·010 동시 적용은 위 명시적 병합안과 실제 가져오기 시험이 선행돼야 한다.
2. 필요한 소비자 기능, 실제 제작 메뉴/자원 차감/보상, 활 방향·사거리·벽 차단·단발 피해·장착·저장/재시작을 게임 개발 범위에서 검증한다. 데이터 모의검사를 게임 PASS로 바꾸지 않는다.
3. 기존 Codex 요청은 별도 후속 콘텐츠 과제다: 고구려 허브 지형/역할, UI 역할·이벤트, 강화 가능 아이템 조건, 피해감소/실명/빛의 단위·중첩 의미. 이번에 완료했다고 표시하지 않는다.
4. 다음 신규 번호는 WK-CONTENT-011 / WK-ASSETS-004. 고정 패키지 덮어쓰기·재생성 금지. main·게임 코드·저장·원본 픽셀 변경 금지.
