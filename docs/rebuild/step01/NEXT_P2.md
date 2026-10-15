# Codex 인계 — P2 위험 기술 검증 준비

작업 `BARAM_REBUILD_P0P1_001`, MASTER_PLAN v1.0. **이 파일은 검증 계획이며 P2 실행 승인이 아니다. 이번 승인 범위는 P0/P1에서 끝났다.** 새 게임·기준 서버·APK/EXE·배포 실행은 0회다. 다음 담당은 AGENTS → MASTER_PLAN → 최신 STATE → 이 파일 순서로 읽고, 기존 인계 커밋으로 reset하지 않는다.

## 재개할 정확한 위치

P0/P1 목록화를 다시 시작하지 않는다. `sources.jsonl`, `archive_members.jsonl`, `field_bindings.jsonl`, `issues.csv`, `RESTORATION_PROFILE.json`을 입력으로 삼는다. 먼저 아래 G0의 접근/지문을 확인하고, P2가 별도로 승인되었을 때만 독립 단위별 검증을 시작한다. 한국 목표시기 지도 정답이 없는 채로 P3 기본 세계를 확정하지 않는다. 검증 가능한 포맷/캐릭터/저장은 독립적으로 진행할 수 있고, 한 장애 때문에 모든 항목을 다시 수집하지 않는다.

현재 판정: **P2 부분 준비**. 한국 원본 바이트·재사용 파서·시청각 표·생성/저장 참고 소스는 준비되었다. 목표시기 한국 도시 지형의 독립 대응, 기술→효과→소리 의미·타격 시점, 실제 Windows/Galaxy 접근과 무료 인증환경은 미해결이다. 모든 P2 시험 결과는 `NOT_RUN`이며 아래 준비 상태는 실제 작동 결과가 아니다.

## G0. 입력과 접근 경로

지속 식별자는 Library 경로/ID와 GitHub 고정 커밋이다. 현재 `/workspace/scratch/8309e434ce3b/` 경로는 이번 세션의 작업 사본으로, 다음 Codex 환경에서 자동 접근된다고 가정하지 않는다. 원본은 공개 GitHub나 이 인계 ZIP에 들어 있지 않다. 연결된 비공개 파일 접근/기존 private 입력 전달 경로로 해당 ID를 가져온 뒤 해시를 대조한다. 접근 실패는 그 입력만 BLOCKED로 남긴다. 현재 Work가 이미 읽을 수 있는 파일을 사용자에게 다시 요청하지 않는다.

|입력|지속 위치와 source ID|SHA-256 / 고정 버전|
|---|---|---|
|한국 1.25|`/Baram1998Assets/KR_1.25_winbaram.zip`, LIB-009, `libfile_135f7d90220c81919353822363ea2395`|`62642ca3ef492f58947abb2c17cbae5b5a60d5f96fd146704b7d99d1aad3bcef`|
|한국 4.91|`/Baram1998Assets/KR_4.91_491v.zip`, LIB-010, `libfile_8c9b5125c46c8191b3e21428f6b2b1a4`|`f11e448db6478b1aca3a7dd47403bdef00cf873b203b14629b0215632190532f`|
|공유 추출본|`/어플/work_assets_shared_PRIVATE_final_20261014.zip`, LIB-036|`3bbcd5d69565bbe0d3bbe34149c59061dc3d1c5f3d27533e50a336cefd3e207c`|
|회수 UI|`/어플/work_ui_recovered_PRIVATE_002_20261014.zip`, LIB-040|`81ed6c992edbb18ef95f0673aeeec2932cf7c53883127546820af6529ec25c20`|
|사용자 사진|LIB-001/002/003 = 7476/7478/7480.jpg|각 SHA와 Library ID는 sources.jsonl. 사진을 실제 확인했으나 촬영 연도 UNKNOWN|
|NA 4.95 후보 설치본|`/Baram1998Assets/NA_4.95_Nexus495.exe`, LIB-014|`486f4684b76658d92eaf84aab77fe9be9489ea01de8264fe90d0040466620aaa`|
|기존 정적 파서|`tools/legacy_assets.py`, `legacy_installers.py`, `legacy_maps.py`|기존 저장소 `c919cf1bdffe0e318d4058dc3fc17be4a2844203`; OLD-PARSER-* 각 파일 SHA 고정|
|참고 서버|project1998/Project1998|`65cb3ef28f289ee35d19abfb6829d6120b9ec0cd`|
|보조 서버|unkmc/RTK-Server|`e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6`|
|도구 소스|TKViewer / TKMapper / EPFViewer|EXT-VIS-*에 각각 고정 ref, 실제 읽은 파일별 SHA. olds463는 독립 원전이 아닌 같은 계보 포크|

KR491 정적 경로: ZIP → `Install/DATA1.CAB` → `NWind.dat` / `NWind.snd`. DAT SHA는 `f8271a52d8dbde5601a0c7bf7460052376b2651930b6bc004eeb1ed20357bfc7`, SND SHA는 `003534e57b426971900f7ec39f5e65d3662fa5f32672cd0564d04680e31e300c`. 기존 EPF/PAL 131세트·WAV163개의 동일 입력은 확인했으므로 PNG 전수 재변환부터 반복하지 않는다. 같은 입력·파서·설정·범위의 결과만 재사용한다. 원본 hash만 같다고 변환 정확성까지 PASS로 승계하지 않는다.

## P2 검증 단위

|ID / 준비 상태|실제 입력과 검증 방법|독립 기대 결과 / 실패·취소|남은 조건|
|---|---|---|---|
|P2-01 한국 지도 / 부분 준비|LIB-009 MAP218개 중 실제 `99.map`은 member `LIB-009-M-f20743b49dae`, SHA `1c26eba1a3a8b159f9b2e54d5c421ae444d14552a860779d51c8e30042407273`. OLD-PARSER-MAP-TBL과 다른 도구를 판본에 맞게 비교. 목표 도시 지도 이미지는 LIB-010 동봉 자료를 후보로 대조.|치수/원점/타일·객체/벽/가림/출구 위치를 독립 자료와 비교. 필수 맵1개 누락·잘린 데이터 거부, 취소하면 이전 입력 유지. 등록/로드/도달/한국 고증을 별도 열로 기록.|1.25가 목표시기 지형인지 미확인. 4.91 설치 묶음에는 MAP 없음. NA495로 이름만 바꿔 통과 금지. ISS-001/004.|
|P2-02 캐릭터 합성 / 부분 준비|LIB-010 Body.epf/pal/tbl, Head.epf/tbl, Sword.epf/tbl, DrwOrder.tbl, MonsFrm.tbl. 각 member ID/SHA는 archive_evidence의 대표 연결표. 한 조합을 네 방향 걷기/공격/시전으로 비교.|몸/머리/무기/옷의 공통 기준점·레이어·팔레트·방향 일치. 누락 부품/범위 오류 식별, 취소/포커스 상실 때 입력 해제. 원본/독립 렌더 화면과 프레임별 대조.|현대 DSC/DNA/Motion.tbl을 한국491 필수 입력으로 강제 금지. DrwOrder token 의미·실행 속도는 미확인. 회수 UI clipping도 대조.|
|P2-03 효과와 소리 / 부분 준비, 의미 연결 차단|LIB-010 Effect.epf/tbl/frm, EffLayer.tbl, EffRange.tbl + NWind.snd163WAV. Effect.tbl 원본 텍스트에 front/back/repeat/frame/Delay/Alpha/Light가 있다. OLD-EFFECT-WAIT-PARSER와 EXT-VIS-003은 비교 후보.|원본 시퀀스와 frameID·지연·대기·앞뒤 레이어·색상을 대조. 입력→동작→명중→효과→실제 소리 출력→다음 행동을 캡처/파형/로그로 맞춘다. 반복 귀환10회·맵전환·취소·없는 소리에서 영구잠김/중복피해 없음.|Delay 단위/Alpha 해석·한국 기술/효과/소리 ID 의미·원본 타격 시점 미확인. sound003/160ms/1024ms/35프레임 fallback은 정답 아님. `play()` 호출만으로 청각 PASS 금지.|
|P2-04 로그인·생성·한글 / 부분 준비|LIB-010 DlgLogin/DlgNew01/Str_Kor, 사진3장·LIB-040, P1998 LoginSession/NameRules/CharacterFactory/LoginAuth/CharacterStore. 구형 화면과 오프라인 프로필·실제 인증을 다른 시험으로 둔다.|성별/머리/색 선택→취소→재선택→이름 조합→중복·오류→생성→종료/재접속. 한글 IME를 Windows/Android에서 별도 확인. 실제 직업Lv1평민·희망직업별도·미학습 상태.|P1998 NameRules는 ASCII. 한국 이름 규칙/생성 순서 원전 미확인. 서버 코드 확보는 한국/Android 완제품 확보가 아님.|
|P2-05 두 플랫폼 입력·UI·로컬 저장 / 입력계약 준비, 실행환경 미확인|새 작은 장면은 P2 승인 후에만 작성. 우측4패널/상태·같은 캐릭터·같은 콘텐츠/저장형식 사용. OLD-SAVE-STORE/OLD-CONTINUITY-JOURNAL의 좁은 검증·백업 패턴 참고.|실제 Windows EXE와 Android 앱에서 이동/공격/포털/탭/다중터치/뒤로가기·강제종료·저장재개. 손상/쓰기실패/중단에는 이전 정상 저장. 패널 조작으로 필드 공격/이동 오발 없음. 파일 내용/좌표 비교.|Godot4.6.3 GDScript/GL은 후보. 엔진/템플릿/JDK/SDK/기기OS/서명 metadata 고정은 P2. Linux·에뮬레이터·실제Galaxy 결과를 구분. 사용자 기존 앱/세이브와 별도 공존.|
|P2-06 같은 계정 순차 이어하기 가능성 / 계약 준비, 실제환경 차단|OLD-CONTINUITY-CLIENT/JOURNAL/CLOUD-README의 인증·revision/RPC 경로를 정적 참고. 실제 배포/DB 생성은 이번에 하지 않았다.|후속 별도 시험에서 인증된 같은 계정의 PC행동A→Android확인/행동B→PC확인. 오프라인 변경 대기·오래된 revision·전송취소/단절에 덮어쓰기 없음.|무료 서비스/프로젝트/스키마/HTTPS·실제 기기 접근 미확인. 파일 수동전달 시험은 이 시험의 PASS가 아님. P3 조기 왕복, P6 전체 검증 요구 유지.|

위 기대 결과는 시험 계약이다. 아직 원본과 새 게임의 허용 시간 오차·성능 예산을 측정하지 않았다. P2에서 장면/기기/조건을 고정하고 시작 시간, 입력 지연, frame-time p95/p99, 메모리 최고값·반복 이동 후 증가, 발열/음향 조건을 기록하여 예산을 결정한다. 렌더링 FPS와 원본 애니메이션 시간은 분리한다.

## 참고 실행본 후보를 준비하는 방법

Project1998은 **NA4.95 참고 서버**다. 정적 확보 43파일은 완전 checkout이 아니므로 그대로 실행할 수 있다고 보고하지 않는다. 전체 고정 checkout, .NET8 환경(`global.json` 8.0.100/latestFeature, SQLite8.0.10, BCrypt4.0.3, MoonSharp2.0.0), 클라이언트4.95의 실제 Inter.dat/NexusTK.dat·snd/Maps와 실행파일을 함께 고정해야 한다. 이후 별도 승인된 P2에서 격리 사본·빈 상태·loopback만 사용하고 양 프로세스에 `P1998_BIND=127.0.0.1`, 별도 `P1998_STATE`를 설정한다. 문서의 LoginServer2000/2001, 게임서버2005/2006과 실제 설정을 대조한다. `Tools/Program.cs`의 Inter.dat 패처와 LoginProbe는 방법 후보이며 이번에 실행하지 않았다. linked testclient는404여서 확보되지 않았다.

RTK는 Ubuntu16.04 i386/GCC/make/MySQL/Lua5.1 계열의 후대 구조 참고다. 정확한 RetroTK 클라이언트가 미확보여서 실행 우선순위는 낮다. 기본 예시 자격증명은 사용자 계정으로 사용하지 않으며 실제 비밀번호/세이브를 외부 코드에 제공하지 않는다. 로그인 성공만으로 한국판 지형·전투·음향·Android 오프라인을 입증할 수 없다. 두 저장소의 같은 계보 자료를 독립 근거 둘로 계산하지 않는다.

## 대량 구현으로 넘어가기 전 게이트

P2 결과는 원본 사실성 / 바이트·자산 활용 단계 / 실제 시험 결과를 분리한다. 한국 맵·캐릭터 합성·효과/소리·생성/한글·양 플랫폼 입력/저장의 각 장애를 해결하거나 구체적으로 제한해야 한다. 미실행 항목은 NOT_RUN, 환경상 불가는 BLOCKED다. 목표시기 한국 기본맵이 미확인인데 NA지형 대체로 P3/P4를 동결하지 않는다. 자료 보완 27개 OPEN은 issues.csv에 있으며, 모든 아이템 수치를 완성할 때까지 P2를 무기한 미루지 않는다.

지금 종료점은 **P0/P1 결과 저장과 이 인계 준비**다. P2 실행·새 게임 개발·기존 게임 수정·원본 공개·배포는 수행하지 않았다.
