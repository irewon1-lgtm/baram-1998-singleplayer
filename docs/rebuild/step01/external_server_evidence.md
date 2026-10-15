# 외부 서버·자료 정적 조사 — P0/P1

작업 ID: BARAM_REBUILD_P0P1_001  
기준: BARAM_REBUILD_PLAN_V1_20261015 / STEP01_WORK_INSTRUCTIONS.md  
조사일: 2026-10-15  
범위: 공개 저장소의 특정 커밋에 있는 소스·CSV·문서 확보, 정적 해석, 출처/시험 인계. **기준 서버·클라이언트 실행, 패키지 설치, 게임 코드 변경, 빌드, 배포, P2 실행은 하지 않았다.**

## 1. 확보 범위와 고정 지문

| 자료 | 고정 커밋 | 실제 확보 |
|---|---|---|
| project1998/Project1998 master | 65cb3ef28f289ee35d19abfb6829d6120b9ec0cd | 선택한 소스·CSV·문서 43개 |
| unkmc/RTK-Server main | e6fa54dc3ec0de1e8a7dbbc5323299eadcf7bef6 | 선택한 C·Lua·환경 문서 25개 |

68개 파일, 2,573,642바이트를 개인 작업 경로에 확보했다. **68개 모두 고정 커밋의 Git blob SHA와 바이트가 일치**하며 SHA-256도 다시 계산했다. source_id 중복 0개, 정적 관찰의 출처/라인 참조 55개 유효를 검사했다. 이것은 자료 무결성 검사의 결과이며 게임 기능 PASS가 아니다.

원본 사본은 `/workspace/scratch/8309e434ce3b/private-external/server/p/`와 `/r/`에 있다. 공개 결과에는 원본 소스·바이너리를 넣지 않고 메타데이터/해석만 저장한다. 원격 URL+커밋+원본 파일 ID+blob SHA+SHA-256을 `external_server_evidence.json`의 `files[]`에 기록했으므로 사본이 없는 다음 환경에서는 같은 커밋으로 회수할 수 있다. 임시 로컬 경로가 다음 작업자에게 자동 유지된다고 가정하지 않는다.

전체 저장소를 받거나 전체 코드를 감사한 것은 아니다. 재귀 트리는 각각 2,806/8,635개 노드이며 truncated=false였다. 사본을 받은 파일도 모든 줄을 의미 감사한 것이 아니라 아래 관찰에 필요한 함수·표·주석을 읽었다. SQL 전체 덤프·실제 맵 바이트 전체는 이 담당 조사에서 내려받지 않았다.

## 2. 새로 연결한 빈칸

| 기능 | 정적 근거와 확인한 동작 | 남은 확인 |
|---|---|---|
| 생성·로그인 | P1998 LoginSession.cs L192–270, LoginAuth.cs L79–122: 중복 이름·비밀번호·외형·저장·잘못된 로그인 경로 | 한국 원본 화면, 한글 인코딩, 실제 wire/UI 흐름 |
| 한글 생성 | NameRules.cs L16–27과 LoginSession.cs L288–290은 ASCII 제한을 명시 | 그대로 이식 불가. KR 인코딩/IME/바이트 제한 별도 |
| 외형·평민 | CharacterFactory.cs L23–76과 RTK char/logif.c L58–64로 외형 인자 연결. Character.cs L75–79/106–110/162는 Lv1·빈 기술·Peasant | 한국 생성 순서와 외형 렌더 슬롯·초기 수치 |
| 네 직업 | 네 trainer 파일의 Lv5 전직·baseClass 분기, SpellLearnCosts.csv의 직업/레벨/금전/재료 열 | 한국 직업별 기술명·학습값·승급 고증 |
| 상점 | potion_shop.lua L147–256은 mapTitle별 재고, npc.c L230–231의 수리/상점/은행 필드 | 한국 점포 위치·서비스·가격 |
| 지도·출구 | Warps.csv의 원/목적 map+xy와 이동 코드의 충돌/경계/warp gate, RTK Warps SQL 로더 | 북미 지형은 한국 지형의 정답이 아님 |
| 스폰 | Spawns.csv의 종/지도/좌표/시간/대체종, SpawnDirector.cs L39–74의 점/그룹 스폰 구분 | 한국 초보 사냥터 일반종·변종·보스·리스폰 |
| 기술 소리 | spark→global_zap→playSound→Lua 바인딩→clif_playsound→opcode0x19의 실제 소스 경로 | 한국 sound archive의 ID 대응, 실제 소리/지연 |
| 효과 | RTK global_zap.lua는 spark unaligned에 animation28, heal은 animation5 | 프레임·지연·기준점·방향·레이어·팔레트 |
| 시전 타이밍 | P1998 Content.Spells.cs L280–288은 35프레임이 RTK 최빈값을 택한 fallback임을 명시 | 35/60초를 한국 정본으로 채택 금지 |
| 음악 | Session.Media.cs/MapBgm.csv/MusicTracks.csv가 MIDI ID·지도 zone·중복 재시작 방지를 연결 | 한국 도시별 원곡, MIDI 음원셋/출력 차이 |
| 비영사천문 | gateway.lua는 region→도시→동서남북 gate box 분리 | 한국 좌표/금지맵/취소/반복 시 정지 미검증 |
| 저장 | CharacterStore.cs L125–183/219–247/403–425는 트랜잭션, 손상 JSON과 미존재 구분, 덮어쓰기 방지 | Android 오프라인·동일 계정 동기화·업데이트 이전 |

각 행의 세부 원본 링크·라인·출처 ID·정상/실패 시험은 JSON `observations[]` 14개에 기록했다. `files[]`의 ID는 예를 들어 `EXT-SRV-P1998-SHARED-NAMERULES-CS` 형식이다. 이름이 같은 기능이라도 원본 묶음/지역/버전을 합치지 않았다.

## 3. 중요한 충돌과 미활용 원인

**같은 spark 이름도 소리가 다르다.** RTK global_zap.lua L74–77은 sound55/animation28인데, P1998 spell_effects.csv L183은 sound701/animation28이다. P1998이 RTK 내용을 가져와 보정한 계보이므로 이를 독립 원작 근거 두 개로 계산하지 않는다. 두 숫자를 평균 내거나 한국 소리 ID로 자동 대입하지 않는다. 원본 archive/클라이언트 조합에서 ID 존재와 실제 재생을 확인하는 작업으로 넘긴다.

P1998 docs/research/README.md는 RTK를 7.x/Mithia·ClassicTK2019 계열로 명시하고 밸런스와 후대 아트의 차이를 경고한다. P1998의 목표 날짜 2001-07-09도 **북미 4.95 재구현 목표**이며 한국 1998–2001 정본과 동일하지 않다. 추출된 CSV 수량을 원작 정확성으로 승격하지 않는다.

| 원인 | 이번 상태 | 다음 조치 |
|---|---|---|
| 버전 불일치 | ASCII 이름, sound55/701, 후대 alignment/아이템/맵/수치 | 한국 입력·archive·해당 시대의 필드별 근거와 대응 |
| ID/의미 미식별 | 한국 효과·소리·프레임 시점과 NA 숫자 대응 | 한국 DAT/TBL/FRM/소리를 우선 연결, 실제 재생은 P2 |
| 접근 불가 | linked Essorcal/project1998-testclient는 API404 | 확보한 LoginProbe와 원본 UI로 최소 시험 준비; 전체 suite 준비 주장 금지 |
| 의도적 미사용 | NA지형을 KR 지형으로 치환하지 않음 | 포맷/함수 구조 참고에 제한, 한국 지형을 primary로 사용 |
| 의도적 미사용 | 코드 복사/포팅하지 않음 | P1998 README의 라이선스 미지정과 RTK 조건을 코드 포팅 전에 확인. 현재는 정적 관찰·명세 참고 |
| 버전/환경 불일치 | RTK 문서는 Ubuntu16.04i386, Dockerfile은 i386/latest+옛 패키지 | 무료 격리 P2에서 가용 패키지와 DB 호환을 먼저 확인; 새 게임 필수 구조로 채택하지 않음 |

## 4. 릴리스·포크·옛 자료 추적

두 저장소 releases API는 빈 목록을 반환했다. tags 컬렉션과 forks 컬렉션은 connector가 거부했으며 git/refs/tags는404였다. 따라서 태그가 전혀 없다고 확정하지 않는다. 대체 저장소 검색으로 Essorcal/Project1998, unkmc/Project1998, RTK-Server-1을 발견했다. Essorcal 포크 비교는 base 대비 ahead0/behind603(포크 head f491531d90faccc0c31c1ac1a60a50d0cbb78107)이어서 새 요구사항을 해결할 독립 자료로 추가 수집하지 않았다. 무관한 동명이름 저장소는 제외했다.

한국 자료 검색에서 [연도별 옛 홈페이지 회고](https://paststory.tistory.com/15)의 실제 본문을 읽었다. 2014년 글이며 시기 경계를 추정한다고 적는다. 당시 홈페이지 이미지를 찾는 단서로만 기록했고 게임 수치/당시 규칙의 1차 근거로 쓰지 않았다. [넥슨 피디아의 1996복원 게시물](https://forum.nexon.com/ncmpedia/board_view?thread=2201109)은 검색 색인에는 관련 설명이 있으나 실제 조회 본문은 빈 껍데기여서 발견 상태만 남겼다. 목표 밖 1996 자료로 복원 프로필을 바꾸지 않는다. 두 URL은 원본 파일 해시가 없는 DISCOVERED이며 완전 확보와 구분한다.

## 5. P2 참고 실행 후보와 정확한 장애

**P1998+NA4.95: 부분 준비.** 43개 선택 사본과 버전·패키지·설정·probe/patcher 소스는 준비했다. 이 사본은 전체 runnable checkout이 아니다. P2에서 전체 소스를 위 SHA로 별도 복사하고 .NET8 SDK(global.json8.0.100/latestFeature), SQLite8.0.10, BCrypt4.0.3, MoonSharp2.0.0 복원이 필요하다. 패키지 설치/빌드는 이번에 실행하지 않았다.

P2 환경은 `P1998_BIND=127.0.0.1`, `P1998_STATE=<새로운 폐기 가능 절대경로>`를 두 프로세스에 동일하게 설정한다(Configuration.md L61/L81). LoginServer2000/2001과 Server2005/2006의 충돌 여부, 원본 NA4.95 클라이언트/Inter.dat/NexusTK.dat/NexusTK.snd/Maps 위치와 해시를 인벤토리에서 연결한다. Inter.dat 리다이렉트는 Tools/Program.cs의 12문자 치환 조건을 읽었으며 원본을 건드리지 않고 사본에서만 준비한다. 최초 사용자 생성·중복·틀린 암호·취소·월드 진입·저장 재로그인과 효과/소리 비교를 분리한다.

이는 북미 로그인부터 저장까지의 참고 실행 후보다. 한국 한글 지원, 한국 지도·수치, Android 오프라인, 계정 동기화를 제공하는 완제품이 아니다. 한국 클라이언트와 연결된다는 검증도 없다.

**RTK: 보조 정적 참고.** 25개 C/Lua/문서 사본과 login→char→map, MySQL/Lua5.1 의존성을 정리했다. README가 가리키는 `/client/RetroTK` 폴더는 읽은 재귀 트리에서 찾지 못했다. 정확한 클라이언트 버전·원본 해시와 옛 i386 패키지 가용성, 전체 DB 마이그레이션은 남았다. 이것이 필요해지는 요구사항에 한해 P2의 격리 기준본 후보로 둔다. 공용 서비스/운영 DB/기존 세이브에 연결하지 않는다.

## 6. 동결과 재개

외부 조사는 이번 68개와 관찰14개로 동결한다. 새 게임 시험은 모두 NOT_RUN이다. 전체 소스 재감사·대량 수치 수집을 반복하지 말고 아래 순서로 재개한다.

1. 전체 step01 원장에 `files[]` 출처 ID를 연결하고 한국 원본 지도·생성·시각/소리의 입력 지문과 결합한다.
2. ASCII 이름, sound55/701,35프레임 fallback, NA맵/스폰, testclient404를 원인과 다음 작업이 있는 이슈로 보존한다.
3. P2 승인 후에만 한국 맵/합성/효과·소리/한글 입력/저장 위험 검증을 실행한다. 원본 서버는 위 버전 조합의 별도 참고 시험이다.
4. 소스 사본 재회수 시 각 URL의 고정 SHA와 blob SHA를 확인한다. 현재68개 원본 SHA가 같고 조사 범위가 같으면 정적 조사를 반복하지 않는다.
