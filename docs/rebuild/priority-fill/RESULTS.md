# 보유 자료 적용·부족 자료 재감사 결과

**PARTIAL — 실제 데이터 선정·P2 연결·Linux 검수와 잔여 재집계를 수행했다. P3/P4 전체 게임·운영 배포·main 병합은 미착수다.**

작업 ID: BARAM_REBUILD_WORK_PRIORITY_FILL_001  
시작 HEAD: dbb88a12d95b369c312b66ec86b7c19182e2481e  
작업 브랜치: work/rebuild-priority-fill-20261016  
실행 입력: WORK-PRIORITY-GEN002 / Godot4.6.3.stable.official.7d41c59c4

## 실제로 채운 것과 남은 경계

| 대상·분모 | 전 | 후 | 실제 실행과 남은 공백 |
|---|---|---|---|
| 한국 MAP218개 | 원본3개 연결·렌더 | 원본198개에서 독립64×64 저장청크250개 연결 | 250개 실제 그리기. 19개 비정상 길이+MAP4 참조오류 격리. 도시명·청크 세계배치·사냥터 입구·출구/귀환은 미확정 |
| 효과128개 | 허용25개 중 ID72는 빈 시퀀스, 실제 비어 있지 않은 후보24개 | 전체 프레임119개·유효 구간8개 검수 가능, ID72 차단 | 대표5개(0/1/70구간/91/127) 화면 렌더와 종료 확인. Light 끔·Alpha 일반합성·한 번 순회는 재구성. 원작 기술·반복·타격·음향 의미는 미확정 |
| WAV163 ID | UI 선택번호가 효과 등과 묶여25개만 도달 | 별도 ID 검색·목록·재생163개 | Godot 디코더163개 통과. 001/085/412의 실제 가상 믹서 출력3개 확인. 나머지160개 출력 및 기술별 대응은 미확인. 파형158종이어도 ID163개 보존 |
| 공식 아이템 그림105건 | 선정 메타데이터만, 실제 화면0건 | 원문105개 대응·PNG93종 실제 연결 | 105건 모두 필드/가방/장비 썸네일 검수3개 위치에서 그림. 2001 대응100건 CORROBORATED, 2000전용5건은 별도판본. 문서 그림을 실제 원작 인벤토리/바닥/착용 그림으로 확정하지 않음 |
| 기술·NPC 규칙 | 전역 기본 프로필null, P2 소비 없음 | 2001 기술188행·NPC22서비스 계약 | 실제 Godot 읽기 전용 조건 소비. 평민Lv1·미학습·Lv5전직 하한 보존. 직업·레벨이 맞아도 실제 학습/자원거래는 BLOCKED/P3 미구현 |
| 기존 충돌15건 | 2000/2001 대안만 보존·미선택 | 2001 작업용 후보15개 선택 | 평균 사용0. 동일 시기 내 진마반지 가격 충돌은 미해결. 더 넓은 시대 차이82건도 보존 |
| Work159후보 | 6개 검수 제약, 실제 패치0 | 70선정·58타프로필·28참고·2가설·1충돌 | 선정70개는 몬스터24/상점42/학습4개 관계 메타데이터. 실제 P3 동작으로 승격하지 않음 |

기존 자료를 재사용했으며 새 원문 전수 재수집은 하지 않았다. 원본 선정의 우선순위보다 먼저 시대·권역·필드 적격성을 확인했다. 2001 가이드 규칙, KR1.25 저장블록, KR4.91 원본 그림/소리는 서로 다른 진단 프로필로 유지했다. 이를 모두2001 한국판 역사정본으로 합치지 않았으며 전역 historical_profile_default는null을 보존했다.

## 전후 집계와 정확한 단위

| 지표 | 전 | 후 | 단위·주의 |
|---|---:|---:|---|
| 기존 정규화 원문선정 행 | 2,309 | 2,309 | 기존2000/2001등 출처 범위. 이번 새 자료 확보 수가 아님 |
| 이번 작업용 원장의 원본범위 채택 | 0 | 629 | 새 프로필의 필드 선정행. 263문서/충돌필드+198한국1.25 저장자료+163WAV+5아이콘2000판본. 목표시기 원작 게임629개 완성 아님 |
| 이번 원장의 교차근거 채택 | 0 | 100 | 2000 문서 그림과2001 항목 대응. 원작 인벤토리ID 증거와 다름 |
| 이번 원장의 재구성·추정 채택 | 0 | 197 | 중립효과127+Work관계70. BALANCE_ESTIMATE 신규 임의수치0 |
| 이번 원장의 실제 코드 연결 | 신규 원장 없음 | 818 | EXERCISED536+BOUND282. 단위는(field_id,content_id)이며 15충돌은 기존기술과중첩 |
| 이번 원장의 실제 소비·검수 | 신규 원장 없음 | 536 | 읽기전용 규칙225필드(210고유계약+15충돌중첩)+아이콘105+MAP198+효과5+음향3 |
| 선정됐지만 미연결 | 신규 원장 없음 | 108 | 공식 메타38+Work관계70. private패키지에 담았다는 것만으로 소비를 주장하지 않음 |
| 연결 후 해당 출력 미실행 | 별도 자산표 참조 | 282 | 효과122+음향160. 전수 디코딩과 실제 출력은 구분 |
| 전 분야 넓은 공백 유형 | 137 | 137 | 150요구/35바인딩그룹 보존. 전체개체수UNKNOWN이므로 부분지원을 전체필드 완료로 삭제하지 않음 |

이번 선정926행은 고유content_id864개이며, 개체·필드·관계·저장블록 등 단위가 섞여 있다. 전체 원작 복원율을 계산하지 않는다. 미해결 CSV883행은137필드유형+5기존실패군+20격리MAP+123효과대기+160WAV출력대기+377문서아이템이미지공백+61Work비선정처분이다. 서로 겹치는 진단 범위이므로883개의 독립 게임 기능이 부족하다는 뜻도 아니다. 2001문서아이템477개 중377그림 미연결은 확보 문서의 분모이며 전체 원작아이템 분모가 아니다.

`BASELINE_COVERAGE.json`과`AFTER_COVERAGE.json`은 동일137필드ID·기존 원문해시를 대조했다. 남은 범위와 이미 확인한 부분의 use/test는 별도 열이다. 예를 들어 NPC서비스22개를 읽었어도 나머지 전체NPC 외형·좌표의 unknown범위는 유지한다.

## 실제 시험과 수정한 실패

| 시험 | 실행/재사용 | 결과·범위 |
|---|---|---|
| 최종 Linux GUI | 이번 실행 gui-run04 | 554검사/실패0. OpenGL llvmpipe 실제 픽셀 렌더·Pulse 가상 출력. 소스/입력 전후 동일 |
| 기존 GEN003 영향 회귀 | 이번 현재코드 실행 original-regression01 | 47검사/실패0. 네방향/몸·머리·무기·방패, 장비교체·해제, 원본효과, 새 격리 저장·백업·좌표/전리품 보호 |
| 효과 GDScript | 이번 실행 | 386검사/실패0. 전체128의 선택·종료·음수/누락/불안전 입력 거부. 픽셀은 대표5개와 별도 |
| 직업·NPC GDScript | 이번 실행 | 17검사/실패0. 188기술·22서비스 계약 읽기. P3실학습/거래는 거부/보류 |
| 효과/Android 관측기 음성시험 | 이번 실행 | Python8+6PASS. Android6개는 합성 명령/판정 시험이며 실제 Android 재시험이 아님 |
| 지도 출력 | 이번 실행 | 1620PNG 구조/CRC/실디코딩0실패,1871산출 파일 해시 일치. 기존 MAP1/99/100의 그림·기하 동일 |
| 배포용 입력 복원 | 이번 실행 | ZIP4,237파일/126,278,424bytes를 새 경로에서 원장·파일SHA까지 확인. 실행을 반복했다는 뜻은 아님 |

지도v1에서4개 floorPNG가 IDAT뒤에서 잘렸고 전수검사기가 거부했다. 원본은 그대로이며 v1 실패·정확한ID/해시는`MAP_V1_PNG_FAILURES.json`에 보존했다. BytesIO인코딩→PNG/픽셀검사→fsync/atomic replace→읽기재검증으로v2를 생성했다. 하위 쓰기 계층 원인은UNKNOWN이며, 해시만 맞으면 정상PNG라는 잘못된 판정은 하지 않는다.

첫 GUI 실행은551검사 중 음향3개가FAIL이었다. 최초250ms 타이머의 실제 대기가약23~25ms로 짧았고 초기오디오 시작이 늦었다. 재생위치/믹서프레임/벽시계를 기록하고 관측구간을 늘린 새 시험에서 동일 peak판정 기준을 통과했다. gui-run02 실패를 지우지 않았으며 run03/04의 별도 증거로만 갱신했다. WAV 메타데이터의 UTF-8경고는 로그에 보존했고 실제PCM출력과 별개로 관리한다.

확장된지도 조회는 지연 로드하며 텍스처캐시에16,777,216pixel 상한을 적용했다. 전체250청크를 바꿔 그린 뒤 상한을 실제 검사했다. 메모리 상한은 원작정확성이나 실제Galaxy 성능PASS가 아니다.

## 기존 실패·환경 차단은 그대로다

- Android GEN003: FAIL_NO_REPORT 유지. 원본 로그는 Godot/Activity/graphics 증거가 부족해 원인UNKNOWN. 현재SDK/adb없음으로 새Android 실행은BLOCKED. 실행확인·전체로그·PID·보고서 경로·조기중단을 관측기에 추가했으며480초 무작정 재시도하지 않았다.
- Windows: 빌드성공의 역사와 native 실행환경 branch규칙 차단 보존. 보호규칙을 바꾸거나 허용브랜치로 우회하지 않았다. 새Windows/Android 설치본은 제작하지 않았다.
- Wine 저장12FAIL: CreateSymbolicLinkW stub 관련 기존 진단 보존. nativeWindows에서 실제링크 생성 확인 후 동일 저장보호 시험이 필요하다.
- 마스크3건: DLGLOGIN.epf:0 / DLGNEW01.epf:0 / DLGPASS.epf:0, 선언폭316대신 run폭318. frame0·잘라내기·빈그림으로 대체하지 않음.
- NA원천참조154FAIL, 실제IME·Galaxy·실물스피커 청취·실계정HTTPS왕복 NOT_RUN/BLOCKED 유지. Linux성공으로 승격하지 않음.

## 중요한 미해결 상위20건

정확한 필드ID/원본ID가 없는 것은UNKNOWN이다. 아래 next자료와방법을 수행한 뒤 영향범위만 재시험한다.

### 1. GAP-H-era_city

- 원본/관련ID: KR125:map:0, KR125:map:208
- 원인·영향: IDENTITY_UNKNOWN / KR1.25 저장블록을 읽어도 1998~2001 국내성/부여성의 지명·건물/문 좌표계가 확정되지 않음 / 도시·사냥터 위치를 원작과 같다고 주장할 수 없음
- 필요 자료: KR1.25 index.json의 map_inventory에 기록된 실제 MAP218개 목록 + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍; field=era_city
- 다음 방법·담당: 복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사; 공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지 / Work: 지도 해독 / P2-01

### 2. GAP-H-exits

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: SOURCE_MISSING / 출구 목적지·조건·왕복 짝을 포함한 한국 서버 원문 없음; 실행 지도 exits는 빈 상태 유지 / 검수 지형을 월드/사냥터로 연결할 수 없음
- 필요 자료: KR1.25 index.json의 map_inventory에 기록된 실제 MAP218개 목록 + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍; field=exits
- 다음 방법·담당: 복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사; 공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지 / Work: 지도 해독 / P2-01

### 3. GAP-H-return_by_country_direction

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: SOURCE_MISSING / 국가·방향별 비영사천문 귀환의 실제 지도ID/좌표·제약 미확정 / 귀환 동작은 P3 연결 불가
- 필요 자료: KR1.25 index.json의 map_inventory에 기록된 실제 MAP218개 목록 + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍; field=return_by_country_direction
- 다음 방법·담당: 복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사; 공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지 / Work: 지도 해독 / P2-01

### 4. GAP-H-collision_occlusion

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: IDENTITY_UNKNOWN / 원본 EXE 유래 충돌 predicate는 실행되지만 서버 활성범위·가림과 지형 의미의 독립 관측 미완료 / 경계 이동/객체 뒤 가림/세계 이어붙임에 추가 검증 필요
- 필요 자료: KR1.25 index.json의 map_inventory에 기록된 실제 MAP218개 목록 + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍; field=collision_occlusion
- 다음 방법·담당: 복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사; 공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지 / Work: 지도 해독 / P2-01

### 5. ASSET-BLOCKED-MAPS

- 원본/관련ID: 3, 4, 57, 74, 121, 150, 154, 160, 162, 196, 199, 203, 257, 262, 263, 265, 266, 280, 281, 283
- 원인·영향: DECODE_FAILED / 한국 MAP218 중20개 원본을 격리:19개 비정수 저장블록 길이,MAP4 참조 범위 오류 / 잘린 prefix/기본 타일로 바꾸지 않고 해당 원본 해독 보류
- 필요 자료: KR1.25 index.json의 map_inventory에 기록된 실제 MAP218개 목록 + 당시 국내성/부여성 사대문/건물/사냥터 좌표와 서버 출구쌍; field=tiles_objects
- 다음 방법·담당: 복수64격자/짧은 MAP을 별도 해독; 도시명 확정·출구 왕복·가림을 독립 검사; 공식 PCX와 원본 MAP 대응을 검증; NA 지명 교체·임시 포털·village 고정 금지 / Work: 지도 해독 / P2-01

### 6. GAP-A-body_head_clothes_weapon

- 원본/관련ID: KRO-NPCLOOK-태백, KRO-NPCLOOK-해두, KRO-NPCLOOK-마로, KRO-NPCLOOK-진선
- 원인·영향: IDENTITY_UNKNOWN / 이름이 있는 원본 화면4개와 KR491 부품 native look의 개별 대응 미확정 / NPC별 외형 렌더와 장비 조합 미구현
- 필요 자료: KR491 Monster.epf/MonsFrm.tbl + kr_official_npc_appearance.jsonl의 KRO-NPCLOOK-*4개 화면; NPC 이름별 원본 look/좌표; field=body_head_clothes_weapon
- 다음 방법·담당: NPC별 화면 crop과 부품/프레임을 대응하고 원본 look 미상은 개별 재구성으로 격리; 한국 NPC 개별 외형/좌표/부품 ID는 화면과 자산을 함께 확인; 같은 역할 외형 일괄 배정 금지 / Work: NPC 바인딩 / P2-02

### 7. GAP-A-coordinate

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: IDENTITY_UNKNOWN / NPC22개 서비스 계약은 소비했지만 실제 한국 지도 좌표·실내/방향·look 연결 없음 / 서비스 패널이 월드 NPC 배치를 의미하지 않음
- 필요 자료: KR491 Monster.epf/MonsFrm.tbl + kr_official_npc_appearance.jsonl의 KRO-NPCLOOK-*4개 화면; NPC 이름별 원본 look/좌표; field=coordinate
- 다음 방법·담당: NPC별 화면 crop과 부품/프레임을 대응하고 원본 look 미상은 개별 재구성으로 격리; 한국 NPC 개별 외형/좌표/부품 ID는 화면과 자산을 함께 확인; 같은 역할 외형 일괄 배정 금지 / Work: NPC 바인딩 / P2-02

### 8. GAP-B-spoken_text

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: SOURCE_MISSING / 공식 서비스 설명은 실제 대사가 아니며 실패/거절/취소/재방문 분기의 한국 원문 미확보 / NPC 대화망은 원작값 또는 명시 재구성으로 별도 구현 필요
- 필요 자료: 1998~2001 한국 길드/주막/대장간의 실제 대화창·선택지 화면 및 실패/거절/재방문 원문; field=spoken_text
- 다음 방법·담당: 공식 서비스 설명과 실제 발화를 분리; 기존 한국어 재구성4개를 별도 대화 계약으로 연결; 원문·공략 설명·재구성 구분; 전체 상태 그래프가 없으면 새 기준본에서 조건별 관측 / Work: 대화 자료 / P2 계약/P3 대화

### 9. GAP-C-spawn_area_count_cap

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: SOURCE_MISSING / 층별 스폰 영역·수량·상한·리스폰 및 AI 경계의 한국 서버 자료 없음 / 몬스터 설명24개 재구성 관계가 사냥터 전투 실행은 아님
- 필요 자료: kr_official_core.jsonl monster행 + 한국 서버/영상의 층별 리스폰·수량·AI·독립/배타 드롭 규칙; field=spawn_area_count_cap
- 다음 방법·담당: 명시 XP/아이템 관계만 선택하고 미관측 확률은 UNKNOWN; nativeID와 변종을 독립 대응; 공식 표의 문서값과 NA 참고 소비 코드를 분리; 원작 확률/독립·배타/수량이 없으면 UNKNOWN / Work: 전투 데이터 / P2 계약/P3 전투

### 10. GAP-C-probability_model

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: SOURCE_MISSING / 명시 확률 일부 외에는 퍼센트/가중치·독립/배타·조건·no-drop 모델 미확정 / 대부분 드롭을 원작 확률로 실행할 수 없음
- 필요 자료: kr_official_core.jsonl monster행 + 한국 서버/영상의 층별 리스폰·수량·AI·독립/배타 드롭 규칙; field=probability_model
- 다음 방법·담당: 명시 XP/아이템 관계만 선택하고 미관측 확률은 UNKNOWN; nativeID와 변종을 독립 대응; 공식 표의 문서값과 NA 참고 소비 코드를 분리; 원작 확률/독립·배타/수량이 없으면 UNKNOWN / Work: 전투 데이터 / P2 계약/P3 전투

### 11. GAP-D-repair_price

- 원본/관련ID: GAP-D-success_rate, GAP-D-failure_loss_or_keep
- 원인·영향: SOURCE_MISSING / 수리비 공식·제작 성공률·실패 소모의 한국 원문 불충분;제작7행은 원문 사실만 선정 / 제작/수리의 금전·재료 변경은 P3에서 별도 계약/시험 필요
- 필요 자료: kr_official_crafting_facts.jsonl KRO-CRAFTING_FACT-*; 해당 NPC 수리 가격·실패 소모·성공률 화면; field=repair_price
- 다음 방법·담당: 원문 재료/결과만 채택; 성공률·수리공식의 근거 없는 기본값 금지; 현대 강화·옛 조합·퀘스트 업그레이드·수리 분리; 성공률 임의값 금지 / Work: 경제 데이터 / P2 계약/P3 제작

### 12. GAP-F-delay_raw_unit

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: DECODE_FAILED / 프레임/모션 raw Delay의 단위·행동 전환·중단 의미가 미해석 / 130ms/실험 지연을 원작 모션 시간으로 승격할 수 없음
- 필요 자료: KR491 DrwOrder.tbl/Body.tbl/MonsFrm.tbl + 같은 행동의 한국 당시 영상 프레임·시간; field=delay_raw_unit
- 다음 방법·담당: 네 방향/무기 합성의 추론과 원본 시간 단위를 분리; 마스크3개 최소 실패 샘플 해독; 한국 원본 표와 네 방향 행동을 대조; 이미지 추출 성공과 모션 의미·속도 복원 분리 / Work: 합성/파서 / P2-02

### 13. FAILURE-kr491_masks

- 원본/관련ID: DLGLOGIN, DLGNEW01, DLGPASS
- 원인·영향: DECODE_FAILED / 원본 마스크 run폭과 선언폭 불일치3건;잘라내기/frame0/빈이미지 대체 금지 / 원본 로그인·일부 생성/비밀번호 화면 해독 차단
- 필요 자료: docs/rebuild/p2-work/UI_PALETTE_DIAGNOSIS.json
- 다음 방법·담당: 최소 실패 샘플/전체 로그를 보존하고 새 동일 플랫폼 시험 결과로만 현재 상태를 갱신 / Work: 플랫폼/파서 / P2

### 14. GAP-G-sound_id

- 원본/관련ID: KR491:sound:001, KR491:sound:085, KR491:sound:412
- 원인·영향: IDENTITY_UNKNOWN / 163WAV ID를 조회/해독하지만 한국 기술별 실제 soundID 호출 의미는 미상 / 3개 믹서 출력 PASS가 기술-효과-음향 정답을 의미하지 않음
- 필요 자료: Effect.tbl 음수 Frame#/Repeat/Alpha/Light 명령 + 기술별 한국 실행 영상/녹음의 soundID·명중·재행동 시간; field=sound_id
- 다음 방법·담당: 안전한 한정 미리보기와 원본 효과 의미를 분리; WAV ID 전수 참조 뒤 실제 출력 관측; 모든 확보 GIF와 원본 프레임 비교; Delay raw 단위/음향/타격 시점은 정확한 P2 관측 / Work: 효과/음향 / P2-03

### 15. GAP-G-impact

- 원본/관련ID: KR491:effect_sequence:72, KR491:effect_sequence:70
- 원인·영향: BOUND_NOT_EXERCISED / 119전체/8부분의 안전 미리보기와 원작 Alpha/Light/반복/명중/재행동 시점은 별개;72는 빈 효과로 차단 / 효과를 실제 공격기술의 원작 타격감으로 채택할 수 없음
- 필요 자료: Effect.tbl 음수 Frame#/Repeat/Alpha/Light 명령 + 기술별 한국 실행 영상/녹음의 soundID·명중·재행동 시간; field=impact
- 다음 방법·담당: 안전한 한정 미리보기와 원본 효과 의미를 분리; WAV ID 전수 참조 뒤 실제 출력 관측; 모든 확보 GIF와 원본 프레임 비교; Delay raw 단위/음향/타격 시점은 정확한 P2 관측 / Work: 효과/음향 / P2-03

### 16. GAP-I-IME

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: BOUND_NOT_EXERCISED / 실제 Windows/Android 한글 조합·확정·지우기·취소·중복 제출 미실행 / 생성 bitmap과 이름 문자열 검사가 실제 한글 생성 성공은 아님
- 필요 자료: DLGLOGIN/DLGNEW01/DLGPASS mask; 2001 생성GIF KRO-CREATE-VIS-20010607 + Windows/Android 실제 IME; field=IME
- 다음 방법·담당: 원본 bitmap, 로컬 생성 흐름, 실인증을 나누고 오류/취소/한글조합을 실제 실행; 한국 공식 생성 절차·원본 문자열·사용자 UI 사진을 구분; 로그인 UI 마스크2개와 실제 IME 별도 관측 / Work: 생성/UI / P2-04

### 17. FAILURE-android_gen003

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: RUNTIME_ERROR / GEN003 설치 후 FAIL_NO_REPORT 보존; 새 Android 실제 보고서/화면/저장 결과 없음 / Linux554 PASS나 APK 생성으로 Android/Galaxy 완료 불가
- 필요 자료: docs/rebuild/p2-work/evidence/ANDROID_GEN003.json
- 다음 방법·담당: 최소 실패 샘플/전체 로그를 보존하고 새 동일 플랫폼 시험 결과로만 현재 상태를 갱신 / Work: 플랫폼/파서 / P2

### 18. FAILURE-native_windows

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: ENVIRONMENT_BLOCKED / 기존 Windows 시험 runner가 branch 보호에 의해 실행 전 차단; native 실행 증거 없음 / Windows 빌드 생성과 앱/저장 안전 검증을 분리
- 필요 자료: docs/rebuild/p2-work/platform/WINDOWS_NATIVE_BLOCKER.json
- 다음 방법·담당: 최소 실패 샘플/전체 로그를 보존하고 새 동일 플랫폼 시험 결과로만 현재 상태를 갱신 / Work: 플랫폼/파서 / P2

### 19. FAILURE-wine_save

- 원본/관련ID: 12 failed save assertions
- 원인·영향: RUNTIME_ERROR / Wine CreateSymbolicLinkW stub 관련12개 저장 FAIL 보존;진짜 링크 fixture 없는 통과 불가 / 같은 안전 assertion을 native Windows에서 실제 재시험 필요
- 필요 자료: docs/rebuild/p2/WINE_STORAGE_DIAGNOSIS.json#latest_v4_result
- 다음 방법·담당: 최소 실패 샘플/전체 로그를 보존하고 새 동일 플랫폼 시험 결과로만 현재 상태를 갱신 / Work: 플랫폼/파서 / P2

### 20. GAP-J-same_account_roundtrip

- 원본/관련ID: UNKNOWN — 대응 원본ID 미확정
- 원인·영향: ENVIRONMENT_BLOCKED / 허용된 무료 실제 인증/HTTPS endpoint·Galaxy 연결 없이 계정 왕복 미실행 / 오프라인 저장만으로 PC→Android→PC 같은 계정 이어하기 완료 불가
- 필요 자료: 동일 새 입력의 native Windows 로그·Android ActivityManager/graphics 로그·Galaxy 실기기·무료 시험인증 endpoint; field=same_account_roundtrip
- 다음 방법·담당: 기존 save_self_test.gd 안전시험 유지; 플랫폼별 보고서·checksum·오류 원인으로만 상태 갱신; 정적 참고 패턴과 실기기/실인증 구분; 좌표 일괄 입구 이동 금지 / Work: 플랫폼/저장 / P2-05/06

## 전달·재개

화면·실제 출력 오디오: BARAM_PRIORITY_FILL_RESULTS_20261016.html  
전체 실행증거: BARAM_PRIORITY_RUNTIME_EVIDENCE_20261016.zip  
비공개 재현입력: BARAM_PRIORITY_PRIVATE_RUNTIME_GEN002.zip  
정확한 저장ID·해시·복원명령은 PRIVATE_DELIVERY.json/NEXT_WORK.md에 있다. 공개Git에는 코드·선정필드·메타·진단만 저장하고 원본그림/음향/폰트/키/사용자세이브를 올리지 않았다.

P2검수와 독립잔여재집계까지 수행했으며 전체게임완료가 아니다. P3/P4·운영배포·main병합·유료작업은 수행하지 않았다. 다음작업은 위지도정체성/출구·개별외형·플랫폼 실패 순서이며, 이미검증한 동일 입력 조사/실행을 반복하지 않는다.
