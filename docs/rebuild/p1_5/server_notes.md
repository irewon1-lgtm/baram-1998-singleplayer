# P1.5 외부 참고 서버: 확보·해독·소비코드 대조 결과

판정: **북미 참고 소스 입력 확보는 완료, 원작 한국판 필드 채택은 0건, 의미 연결은 PARTIAL**이다. 서버·클라이언트·빌드·패키지 설치·DB 실행은 모두 NOT_RUN이다. 이 문서는 한국판 대사·좌표·확률·성장 수치를 북미 자료로 대체하도록 허용하지 않는다.

정규화 원행은 비공개 입력이다. 공개 카탈로그는 `selected_content/na_reference_catalog.json`, 파일별 출처·해시·소비코드 관측은 `research_server.json`이 정본이다. 37,526개 행을 한국판 복원 완료 건수로 계산하지 않는다.

## 실제 추가 확보와 기존 결과 재사용

| 입력 | P0/P1 확보 범위 | 이번 실제 확보·바이트 검사 | 판본·계보 |
|---|---:|---:|---|
| project1998/Project1998 | 선택 파일 43개 | 고정 전체 tree의 2,770개 파일, 24,219,344바이트 | 65cb3ef28f289ee35d19abfb6829d6120b9ec0cd; NA4.95를 목표로 한 2026년 재구현, RTK·후대 자료 혼합 |
| unkmc/RTK-Server | 선택 파일 25개 | 고정 전체 tree의 8,404개 파일, 137,070,633바이트 | e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6; Mithia/ClassicTK2019 계보의 2020년 NA7.x 참고 서버 |

이전 68개 선택 파일을 다시 확보한 성과로 중복 계산하지 않는다. 이번에 추가 접근 가능한 고정 tree 경로는 11,106개다. 독립 근거 가족은 두 개로 늘어난 것이 아니다. P1998 자료 상당수가 RTK에서 파생했다.

`git -c core.hooksPath=/dev/null clone --no-checkout`으로 소스 이력만 내려받고, 고정 커밋을 정적으로 내보냈다. `git archive`가 P1998의 6개 파일에 CRLF 변환을 적용한 것을 발견하여 `git cat-file blob` 원본 바이트로 교정했다. 최종 11,174개 모두 Git tree의 blob SHA 및 실제 바이트 SHA256을 대조했다. 하위 모듈 gitlink는 두 tree 모두 0개다. 소스 파일을 해석하거나 실행해서 설치하지 않았다.

전체 개별 경로·해시는 비공개 입력의 `Project1998-files.json`, `RTK-Server-files.json`과 각 `*-tree.json`을 사용한다. 수신 시 공개 Git 고정 커밋에서 재확보하거나 비공개 인계 ZIP의 동일 상대 경로를 읽고 이 해시를 재검사한다. 현재 Work의 정적 파일 읽기는 Codex 수신 환경 G0 시험을 대신하지 않는다.

## 전수 처리 범위와 남은 의미 해독

| 분야 | 실제 전수 처리 | 해소되지 않은 내용 |
|---|---|---|
| NPC 외형·서비스 | P1998 NPC380행, 장비1행, 서비스 composition32행; RTK NPC385행·장비1행 | KR 개별 NPC 이름·외형·좌표·방향 대응, 한국 화면 대조, 실제 합성·모션 |
| NPC 대사·퀘스트 | RTK NPC Lua163개 파일의 관련 call-site3,398개와 분기 위치; P1998 click/speech Lua26개 진입점 | 동적·여러 줄 인자 및 함수 간 분기를 완전히 해석한 대화 그래프는 아님. C# fallback도 별도. KR 원문0건 |
| 몬스터·스폰 | P1998 몬스터716행, 고정스폰1,175행, 기본영역2,588행·트랩20행·제작8행 및 행동표 | P1998 영역스폰24행은 존재하지 않는 몬스터 ID 참조. 북미 스폰을 한국 배치로 채택하지 않음 |
| 드롭 | P1998 drop377표와 실제 소비코드; RTK literal387표의 일반629·rare373개 roll을 독립 추출 | KR 확률·수량 미확정. RTK 전역 특수드롭·조건은 표 외 handler가 존재함 |
| 제작·수리 | RTK 제작·퀘스트 Lua16개 파일·call881개; Recipes 스키마24필드·실제 행0개; P1998 토글/방어구퀘스트/채집 표 | Recipes0행으로 제작 부재를 단정하지 않음. Lua의 조건·소모·실패 그래프는 부분 해독. KR 시대 적합성·성공률 미확정 |
| 직업·성장·기술 | P1998 기술927·학습비591·기술레벨143·효과643·경험치491행, 직업/성장/매개변수 표; RTK 기술906행·Lua394개 파일·call2,776개 | NA 직업/서브패스·후대 수치를 한국4직업의 정답으로 쓰지 않음. 시청각·명중 시간은 미관측 |
| 경제 | P1998 아이템2,544행, 상점재고38·매입46·분류11행과 소비코드; RTK 아이템2,545행 | 실제 런타임의 curated shop 우선순위·동적 제한과 KR 당시 가격·재고는 별도 |
| 지도·이동 | P1998 워프4,824·gateway gate16행 및 이동 관련 표; RTK 지도9,850·워프4,476행 | 한국 지형·도시·출구 대응 근거로 채택하지 않음. NA 좌표·지도번호는 namespace를 보존 |

원행 수는 발견한 고정 참고 소스의 분모다. 한국판 전체 개체의 모집단으로 간주하지 않는다. 353개 CSV행은 후행 열 일부를 원래 생략한 상태여서 누락 필드를 그대로 보존하고 `source_shape_missing_columns`와 진단에 기록했다. 0이나 빈 기본값을 넣지 않았다. RTK drop5표의 여분 amount는 원코드의 `#items` 범위 밖이므로 사용되지 않는 꼬리 값으로 기록했다. 이 파일들의 읽기 성공을 모든 동작 지원으로 표현하지 않았다.

## 소비코드로 확인한 채택 금지·미활용·차이

각 항목의 파일 SHA와 정확한 행은 `research_server.json.semantic_findings`에 있다.

1. **NPC 방향:** P1998 `Server/Content.Csv.cs:547–590`은 원표 `NpcSide`를 읽어 방향으로 쓰지 않고 `Dir=2`를 지정한다. NPC380행의 저장 방향은 344개가2, 35개가0, 1개가3이다. 방향 열이 있다는 사실과 실제 존중되는지를 분리해야 한다.
2. **NPC 착용:** P1998 `NPCEquipment.csv`는 1행이 있지만 고정 `Server/`에서 이 테이블의 소비 참조는 발견되지 않았다. 파일 존재를 착용외형 완성으로 해석하지 않는다. NPC380행 가운데 human-composite flag는1개이며 나머지는 개체 look 경로가 중심이다. look75종, map275개라는 집계도 한국 NPC 외형 식별 성과가 아니다.
3. **수리:** P1998 `Server/NpcAbility.cs:529–536`의 `RepairAbility`는 안내문만 있는 stub이다. 수리 flag8개가 실제 내구도 복구·금전 소모8건을 의미하지 않는다. RTK 수리 함수·C 소비코드가 별도 입력이며 한국 수리비는 미확정이다.
4. **드롭의 일반 roll:** RTK `MobDrops.lua:3437–3468`은 각 행을 `1..100000` 정수로 독립 추첨하고 `rate*1000` 이하를 통과시킨다. 같은 아이템이 여러 행에 등장해도 각각 별개다. 숫자 item token은 금전이며 금액은 고정, 일반 물품 수량은1..최대 정수 난수다.
5. **rare roll:** 같은 파일 `3473–3499`는 각 행을 모두 추첨한 뒤 성공한 것 중 소스 순서상 첫 항목만 지급한다. 가중치 분포가 아니다. j번째 지급 확률은 해당 성공확률 × 앞선 모든 행의 실패확률이며 아무것도 안 나오는 경우가 남는다. 이 식은 해당 코드의 의미이고 한국판 확률 추정이나 가상 처치 실험이 아니다.
6. **금전 구현 차이:** P1998 `Content.Mobs.cs:442–464`는 gold 분기 전에 수량을1..최대로 무작위 선택한다. RTK의 고정 금전과 다르다. 같은 계보의 표·코드를 자동으로 합치지 않는다.
7. **교정표에 추정 확률 포함:** P1998 `re/extract_mob_drops.py:34–72`는 아카이브로 확인한 아이템 존재에 accessory 확률을 calibration으로 추가했다고 명시한다. 대략1% 등은 그 프로젝트의 재구성 선택이며 한국 원작 확률로 승격하지 않는다. alias와 없는 아이템을 제외한 처리도 원본 Lua387표와 최종 CSV377표의 차이로 보존한다.
8. **특수드롭 누락 금지:** RTK `HandleMobDrops`는 PC 처치 조건, 맵 조각과 용의 정수 handler를 별도로 호출한다. literal monster표만 추출해 모든 드롭이 재현된 것으로 계산하지 않는다.
9. **직업99 표식:** 기술118행의 `SplPthId=99`는 일반 직업에 매칭하지 않는 특별 표식이라고 P1998 소비코드가 명시한다. 다섯 번째 직업을 만들거나 전직업 공통으로 풀지 않는다. GM/proc/dog 경로는 별도다.
10. **대화 우선순위:** P1998의 Lua 대화가 있으면 C# ability보다 우선한다. 서비스 composition은 NPC ID 또는 map별로 좁혀질 수 있다. 역할만 같다고 모든 같은 식별자·도시에 같은 기능을 주지 않는다.

## 실제 정적 검사

```bash
python3 tools/rebuild/p1_5/extract_na_references.py --source-root <private-server-root> --out <private-selected-content> --metadata docs/rebuild/p1_5/research_server.json
python3 tools/rebuild/p1_5/validate_na_references.py --source-root <private-server-root> --selected <private-selected-content> --metadata docs/rebuild/p1_5/research_server.json --out <private-server-root>/na_static_validation.json
```

실제 결과: 도구 exit0, 출처파일630개 해시·크기·Git blob 대조, 정규화11파일/37,526행 읽기, 중복 record ID0, 출처 ID 끊김0, 무단 KR 선택0. 자료 참조 그래프는 **PARTIAL**이다. 영역스폰→몬스터2,592개는 연결되고24개는 대상이 없다. 드롭→물품917개·금전75개, 드롭→몬스터377개, 학습비→기술591개·직업591개·물품1,073개, 상점→NPC95개·물품944개는 연결됐다. 경로99와 금전·명시적 빈재고는 원소스 의미가 있는 sentinel로 별도 집계했다.

첫 dry-run은 다중 INSERT에서 tuple 번호를 다시 시작한 추출기의 record ID 중복1,876개를 실제 FAIL로 잡았다. ID에 소스 offset을 포함하도록 최소 수정한 후 같은 입력으로 재시험하여0개를 확인했다. 이 실패는 원본 SQL 중복 결함으로 돌리지 않는다. 이 검사는 새 게임 가져오기·게임 동작·확률의 역사적 정확성 PASS가 아니다.

## 의존성·호환 쌍·P2 준비

**P1998 — SOURCE_READY / EXECUTION_PARTIAL.** 전체 source/data와 maps 디렉터리2,040파일(.map2,039개·CSV1개)을 확보했다. `global.json`의 SDK8.0.100/latestFeature, 기본 net8.0, 런타임 두 프로젝트 LoginServer와 Server, Shared·Shared.Core·Protocol.Tk495 프로젝트를 확인했다. 런타임 외부 패키지는 MoonSharp2.0.0, BCrypt.Net-Next4.0.3, Microsoft.Data.Sqlite8.0.10이다. 선택적 Windows 편집기 두 개의 WebView2 및 시험 프로젝트 패키지는 `research_server.json.dependencies`에 분리했다. restore/build/실행은 NOT_RUN이다.

대응 클라이언트 후보는 Library `LIB-014`, 파일 ID `libfile_0ef3b7e0828c8191a637c4061889b72d`, `/Baram1998Assets/NA_4.95_Nexus495.exe`, 설치파일 SHA256 `486f4684b76658d92eaf84aab77fe9be9489ea01de8264fe90d0040466620aaa`다. 이는 기존 목록의 설치파일 신원이며 설치된 게임 EXE가 문서의 특정4.95 바이너리와 같다는 검증은 아니다. 정확한 `NexusTK.exe`·`Inter.dat`·DAT/SND·Maps의 실제 바이트와 PE버전 대응을 P2 G0에서 확인해야 한다. 북미 쌍은 한국한글·지도·규칙 검증을 대신하지 않는다.

향후 별도 승인된 P2 관측 때에는 원본을 건드리지 않는 사본, 빈 일회성 state, 명시적 `P1998_BIND=127.0.0.1`, wire logging 비활성 조건을 준비한다. 설정 문서는 프로그램 자체의 기본 bind가 모든 interface일 수 있음을 명시하므로 launcher 문구만 보고 loopback을 가정하지 않는다. 실제 listener·실행 확인은 이번에 하지 않았다. `Essorcal/project1998-testclient` API404와 정확한 이름 저장소 검색0건이 남아 전체 보조 suite 준비를 주장하지 않는다. 자체 LoginProbe 소스가 있다는 것과 전체 suite 확보는 별개다.

**RTK — SOURCE_READY / COMPATIBLE_CLIENT_BLOCKED.** 전체 C/Lua/SQL/지도 입력과 Makefile을 확보했다. README는 Ubuntu16.04 i386·GCC/make·MySQL client/server/devel·Lua5.1/devel을 요구한다. Makefile은 crypt/mysqlclient/math/zlib/dl/Lua5.1/pthread를 링크하고 stack protector를 비활성화하는 플래그도 포함한다. Dockerfile은 i386/ubuntu:latest와 예전 패키지명을 섞는다. 패키지 실재·빌드 성공·비트수·DB migration은 NOT_RUN이며 확정 재현환경으로 채택하지 않는다. README의 `/client/RetroTK`와 WHE.exe는 고정 tree에 존재하지 않는다. 대체 `unkmc/RTK-Server-1@9757360e4e3ed79519338d39ea6e10b3919bdff9`의 비잘림 tree8,573항목도 확인했으나 해당 client경로는 없었다. 정확한 호환 client build/hash는 계속 BLOCKED다.

## 경로 확장 결과와 계보

- 두 원본 저장소의 releases API는 실제 빈 목록이었다. 포크 전용 endpoint는 connector가 허용하지 않아 저장소 검색과 compare로 우회 조회했다. `unkmc/Project1998`은 원본보다970commit 뒤, `Essorcal/Project1998`은603commit 뒤이며 둘 다 ahead0이었다. 최신 코드를 새로 얻은 것으로 세지 않는다.
- 실제 Git 전체 이력에서 RTK는2020년 초기/Mithia→RetroTK 재명명과2026년 추가1행 기록을 확인했다. P1998 고정 HEAD의2026-10-14 map-entry guard 수정도 포함한 상태를 보존했다.
- 새 `Essorcal/project1998-docs` README를 읽었다. spells/items/mobs/atlas는 같은 game-data의 자동 생성물이고 그림은5.33 기반이라고 명시한다. 독립 한국 원문 또는 별도 확률 증거로 세지 않는다. 큰 effects HTML 조회 실패를 자료 부재로 기록하지 않는다.
- 한국자료 조사자가 확보한 Nexia archive의 직접 링크를 이어 읽었다. `darkalucard/StarterTK@735f633537028230f9d246a01066b56970eb62c5` README는 Mithia/RetroTK 기반7.50이라고 명시한다. `stevencorona/yuri@625bb52e857db52a9bb0edc28f2d067b12417345` README는 같은 Lua/DB 호환을 목표로 한 Mithia replacement라고 명시한다. 둘 다 한국1998~2001 숫자를 보완하는 독립 근거가 아니므로 불필요한 대량 수집은 하지 않았다.
- EmpireOfHan의 master404 후 main 고정 tree `e5a8a09e673640427f245967c49c9dc427b822ec` 접근을 확인했다. BlankTK는 README와 저장소 API 모두404였다. 유효한 경로가 닫힌 것과 자료 자체의 부재를 구분한다. 실제 응답·검색·제외 이유는 비공개 `discovery.json`에 보존했다.

## 보안 관측

RTK의 원본 참고 DB에는 **외부 서버 캐릭터 인증 관련 해시·내부 IP·게임상태 행**이 들어 있다. 대표 위치는 `database/2020-09-02-21-55-01_RTK.sql.bak`, Character schema430행·INSERT523행이다. 값은 공개 산출물·정규화 행에 복제하지 않았다. Accounts/Character/Inventory/Equipment/메시지/registry 등은 SQL 화이트리스트 밖으로 제외했고 원본은 비공개 참고 입력에만 보존한다. 외부 공개 자료의 이 상태는 사용자 계정의 노출을 입증하지 않는다. 계정 키·서명키·암호·이력을 변경하지 않았다.

외부 EXE·WHE·Lua·SQL·설치·빌드 훅은 실행0회다. 원본 보존·바이트 일치는 안전성 판정이 아니다. P1998과 RTK를 그대로 인터넷 서비스로 실행하거나 실제 사용자 암호/세이브를 넣는 것은 이번 결과에 포함되지 않는다. 이번 결과로 새 게임 코드·배포·운영 데이터는 바뀌지 않았다.
