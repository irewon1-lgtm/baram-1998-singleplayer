# Codex 실행 인계 — BARAM_PARALLEL_V1

## 고정 기준과 보존

- 개발: `codex/game-core`, 독립 worktree `/workspace/baram-codex-core`.
- 최초 게임 기준: `dev/codex-asset-runtime-20261014`, `dea6574c9a69ebb04432d10fc32951aacd8b66cb`. 원래 폴더와 main·조사·수치 원문은 보존했다.
- 마지막 확인된 원격 저장: `b5ef10646a2a41ff16ad575df47373c4b0399788`(확인된 실행본 빌드). 실행 통합 코드 묶음은 ae4fb282315955c566b6b08ebf210b2301a9597f이며 수신 기록은 후속 커밋에 연결돼 있다. 최종 원격 HEAD는 최신 문서/검증 후속 커밋을 포함하므로 git ls-remote로 확인한다.
- 실제 반영 목록 HEAD: `d4bd4b17a5307d5c882936c39547d698736d3733`. 최종 새 전달 목록은 `6bfa2687a996f3e80297df9e7a51e7e364a67b5a`에서 읽었다. 검증 실행본은 기존 확정 커밋들로 고정했다. 브랜치 병합/루트 덮어쓰기/상류 파일 수정은 하지 않았다.
- 엔진: 기존 Godot 4.6.3. Work schema 1은 그대로, Codex runtime envelope 2와 저장 schema 2를 사용한다. 이전 envelope 1 로드 경로도 유지한다.
- 활성 콘텐츠: `9e30ec651489a4f5bdbf5c4e727a41a3c7a2b2825a373262056c1e896a82fb7c`.
- 실행 정본과 실제 픽셀은 `/workspace/baram-private/codex-core-20261014/active-content`, 기존 자산은 `/workspace/baram-private/game-assets`에 있다. Git에는 원본/추출/파생 픽셀·사운드·사용자 저장을 커밋하지 않는다.

## 수신된 고정 패키지

| 패키지 | 고정 커밋 | 활성 상태 |
|---|---|---|
| WK-ASSETS-001 | 1800a3a0d7ffdb4b27212c6dfdd2539a93212d6b | 983/992 PARTIALLY_IMPORTED; v125 9개 WAITING_DEPENDENCY |
| WK-CONTENT-001 | d318098bce3c2923516a8b83ad5e2d1fe53d055e | IMPORTED |
| WK-CONTENT-002 | 10b4dcfbf1d1c9fff89b36c71ca36429f12e7bda | IMPORTED, 기존 ID 조건부 수정 |
| WK-CONTENT-003 | 897495bfd15f9c35fd7d0d9da64c4009232ad33b | IMPORTED |
| WK-CONTENT-004 | da6679f563a55dd54cec719eb0903edd8745eca5 | IMPORTED |
| WK-ASSETS-002 | 174eb63dad76e36dee83551b02648f7da8f2dcc4 | 47개 IMPORTED; 75 UI 프레임 역할/이벤트 미연결 |

- 001 KR 자산은 보유 DAT/SND와 검토한 고정 Work 변환기로 재생성하여 각 공개 메타데이터/page/WAV 해시에 일치했다. Library 전체 ZIP 취득을 주장하지 않는다.
- 지역 001은 전체 비공개 ZIP 해시까지 재현했다. 지역 002는 새 원본 맵 322개 각각의 입력/출력 해시를 확인했다. 002 전체 ZIP 취득과는 구분한다.
- UI 002는 고정 clipping 프로필로 47개 정의/75프레임/전체 ZIP SHA와 크기까지 일치했다. 다른 정상 EPF나 상류 Work 파일을 수정하지 않았다.
- 기존 ID가 같은 그림을 쓰더라도 재발급/통합하지 않는다. 동일 패키지 재수입은 ALREADY_IMPORTED이며, 004/자산002만 추가 반영했다.
- 원본 기준 수치와 Work의 ORIGINAL/AVERAGED/INFERRED/DERIVED, 변경 전 조건, patch history를 보존한다. 001–004는 원작 전체 확인값이 아니다.

## 실제 구현·연결

- 선언형 Work 어댑터: 원본 TBL 지면·SObj 위쪽 기둥, 4비트 충돌, 출입구, NPC/몬스터 개체, 장비·아이콘·방향/행동/기준점, 효과의 앞/뒤/반복 시간, WAV.
- 기존 마을/맵 ID 38개를 유지하며 Work 물리 맵 385개를 별도로 연결했다. 총 423씬은 고유 지형 423개라는 뜻이 아니다. 중복 제거 원본 지형은 387개다.
- 데이터 정의: 아이템613, 몬스터320, NPC155, 기술211, 퀘스트99, 상점62, 제작법193, 승급12, 성장401. 배치/실행 표시 수는 content-summary와 GUI 결과에서 따로 확인한다.
- 공통 후보 상태 거래·보상·장착·소모·수련·제작·강화·승급, 개별 장비와 내구/강화 단계, 반복 의뢰 회차/정렬 목표/맵 조건/중복 보상 차단.
- 4직업 1–99 성장/종단 처리, 승급/경험치 교환, 1차 승급 장비 조건과 귀속 수련 문서 소모. 자연 육성 완주와 구분한다.
- 피해/회복/방어막/지속 상태, 근접·원거리·독 공격, 제한 경로 탐색, 저장된 몬스터 정의의 현재 정본 재연결.
- 이미지 LRU에서 먼저 그린 페이지가 제거되며 흰 사각형이 생기던 원인을 수정했다. 현재/직전 프레임 리소스만 유지하여 반복 디코딩을 피하며, 사용하지 않은 페이지는 다음 프레임에서 해제한다.
- 저장: checksum/내용 검증, 임시 파일→제한 백업→안전 교체, v1 사본 이전, 손상 주 파일은 정상 백업이 있을 때만 정확한 손상 사본 보존 후 복구, 미래 버전 자동 백업 fallback/새 게임 대체 금지.

## 검사와 미완료

- 가져오기31 PASS: 합성 test.* 데이터로 중복/같은 batch 변조/참조/단위/확률/해시/조건부 충돌/의존 커밋/원자적 실패 복구. 게임 플레이 시험이 아니다.
- 공통 시스템43 PASS. 실제 활성 Work 데이터41 PASS. 과거 실제 레벨6 저장의 읽기→사본 변환→재저장→재로드/핵심 진행과 원본 SHA 보존을 포함한다.
- 실제 X11: 기본 생성·이동·사냥·경험치·줍기·장착·기술 자원·NPC·저장·별도 프로세스 재시작을 실행했다. Work 지역/NPC 연결과 캐시 수정 전후 화면을 확인했다. 상세 코드/콘텐츠 버전과 실패/시간초과는 receipt에 남긴다.
- 이전 원본 계산37 PASS는 그때의 코드와 범위에만 유효하다. 변경 없는 원본 수치 조사를 재실행하지 않았다.
- 전체 맵 정상 이동, 모든 기술의 GUI/조건 의미, 네 직업 자연 1–99 완주, 전체 승급 완주, 장시간 안정성, 사용자 플레이, 원작 동일성은 NOT_RUN/미확정이다.
- Work 고구려 마을 역할은 북미 원본76의 바위/용암형 지형을 선택했다. 실제 옛 마을은 유지했다. 지형/역할 재선정은 Work 수정 요청이며 원작과 동일하다고 표시하지 않는다.
- UI 47개는 취득·등록과 정상 게임 이벤트 연결을 구분한다. 역할 연결을 임의로 완료 처리하지 않는다.
- Windows 엔진 다운로드: 프록시 CONNECT 403 BLOCKED. Linux 성공을 Windows 실행 PASS로 바꾸지 않는다.

## 복구와 바로 다음 작업

- 원래 정상 개발 커밋 dea6574와 기존 비공개 자산·원본·사용자 저장은 그대로 있다. 현재 활성 버전 전 immutable release와 ACTIVE.previous도 개발 vault에 보존한다.
- 원복은 관련 코드/데이터/저장 호환성을 함께 확인한다. envelope2를 이해하지 못하는 옛 런타임에 현재 콘텐츠를 억지로 읽히지 않는다.
- 비공개 실행본: /workspace/baram-private/codex-core-20261014/results-release6/baram_codex_core_PRIVATE_20261014.zip (173436306bytes), SHA256 83ae609bc87b7031a35bf3af4a624922c7f4f3bc3c9bed25e90cc4cc3da0bd7a. 코드 b5ef106과 활성 콘텐츠9e30ec65.../envelope2/save2를 고정했다.
- 별도 검증·화면 ZIP: 같은 폴더의 baram_codex_core_VERIFICATION_PRIVATE_20261014_v2.zip. Gitbundle/원본용 intake 입력/현재 실행 픽셀은 실행 ZIP에 있다. 사용자 저장은 제외했다.
- 실제 해제 후 1438 manifest 파일 크기/SHA 전수 일치, Linux launcher의 새 생성·장착·이동·Work 기술·저장9 검사와 별도 프로세스 재시작5 검사 PASS. 게임 빌드/콘텐츠 버전도 저장/실행 결과와 일치한다.
- 현재 버전의 renderer draw telemetry: Work 시트91 프레임ID(타일55/기타36), 별도 기존 atlas19 프레임ID/타일280 ID. 겹친 픽셀까지 각 자산의 실제 시각 표시를 개별 판정한 수가 아니며, 두 네임스페이스를 원본 고유 그림 수로 합산하지 않는다.
- 현재 Work 타일 정적 배치7392 고유ID/694853 배치와 실제 프레임 표시를 구분한다. 전체 맵을 정상 입력으로 모두 다니지는 않았다.
- 다음: 사용자 재현 오류나 새 고정 Work 패키지부터 처리한다. 현재 데이터로는 초기 로딩(이 환경 소프트웨어 GL 약45–49초)과 모든 동적 출입구의 실제 통행을 우선 측정한다. `tests/run_playable_screen.py`의 route는 interact 출입구를 벽으로 취급하지 않도록 수정했다. 최신 전체 bridge tour의75초 시간초과는 FAIL을 보존했으며, 성공한 개별 복귀/지역 화면 결과와 구분한다.
- Codex 후속 코드: `game/main.gd` dungeon 밝기 분기는 아직 legacy buff 이름을 읽고, Work `status.light`는 저장/만료 처리만 연결됐다. 기존 light 선언의 화면 밝기 연결과 비걷기 동작의 반복/종료 타이밍 대조를 다음 영향 검사 대상으로 남긴다. 모든 기술의 효과 완성을 주장하지 않는다.
- v125 정확한 미확보 9개 ID는 content-summary와 WK-ASSETS-001 receipt에 있다. 다른 패키지 적용을 막지 않는다.
- 실행본에 사용자 저장을 넣지 않는다. 실행본 검증과 확인된 코드 원격 SHA를 이 문서에 기록했다. 세션 종료 뒤 자동 감시하고 있다고 주장하지 않는다.

## 실행본 고정 후 새 전달

- WK-CONTENT-005/006/007/008와 WK-ASSETS-003의 고정 manifest와 index SHA는 실제 일치했다. 상세 데이터 검사/취득/반영/플레이는 NOT_RUN이며 READY_NOT_RECEIVED로 남긴다.
- 다음 바로 시작할 파일: integration/content-import/receipts/followup-inputs.json. 각 source_commit/manifest_path에서 스냅샷을 읽고 PROTOCOL/schema 및 새로운 capability 이름의 실제 의미를 대조한다. 기능이 이미 있으면 명칭 차이로 반려하지 않는다.
- 활성9e30ec65...와 실행 ZIP83ae609b...에 새 자료를 섞지 않았다. 새 버전은 별도 검증·커밋·ZIP으로 처리하고 현재 정상 실행/저장 복구 기준을 보존한다.
