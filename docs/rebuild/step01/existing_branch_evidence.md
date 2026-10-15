# 기존 조사·콘텐츠 브랜치 인수 증거

작업: BARAM_REBUILD_P0P1_001 · 계획 v1.0 · 정적 읽기만 수행. 게임/서버/빌드/배포/새 런타임 시험은 NOT_RUN.

## 실제 확인 범위

- 기존 브랜치 5개와 모바일 workflow가 고정한 별도 커밋 1개의 tree를 읽었다. 핵심 텍스트/JSON/좁은 소스 70개를 확보하고 Git blob identity를 다시 계산했다.
- 모든 원본 압축을 재해독하거나 기존 게임 전체를 감사하지 않았다. 공개 저장소의 기존 기록은 과거 기록이며 새 게임 원작 정확성/실행 PASS로 승계하지 않는다.
- 바이트/출처/소스 ID/한계 및 기계 판독 요약은 existing_branch_evidence.json에 있다.

## 브랜치 고정

| 범위 | 커밋 |
|---|---|
| content | c919cf1bdffe0e318d4058dc3fc17be4a2844203 |
| restoration | 2775b1166a760b6a1757f09f2faf1e799d3fd59e |
| world | 0ebfbe1514700a8afc00f71b20b9f88b23eb075f |
| community | 0aac06f7c713e5b1d16e95e101c106847bc56ed4 |
| core | ac08964cbbc2ae1a6499a760de7d6b81c45c3f27 |
| mobile | 2bb4ec55fa8ccb347b11d2bf2532ae4d4806b76a |
| mobile_workflow_pinned_input | 2bb4ec55fa8ccb347b11d2bf2532ae4d4806b76a |

## 실제 패키지 13개

ASSETS001~003, CONTENT001~010이 존재하며 이후 패키지는 고정 tree에 없다. manifest 해시와 인덱스 수량 13/13을 대조했다. 이 수량은 원전 정확성이나 실행 중 활용 수량이 아니다.

| 패키지 | 정의/수정 수 | 이전 가져오기 기록 |
|---|---|---|
| WK-ASSETS-001 | asset:992 | PARTIALLY_IMPORTED |
| WK-CONTENT-001 | advancement:12, class:5, drop_group:269, economy:1, enhancement:1, growth:401, item:535, map:64, monster:269, npc:59, quest:33, recipe:1, shop:38, skill:199 | IMPORTED |
| WK-CONTENT-002 | item:356, monster:36, npc:45, shop:20 | IMPORTED |
| WK-CONTENT-003 | drop_group:51, item:66, map:327, monster:51, npc:96, quest:62, recipe:192, shop:24 | IMPORTED |
| WK-CONTENT-004 | class:4, item:12, npc:4, quest:4, skill:211 | IMPORTED |
| WK-ASSETS-002 | asset:47 | IMPORTED |
| WK-CONTENT-005 | class:4, item:24, npc:4, quest:8, skill:16 | NOT_RUN |
| WK-ASSETS-003 | asset:8 | NOT_RUN |
| WK-CONTENT-006 | skill:7 | NOT_RUN |
| WK-CONTENT-007 | item:23, npc:14, recipe:22 | NOT_RUN |
| WK-CONTENT-008 | item:16, npc:12, recipe:16 | NOT_RUN |
| WK-CONTENT-009 | drop_group:70, item:12, map:90, monster:70, npc:104, quest:16 | NOT_RUN |
| WK-CONTENT-010 | item:3, npc:3, recipe:3 | NOT_RUN |

누적 CONTENT009 기록은 item675/map386/monster390/npc259/shop62/skill227/recipe231이며 CONTENT010 신규 item3·recipe3, NPC 수정3이다. 따라서 기존 대장의 결과는 item678/recipe234다. 이 작업에서 전체 payload를 병합하거나 게임 활성 수를 측정하지 않았다.

## 기능별 발견과 다음 작업

### OLD-F01 — 한국 지도와 NA 지도 후보를 분리

기존 논리386/물리385 정의가 한국 지형/도시 좌표의 근거가 되지 않는다. 원본 지도1750 대장은 북미4.95 계열이다.

- rule.map.overlay: Original NA geography, not verified KR1998 layout
- rule.exp2.region: NA495 geometry is not verified Korean1998 geography; square dimensions inferred
- source-maps/000.jsonl original_map_id 0: NA-4.95/Maps/TK0.map sha256 88a5d13247dcff1245bbb818a67820ab421b064e17acb1fe6fef12ba607a2315, 193600 bytes

자료 ID: OLD-WK-CONTENT-001-PROVENANCE, OLD-WK-CONTENT-003-PROVENANCE, OLD-SOURCE-MAP-SAMPLE

미활용/공백 분류: 버전 불일치. 다음 작업: KR 원본 MAP/member와 독립 스크린샷·공식 좌표를 연결. NA 후보는 포맷 검증에만 사용. 한국 맵 P2는 이 연결을 별도 확인.

### OLD-F02 — 전직·네 직업 자료는 실제로 나뉘나 광범위 fallback 존재

모든 직업 자료가 아예 없었던 것은 아니다. 생성/학습 제한이 이 목록을 소비하는지와 식별 실패 시 전직업 허용이 별도 문제다.

- class arrays: novice0, warrior33, rogue57, mage85, poet51 skill IDs
- build_content.py:348-349: 직업 문자열에서 아무 직업도 찾지 못하면 jobs=JOBS.copy()
- class starter.selected_job_applies_from_level=6 vs current requested Lv5 guild transition requires semantic review

자료 ID: OLD-WK-CONTENT-001-CONTENT-000, OLD-WK-CONTENT-001-CONTENT-001, OLD-CONTENT-GENERATOR

미활용/공백 분류: ID 미식별 / 지원 코드 연결 미검증. 다음 작업: 직업 미식별 기술은 UNKNOWN/quarantine. Lv1 평민 미학습·Lv5 전직·다른 직업 기술 거부를 데이터 계약과 P3 회귀시험에 넣는다.

### OLD-F03 — 기술 효과의 원본 시간표와 기술 의미 대응을 분리

소스의 front/back/repeat/delay는 쓸 수 있지만 특정 한국 기술의 정확한 모양·타격시점은 미확인이다.

- effect 70 front: frame687..696 each100ms then frame-1 700ms; back starts frame-1 1000ms
- ASSETS003: 8 recovered timelines,139 entries,17 wait entries; -1 blank wait interpretation INFERRED/native NOT_RUN
- CONTENT004 effect association: element/purpose-compatible pool; individual historical skill correspondence unverified
- build_content.py:388 impact_delay_ms=160 for base skills

자료 ID: OLD-WK-ASSETS-003-CONTENT-000, OLD-WK-ASSETS-003-RECOVERY-SUMMARY, OLD-WK-CONTENT-004-PROVENANCE, OLD-CONTENT-GENERATOR

미활용/공백 분류: ID 미식별 / 버전·시간 의미 미검증. 다음 작업: effect.tbl signed parse만 좁게 재사용; 기준본/영상의 기술 ID와 시간축을 P2에서 비교. 160ms 공통 타격값은 역사값에서 제외.

### OLD-F04 — 소리 보유와 실제 호출 연결의 큰 차이

파일 부재만의 문제가 아니라 소리 ID 의미/호출 조건/시점이 미식별인데 공통 소리를 선택한 상태다.

- 163 sound definitions: CONTENT_DEFINED_REFERENCE1,DECODED_UNUSED162
- sound352 original metadata: sounds/352.wav SHA256 541c5d6c40535d9dbe321e688a608dde7c1768bda867b20f4e43f66bb7649dd4; mono11025Hz16bit4592 samples416ms
- base skill animation assigns sound.003, or first available sound fallback

자료 ID: OLD-CONTENT-SUMMARY009, OLD-WK-ASSETS-001-CONTENT-018, OLD-CONTENT-GENERATOR

미활용/공백 분류: ID 미식별 / 지원 코드 연결 미검증. 다음 작업: 파일 ID별 듣기 표본과 원본 행동/서버 message 소리값을 연결; 일반공격/시전/명중/BGM을 구분, native output timing NOT_RUN.

### OLD-F05 — 상점별 자료가 역할 기반 추정으로 보완됨

기능 가능한 재고를 생성한 것이며 당대 NPC별 원전 재고·서비스표를 복원한 근거가 아니다.

- build_content.py:312-319: shop role filters all buyable items, infinite stock, empty=>acorn; smith repair multiplier .001
- build_content.py:475-480: remaining buyable items added to first grocer/craft shop
- NPC dialogue/placements are authored Korean offline completion

자료 ID: OLD-CONTENT-GENERATOR, OLD-WK-CONTENT-001-PROVENANCE

미활용/공백 분류: ID 미식별 / 의도적 추정 보완. 다음 작업: NPC+era별 buy/sell/repair/rest/craft 관계를 원전 필드로 분리. 임의 재고/도토리 fallback/수리배수는 기본 복원 프로필에서 채택 보류.

### OLD-F06 — 008/010의 수정 충돌은 적용 순서로 해결되지 않음

공개 패키지13개 존재와 전부 안전하게 결합 가능은 다르다.

- wk.npc.exp2.dry.51.smith and wk.npc.exp2.forest.11.smith; services/dialogue 4 fields conflict
- known-state merge proposal exists; original immutable packages preserved

자료 ID: OLD-CONTENT-WORK-STATE, OLD-NPC-008-010-CONFLICT

미활용/공백 분류: 패키징·버전 충돌. 다음 작업: 기본 역사 프로필에서 authored extension 필요성부터 결정. 채택 시 두 입력 manifest 고정·known-state guard·원자 병합. 새 게임 적용 NOT_RUN.

### OLD-F07 — 기존 숫자 평균과 지역별 대체 공식은 채택 보류

과거 평균 정책은 현재 정본의 지역·연도 분리 원칙으로 대체한다. 그림을 가진 클라이언트가 서버 수치까지 증명하지 않는다.

- C04 squirrelXP5/10 separate dated captures; historical implementation had mean7.5
- C13 guild coordinates1999/2001 differ; relocation date unknown; do not average
- RUNTIME_INPUT_RULES initialHP/MP = P1998 external replacement; repair NA/RTK/Mithia options unselected

자료 ID: OLD-KR-CONFLICTS, OLD-RESTORATION-RULES

미활용/공백 분류: 버전 불일치 / 근거 부족. 다음 작업: 기본 도시/시기 프로필을 PROVISIONAL로 만들고 원문 날짜 필드 유지. 동귀어진/백호왕800/길드명 독립 보류.

### OLD-F08 — 좁은 파서 세 개는 재사용 후보

파일 포맷 처리 기능은 독립 모듈이며 전체 main.gd와 분리해 쓸 수 있다.

- DAT bounds and duplicate names; EPF stencil and signed frame rectangle; PAL animation ranges
- MAP headerless byte-count requires separately attributed dimensions; TBL bases and static-object columns
- InstallShield v4 raw DEFLATE and Wise stream CRC reader; no installer execution

자료 ID: OLD-PARSER-DAT-EPF-PAL, OLD-PARSER-MAP-TBL, OLD-PARSER-INSTALLER, OLD-THIRD-PARTY-NOTICE

미활용/공백 분류: 새 런타임 미연결. 다음 작업: 입력 SHA+parser hash가 같을 때 기존 추출본 재사용. KR 입력/독립 MIT viewer 표본을 P2에서 대조; 기존 claims는 재실행하지 않음.

### OLD-F09 — 저장·캐시 유틸은 범위를 좁혀 재사용

저장 검증·백업 패턴은 후보지만 계정 연동이나 OS atomic-replace 완료를 뜻하지 않는다. 캐시 코드를 그대로 가져오면 변환코드 변경 누락이 재발할 수 있다.

- save_store schema2 payload SHA,16MiB limit,pending/backup/future format refusal
- cache manifest has format/content_version/source_world_sha256/binary SHA, but omits converter source/config/toolchain fingerprint

자료 ID: OLD-SAVE-STORE, OLD-CACHE-BUILDER, OLD-CACHE-READER

미활용/공백 분류: 지원 코드 미검증 / 캐시 지문 부족. 다음 작업: 새 save schema adapter·Windows/Android rename failure/interrupt tests; cache key must include input/parser/compiler/config/palette/map generation hashes.

### OLD-F10 — 기존 Android/Windows 도구체인과 클라우드의 준비 범위

구현된 HTTP/Auth/RPC 코드가 있어도 실제 배포·인증·계정 왕복이 준비됐다는 뜻은 아니다. 이전 file transport/fixture 검사를 cloud PASS로 승계하지 않는다.

- Godot4.6.3 stable; GDScript, gl_compatibility, 960x640 viewport
- workflows in core use separate mobile commit2bb4ec55; generated export_presets rather than tracked file
- android_ci JAVA_HOME or Java17 path, ANDROID_HOME external SDK, no pinned platform/build-tools version; arm64 player and x86_64 verification; non-Gradle export
- signing supplied by private vault; actual private identity not opened in this task
- cloud README: deployment pending; no project/schema/player account provisioned at pinned commit; real HTTPS and Galaxy remain unverified

자료 ID: OLD-PROJECT-GODOT, OLD-CORE-ANDROID-PRIVATE-CHECK, OLD-CORE-WINDOWS-CONTINUITY-PRIVATE-CHECK, OLD-ANDROID-EXPORT, OLD-CONTINUITY-CLIENT, OLD-CONTINUITY-JOURNAL, OLD-CLOUD-README

미활용/공백 분류: 실행환경 접근 미확인 / 서비스 미배포. 다음 작업: P2 Godot/language/export candidate as above; verify actual SDK/template hashes/signing metadata only when builds authorized. P3/P6 free real Auth+RPC deployment and same account roundtrip separately.

## P2에 넘길 입력 후보

| 검증 단위 | 실제 입력 후보 | 독립 기대 결과와 남은 조건 |
|---|---|---|
| 한국 맵 | KR 원본+도구 입력은 원본 담당 카탈로그와 결합; 기존 NA495 map sample, legacy_maps.py는 포맷 비교만 | 당시 한국 지도/스크린샷/동일 시기 좌표; NA 지형에 한국 이름 부착 금지 |
| 캐릭터 합성 | ASSETS001 body/head/sword 모델, 원본 발 기준점/방향 N,W,S,E·drworder 표 | 같은 외형의 원본 4방향과 레이어 비교; 100ms는 일부 기존 추정값 |
| 효과/소리 | effect070 등 front/back/repeat/delay, -1 wait 파서; sounds352 WAV 식별자/메타데이터 | native 또는 영상 비교 필요; 개별 기술 효과/소리 의미·실제 출력 시점 미확인 |
| 로그인/생성 | Project1998는 외부 담당 조사; 옛 화면·로컬 프로필·실제 Supabase Auth 세 행 유지 | 기존 cloud 코드 있음/배포 pending; 파일 이동 시험으로 인증 성공 보고 금지 |
| Windows/Android 저장/입력 | Godot4.6.3 GDScript 후보, schema2 save_store, core CI가 고정한 mobile2bb4ec55 | 새 게임 장면/PC·Android native 결과 NOT_RUN, 실제 Galaxy 미확인, SDK pin 추가 |

13개 패키지 자료는 보존하되 새 기본 복원 프로필에 자동 채택하지 않는다. 특히 NA 지형, authored quest/equipment/advancement, 공통 sound/impact fallback, 직업 미식별 전직업 허용은 기본 고증값에서 제외하고 별도 후속 후보로 남긴다.

## 이번에 실행한 정적 검사

- Git blob identity: 70개 실제 텍스트 PASS.
- manifest 인덱스 SHA256/수량: 13개 PASS.
- manifest member 경로/크기: 415개 tree metadata 참조 PASS. 원본 payload 전수 SHA 검사가 아니다.
- 실제 읽은 manifest member SHA256: 16개 PASS.
- finding→source ID: 10개 finding 참조 PASS.
- 서버 실행·새 게임 시험·Windows/Android/Galaxy·실계정 동기화: 모두 NOT_RUN.

## 읽지 않은 범위

- Full original client archives in this assignment; delegated source preservation inspection remains authoritative
- Every package JSONL record or all original resource bytes
- Current installed APK/Windows provenance beyond specified refs
- Private signing bytes, private vault files, actual account passwords/tokens
- Full historical source originals behind inherited research reports
- Complete original gameplay video/audio or exact impact measurements
