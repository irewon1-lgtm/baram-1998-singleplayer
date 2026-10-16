# G0·P2 기술검증 결과 — PARTIAL

작업 `BARAM_REBUILD_CODEX_P2_001`, Codex 브랜치
`codex/rebuild-p2-20261016`. 기준 계획 HEAD는
`590bd626b63cebf6d858c8e9c1c9ce822ea0ec94`이며 reset/force-push 없이 분기했다.
원래 checkout은 보존하고 `/workspace/baram-p2-codex` worktree에서 작업했다.
최종 실행 앱 소스는 `7bfe3fff902f95de5b0b4253e2e0187853e24de0`에 고정했다.
최종 APK/EXE export는 전체 프로젝트 지문이 빌드 중 일치함을 확인했다. 초기 실패 앱·소스 지문과 수정 전후 증거는 별도로 보존했다.

**전체 P2 완료·P3 준비 PASS가 아니다.** G0 필수 비공개 입력 미수신,
원작 의미 공백, 네이티브 기기·IME·HTTPS 계정 왕복 미검증을 유지한다.

| 단계 | 실제 실행과 결과 | 판정·제한 |
|---|---|---|
| G0 전송 | 고정 도구로 실제 missing-core 검사, BLOCKED/exit1 | corev1·참고3분할 없음 |
| G0 바이트 | 원본42개·필요 중첩 바이트 없음 | BLOCKED; 감사 전용2개만 지정 지문으로 별도 확보·미실행 |
| G0 정규화 | private JSONL34개 없음, public save contract만 있음 | BLOCKED; 44,796행 현재 import NOT_RUN |
| G0 참조 | 과거154 오류의 실제 ID/원인/대상 풀을 보존된 진단과 대조 | 과거 FAIL 유지; 이번 import 종료코드1 재현으로 세지 않음 |
| G0 역사 의미 | 한국 지도/동작/음향/이름 규칙 공백 보존 | BLOCKED/UNKNOWN; 자료 무결성과 별도 |
| P2-01 | 한국 원본 지도·타일·객체·도시 근거 수신 불가 | BLOCKED; 렌더/충돌/사대문/왕복/귀환 실제 시험 NOT_RUN |
| P2-02 | KR491 부품·프레임·팔레트·원본 mask 없음 | BLOCKED; 합성/장착·미리보기/네 방향/mask2 재현 NOT_RUN |
| P2-03 | Effect128·WAV163 실제 바이트 없음, 오디오 하드웨어 없음 | BLOCKED; 효과/신호/실청취/원작 타격시간 NOT_RUN |
| P2-04 | 고정 NA LoginServer 빌드, 제공 시험81/81 PASS; 실제 loopback 서버의 합성 패킷·DB 검사17 PASS | PARTIAL; 실제 호환 클라이언트·한국 원작·IME·Lv5 전직 NOT_RUN/BLOCKED |
| P2-05 Linux | 공유 저장107검사 PASS, 실제 강제종료7경계·새 프로세스 재시작 포함; 화면 UI11·공유 저장85 PASS | 합성 fixture 범위 PASS; 실제 세이브 이전·원작 외형·실기기 결과 아님 |
| P2-05 Windows EXE | 같은 프로젝트 export PASS; Wine10 실제 UI11 PASS, 저장85중73 PASS/12 FAIL, 별도22 NOT_RUN | Wine CreateSymbolicLinkW stub 확인; 원래 FAIL 유지. 실제 링크 보호 미입증. 네이티브 Windows NOT_RUN |
| P2-05 Android APK | 같은 프로젝트 export PASS; Android10 소프트웨어 에뮬레이터에서 2회 실행/재시작, 매회 UI11·저장85 PASS, Linux 저장 바이트 일치 | 실제 Galaxy/휴대폰·native IME/물리 터치 NOT_RUN |
| P2-06 | 실제 설정·변수 이름/존재·identity manifest 확인; 제공된 시험용 인증/HTTPS/DB endpoint·binding 없음 | BLOCKED_ENVIRONMENT; PC→Android→PC 인증 왕복 NOT_RUN |

실행 명령·환경·코드/입력/도구 지문·종료코드는
`G0_RESULTS.json`, `SAVE_EXECUTION_RECEIPTS.json`,
`REFERENCE_RESULTS.json`, `PLATFORM_EXECUTION.json`, `evidence/`에 있다.
판정이 없는 명령을 실행했다고 쓰지 않았으며, 0개 실행을 PASS로 세지 않았다.

저장 구현은 공통 메타데이터/payload checksum, 소유자·stable ID·장비/기술·좌표,
직전 백업과 임시파일 검증, 손상 보존, 지도 버전 변경의 유효 좌표/전리품 보존과
불가능한 변환의 DEFERRED를 검증한다. 모든 값과 지도는 합성 fixture다.
실제 사용자의 세이브·앱·서명키는 열거나 변경하지 않았다.

독립 리뷰에서 결과파일 쓰기 실패의 거짓 PASS, pending symlink 쓰기,
다른 소유자의 backup-only 슬롯 덮어쓰기, SOURCES 전용 의존 바이트 확인 누락을
재현했다. 원인에 필요한 코드만 고치고 저장107·수신42검사를 실행했다. Android 초기 SwiftShader renderer 실패는 swangle 소프트웨어 backend에서 실행해 분리했고 엔진/앱 설정을 바꾸지 않았다. Android 실제 실행에서 추가로 발견한 고정 시험 디렉터리 재사용과 잘못된 파일 backend의 링크 검사 누락을 수정했다. 실행별 디렉터리를 보존·분리하고 native USERDATA backend를 사용하며 링크 assertions는 유지했다. ANDROID_STORAGE_DIAGNOSIS.json에 원본5실패와 근거가 있다.
고의 결과파일 기록 실패는 실제 FAIL1/exit1을 반환한다. 초기 결과와 실패 로그는
보존했다. Wine의 별도12실패는 지우거나 assertion을 낮춰 통과시키지 않았다.
`WINE_STORAGE_DIAGNOSIS.json`의 native mklink 재현과 공식 소스를 따른다.

기존 고정 도구도 현재 환경에서 격리 회귀를 실행했다: 검증기25 PASS,
importer18 PASS, 패키지 방어20 PASS. 실제 패키지가 없어 패키지 wrapper는
PARTIAL/exit2이고 실제 outer/reference 검사는 NOT_RUN이다. 이 합성 회귀 결과는
실제 수신 데이터 PASS가 아니다. 기존 원장2489-ID와 전체 import3565-ID 범위를
구분했으며 원천154 오류(기술→직업115, 스폰→몬스터24, 드롭→아이템8,
드롭→몬스터7)는 삭제/NULL/기본값 치환하지 않았다.

원본→실행 활용에서 현재 실제 소비한 것은 공개 저장 계약과 고정 이전 저장
소스의 좁은 알고리즘 패턴, 별도 검증한 NA 로그인 소스와 두 tuning CSV다.
원본 게임 그림/소리/지도/아이콘 소비는 **0**이다. 공개 catalog를 비공개 자료로
보고하지 않았다. 지도·효과·NPC를 임의 그림/공통값으로 채우지 않았다.
기준 서버 소스2770파일의 Git byte/명시 CRLF 변환을 대조했지만, 그 성공은
한국 원작이나 그래픽 클라이언트 로그인 근거가 아니다.

Work 시작 시 B001/HEAD `2eb791f...`를 읽고 시험 경계에서 B002/HEAD
`a74f4dd5322c67ec5ab5ee2b49d9f08299846f49`를 확인했다. 종료 경계의 최신 `d9817bf66ffd230b231e0584f367df3c9823fa73`에서도 B001/B002 고정 파일이 동일함을 확인했다.
B001 후보5·B002 후보154의 접근 가능한 메타데이터 길이/해시는 대조했다.
양 배치의 실제 비공개 ZIP·원본 참조는 미수신이므로 모두 DEFERRED,
ACCEPTED_FOR_P2/EXERCISED 필드는0개다. B002 혼합 스키마와 기존값 계약 누락도
별도로 기록했다. WORK_REQUESTS의 두 묶음만 전달 기록으로 남겼으며 다른 채팅의
자동 수신·응답을 가정하지 않는다. 실제 Work 응답은 요청001을 ACK했지만 전송 BLOCKED라고 기록했고, 제시한 Work-local 경로6개도 이 환경에서는 존재하지 않았다(WORK_RESPONSE_RECHECK.json). Work 브랜치 merge나 Work 파일 수정은 없다.
GEN001 실행 중에는 입력을 바꾸지 않았고 채택 세대를 만들지 않았다.

`ARCHITECTURE_DECISION.md`와 `storage/PROVENANCE.json`에 재사용·언어·엔진 근거가 있다.
Godot4.6.3/GDScript/compatibility는 이번 고정 후보이며 두 네이티브 플랫폼의
확정 결정은 보류다. 캐시 지문은7요소와 변환 코드 변경을 검사했지만 원본 렌더
캐시 재생성은 입력 미수신으로 NOT_RUN이다. 2000/2001 기본 프로필은 null을 유지했다.

실제 EXE/APK·화면·로그의 생성 위치와 SHA256은 PRIVATE_ARTIFACTS.json에 있다.
연결된 비공개 다운로드/업로드 수단이 없어 **바이너리·시청각 전달은 BLOCKED**다.
`/workspace` 경로는 생성 위치이며 다운로드 완료가 아니다. 원본을 담은 화면·
영상·오디오·게임 플레이 증거는 만들지 못했다. 자격증명·감사 원본·DB·키·폰트는
인계 ZIP이나 Git에 넣지 않았다. 공개 코드/비민감 결과만 Codex 브랜치에 저장했다.

정확한 다음 시작점과 P3 조건은 NEXT_P3.md를 따른다. 접근 가능한 비공개 바이트
경로, 실제 Windows/Android/Galaxy 환경과 허용된 무료 인증 시험 환경이 필요하다.
공통 STATE에는 이번 승인/부분 결과 반영을 제안할 뿐 직접 수정하지 않았다.

성능 원시값은 플랫폼 영수증의 `script_ready_us`, frame delta p95/p99와 Godot static memory다. 이는 전체 OS cold start·총 RSS/PSS·실제 입력 지연 또는 Galaxy 성능이 아니다. 소프트웨어 에뮬레이터 수치로 네이티브 성능 예산을 확정하지 않았다. 현재 시험 서버·에뮬레이터·자체 ADB는 종료했고 검수 앱도 종료했다. 추가 진행을 예약하지 않았다. 비공개 저장소의 최신 원격 tree도 재확인했으나 현재 전달본/원본 이름 대응이 없었고 실제 입력은 추가 확보되지 않았다(PRIVATE_ROUTE_RECHECK.json). 서명·계정·세이브·기존 archive 내용은 읽지 않았다.
