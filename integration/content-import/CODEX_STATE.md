# Codex 실행 인계 — BARAM_PARALLEL_V1

## 고정 기준과 보존

- 개발: `codex/game-core`, 독립 worktree `/workspace/baram-codex-core`.
- 최초 게임 기준: `dev/codex-asset-runtime-20261014`, `dea6574c9a69ebb04432d10fc32951aacd8b66cb`. 원래 폴더와 main·조사·수치 원문은 보존했다.
- 마지막 확인된 원격 코드 저장: `623f4cfddd5bc84968da2fc5e8d910fc4d96b6c4`(Windows 포장/검증 후속 코드). 고정 게임 빌드는 `b5ef10646a2a41ff16ad575df47373c4b0399788`이다. 이 인계와 수신 기록은 후속 커밋이며 최종 원격 HEAD는 `git ls-remote`로 확인한다. 최초 실행 통합 코드 묶음 ae4fb282315955c566b6b08ebf210b2301a9597f와 기존 수신 근거는 보존했다.
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
- Windows 공식 GitHub 다운로드는 프록시 CONNECT 403 BLOCKED 이력이 있으며, 2026-10-14 Windows 포장 작업에서는 허용된 Archive.org 보관본으로 Godot 4.6.3 x64 release template을 취득했다. 아래 Windows 포장 재개 항목을 따른다. Linux 성공을 Windows 실행 PASS로 바꾸지 않는다.

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

## Windows 64비트 실행본 포장 — 2026-10-14

- 이번 목적은 현재 검증된 게임을 사용자가 실행할 Windows ZIP으로 전달하는 것이다. Work 콘텐츠 제작이나 새 패키지 가져오기는 수행하지 않았다. 작업 시작 HEAD는 a02a36639467e5ea4444b8d4f0959952d98bec7b였다.
- Linux 원본 ZIP83ae609b.../게임b5ef106/활성9e30ec65.../envelope2/save2를 고정했다. 기존 게임 스크립트·수치·정본·픽셀·음향은 바꾸지 않았다. Windows bootstrap과 전용 메인 씬만 추가하여 외부 비공개 자료 및 저장 경로를 연결했다. 엔진 설치나 Python은 사용자 실행본에 필요 없다.
- Windows 템플릿은 https://ia600702.us.archive.org/27/items/godot-v-4.6.3-stable-export-templates-windows/4.6.3.stable.7z 에서 실제 취득했다. 보관본 MD5/SHA1/크기 일치, SHA256830ee5c4...를 기록했다. release x64 template SHA25691724f15...와 버전4.6.3/official7d41c59c.../AMD64 GUI PE 형식을 확인했다. 공식 배포 체크섬 대조는 공식 호스트 차단으로 BLOCKED이며, 이를 공식 SHA 검증으로 과장하지 않는다.
- 포장 코드938443c538d2edf8db0a68302cc1fb1d48eb39c9, 별도 픽업/재시작 시험 코드a5cd8ce, 최종 포장 검증 코드623f4cfddd5bc84968da2fc5e8d910fc4d96b6c4를 커밋·push한 뒤 원격 SHA 일치를 확인했다. 이 기록은 후속 metadata 커밋이다.
- 실제 결과 ZIP: `/workspace/baram-private/windows64-20261014/player-release/바람의나라_Windows64_개인용.zip`, 125493950bytes, SHA256 `7fe9b59e90410ec6af915797ccbb8e7630855574274c419d00fea0a32895baf2`. 작업공간 파일 참조 `/workspace/output/바람의나라_Windows64_개인용.zip`은 같은 바이트의 hardlink이며 외부 업로드 링크가 아니다.
- ZIP 전체 해제 후 `바람의나라.exe`를 더블클릭하는 구조다. Windows AMD64 GUI release template에 게임 PCK를 내장했다. 실제 EXE SHA256 `a5974353e5c6903f34dab7aa02e8e2ec64ffdd566c49849cfb62ead1363a0466`.
- 기존 비공개 실행 자산60파일 + 콘텐츠883파일 = 943파일/145473744bytes가 Linux 검증 ZIP과 모두 바이트 동일하다. 원본 설치압축·미리보기·개발 Linux 엔진·Gitbundle은 이전 비공개 ZIP에 보존하고 Windows 사용자 실행본에는 필요 없는 부분만 제외했다. 원본 자산이 없는 별도 체험판을 만들지 않았다.
- 최종 ZIP950멤버/manifest949파일의 크기·SHA 전수검사와 CRC PASS. 사용자 저장 파일0개, 검사한 EXE/비공개 파일이 최종 ZIP과 동일하다. 바뀐 검증 JSON과 manifest만 갱신했으므로 동일 게임 플레이를 반복하지 않았다.
- 자동 포장 보호11검사 PASS. 실제 ZIP에서 해제한 EXE의 embedded PCK를 Linux Godot/X11로 읽어 생성·이동·장비·NPC 거래창·사냥터 이동·공격·경험치·기술·저장·별도 프로세스 재시작25검사를 실행했다. 첫 토끼가 드롭0개였으므로 이 결과로 픽업을 PASS 처리하지 않았다.
- 그 정상 입력 저장의 정확한 사본으로 제한된 추가 사냥을 실행해 `kr.item.1f5693995ced` 1개가 실제로 드롭/줍기/보유수량 증가/저장됐고, 별도 프로세스에서 player/inventory/world/loot가 유지되는 12검사 PASS. 상태나 레벨·드롭을 주입하지 않았다. 합계37검사는 화면·행동·저장 범위이며 Windows PE 프로세스 실행 시험이 아니다.
- 비공개 화면·PCM 음향·원시 실행 로그: `/workspace/baram-private/windows64-20261014/gui-pck1`, `gui-loot1`. 공개 metadata는 `integration/content-import/receipts/windows64-package.json`에 있으며 픽셀/음향/저장 원문은 넣지 않았다.
- Windows 기본 저장은 `%LOCALAPPDATA%\BaramSinglePlayer\saves\v2\character.json`으로 ZIP 외부에 고정했다. schema2의 검증/한 개 백업/안전교체/지원하지 않는 버전 거부 로직을 그대로 사용한다. 실제 Windows 경로 권한·GUI·음향·저장·더블클릭 실행은 **NOT_RUN**이다. Linux 환경이며 Windows runner/Wine가 없다.
- 당시 대화 직접 첨부는 **BLOCKED**였다. 이후 아래 2026-10-15 비공개 파일 전송으로 실제 업로드·전체 다운로드 검증을 완료했다. 직접 채팅 첨부 기능과 Google Drive 계정 인증은 여전히 제공되지 않았으며, 사용자가 허용한 다른 파일 전송 방법을 사용했다. 사용자에게 별도 비공개 저장소를 요구하지 않았고 공개 배포·새 과금은 하지 않았다.
- 기존 알려진 일부 습득 메시지의 내부 ID 표시, 미확보 v125 자산9개, 전체 맵 통행/네 직업 자연1–99/승급/장시간 안정성/원작 동일성은 기존 미완료로 보존한다. 이번에 새로 콘텐츠가 연결됐다고 집계하지 않는다.
- 다음 즉시 작업: 첨부/다운로드 기능이 실제 제공되면 위 SHA ZIP을 재제작 없이 전달한다. 실제 Windows 환경이 있으면 더블클릭과 기본 저장 경로의 짧은 시험부터 한다. 이미 통과한37실행검사나 원본 자료 조사를 반복하지 않는다. 새 Work 통합은 기존 `followup-inputs.json`부터 별도 새 버전으로 시작한다.

## 기존 ZIP 실제 비공개 파일 전송 — 2026-10-15 한국시간

- `/workspace/output/바람의나라_Windows64_개인용.zip` 125493950bytes/SHA2567fe9b59e...를 그대로 전송했다. 게임 재제작·코드·콘텐츠 변경은0개이며 원본 ZIP도 변경하지 않았다.
- Google Drive API는 HTTP401/UNAUTHENTICATED였다. 제공된 Drive 앱 도구·계정 인증·rclone remote가 없다. 사용자가 다른 파일 전송 방법도 명시적으로 허용하여 무료 Send 서비스 `send.vis.ee`의 암호화 비공개 링크를 사용했다. 새 GitHub 저장소·사용자 가입·과금·공개 자산 배포는 없다.
- 기존 ffsend 업로드 클라이언트는 WebSocket에서 설정된 HTTPS 프록시를 사용하지 못했다. 표준 WebSocket 클라이언트로 같은 프록시와 TLS 인증 검증을 유지하여 정상 연결했고, Send v3/RFC8188 암호화 형식으로 기존 ZIP 바이트만 업로드했다. 서버에는 해독키를 전송하지 않았으며 링크·관리 토큰은 비공개 vault에만 저장했다.
- 업로드 성공 확인 후 독립적인 공식 ffsend 클라이언트로 실제 ZIP125493950bytes 전체를 다운로드/해독했다. 원본 SHA256 `7fe9b59e90410ec6af915797ccbb8e7630855574274c419d00fea0a32895baf2`와 정확히 일치하고 CRC 및 Windows EXE 멤버도 PASS였다. 검증 다운로드 뒤 원격 Exists:true/Password:false와 브라우저 다운로드 페이지 HTTP200을 재확인했다.
- 비공개 링크/전송 상태: `/workspace/baram-private/delivery-20261015/transfer-private.json`. 실제 재다운로드 결과는 같은 폴더의 `download-verified-original.zip`, 로그도 그 vault에 있다. 링크의 해독 fragment와 owner token은 Git에 커밋하지 않는다. 사용자 대화에는 검증된 링크를 제공했다.
- 요청한 전송 수명24시간/다운로드5회이며 검증에1회를 사용했다. 유효기한은 2026-10-16 00:19 한국시간으로 설정했다. 이후 만료되거나 다운로드 한도가 소진되면 기존 ZIP을 새 비공개 전송으로 다시 제공하며 게임을 재제작하지 않는다.
- 공개 메타데이터: `integration/content-import/receipts/private-delivery-20261015.json`. Windows-native 실행과 사용자 실제 다운로드·플레이는 아직 NOT_RUN/사용자 확인 대기이며 파일 전송 검증과 혼동하지 않는다.
- 다음: 사용자의 실제 실행 결과/오류부터 처리한다. 링크가 유효한 동안 같은 업로드·전체 다운로드를 반복하지 않는다. Windows 실행 검증·기존 Work 후속 통합은 기존 고정 계획대로 별도로 진행한다.
