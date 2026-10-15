# 시청각·자료 도구 정적 조사 — P0/P1

작업 ID: BARAM_REBUILD_P0P1_001. 네 지정 문서를 실제 읽고 수행했다. 새 게임·파서 구현, 기준 서버/클라이언트 실행, 빌드, 음향 재생은 하지 않았다. 상세 파일·해시는 `external_visual_evidence.json`에 있다.

## 실제 확보와 확인 범위

| ID | 저장소 | 고정 커밋 | 실제 확보 | 판정 |
|---|---|---|---:|---|
| EXT-VIS-001 | DizzyThermal/TKViewer | `2943507d0a8b91b990b94d2cc82c3f589343d3ec` | 33개 소스/문서 | 정적 핵심 구간 읽음, 실행 NOT_RUN |
| EXT-VIS-002 | DizzyThermal/TKMapper | `13c6dc3089b51ba2ba390a421125bd55ebf4edd3` | 21개 소스/문서 | 정적 핵심 구간 읽음, 실행 NOT_RUN |
| EXT-VIS-003 | DizzyThermal/EPFViewer | `2bc585b3ae3310df5de46f7789eada92840fbd59` | 34개 소스/문서 | 정적 핵심 구간 읽음, 실행 NOT_RUN |
| EXT-VIS-004 | olds463/EPFViewer | `056eb4045d2e7592bb17453f8a4a472232a83d7e` | 4개 소스/문서 | 정적 핵심 구간 읽음, 실행 NOT_RUN |

최초92개 파일 모두 원격 트리의 Git blob SHA와 실제 받은 바이트의 Git blob SHA가 일치했다. 이것은 확보 무결성 검사이며 원작 정확성·파서 정확성·실행 PASS가 아니다. 원본 게임 자산이나 실행 바이너리는 이 결과에 포함하지 않았다. 로컬 사본은 `/workspace/scratch/8309e434ce3b/private-external/visual/`에 있으며, 다른 세션에서도 존재한다고 보장하지 않는다. 각 파일의 고정 커밋 URL·blob SHA·SHA256으로 다시 확보할 수 있다.

## 새로 메운 빈칸

- **프레임·합성:** `EXT-VIS-003`의 `FileHandlers/DscFileHandler.gd:12–53`에서 부품 기준 프레임/팔레트·모션별 프레임 offset을, `MotionTblFileHandler.gd:21–45`에서 모션명/ID·프레임별 레이어 순서를 실제 확인했다. `Renderers/NTK_CharacterRenderer.gd:94–144`는 이 순서와 공통 pivot을 사용한다. 따라서 단순 이미지 추출을 넘어 네 방향/무기/의상 합성 시험을 준비할 근거가 생겼다. TODO와 미해독 바이트는 남는다.
- **효과:** `EfxTblFileHandler.gd:57–102`의 효과/프레임/delay/palette와 `FrmFileHandler.gd`·`NTK_EffectRenderer.gd`의 FRM 팔레트 대응을 찾았다. 특정 한국 기술명→원본 효과 ID, 실제 시전/명중/소리 호출 시점은 아직 해결되지 않았다. Efx 팔레트 값과 실제 FRM 선택 차이는 P2 비교 항목이다.
- **몬스터 동작:** `DnaFileHandler.gd:22–50`에 프레임 offset·duration·alpha가 있다. 이 데이터로 몬스터 배치·드롭·전투 수치를 확정할 수는 없다.
- **지도:** `EXT-VIS-002`의 MAP 4/6바이트 셀 후보와 SObj 충돌 데이터를 확인했다. 한국판 적용, 정상 출구·도시 연결·NPC/스폰 위치는 별도 근거가 필요하다.
- **UI 자산 식별:** `Resources/ViewerResources.gd:56–81,100–104`의 DLGLOGIN/DLGNEW/iteminv/invenbut은 한국판 내부 대응 파일을 찾는 단서다. 북미판 파일에 한국 이름을 붙여 확정하지 않는다. 사용자 사진 기준은 그대로 유지한다.

## 잘못 재사용하면 재발할 문제

1. **캐릭터 시간:** `EXT-VIS-001`의 `PartRenderer.java:368–369`는 `defaultDuration=64*16`ms를 넣는다. 이 뷰어의 GIF 속도는 원작 캐릭터 속도 근거가 아니다. DNA의 duration, effect.tbl의 delay, 실제 공격 유효 프레임/다음 행동 시간도 서로 구분한다.
2. **독립 근거 중복:** `olds463/EPFViewer`는 GitHub metadata상 `DizzyThermal/TKViewer` 포크다. 별도 원작 근거로 두 번 세지 않는다. `file_reader.py:273,297–302`는 first PAL·24×24 출력에 고정되어 일반 EPF/팔레트 기준으로 쓸 수 없다.
3. **최신 도구 호환:** 두 Godot 도구의 현 `project.godot`는 4.7 / Forward Plus다. README의 4.x를 근거로 기존 엔진에 바로 가져오지 않는다. TKMapper MAP 읽기/쓰기의 2026-06-26 커밋은 preliminary/may be buggy, HEAD는 save regression 수정이라고 기록되어 있다. 실제 roundtrip 미검증이다.
4. **소리/타격감:** 도구에서 프레임 데이터는 찾았지만, 확인한 범위에 음원 디코더·소리ID 대응·게임플레이 호출 시점은 확정되지 않았다. sfx volume 설정 하나가 지원 증거가 되지 않는다. 영상/원본 클라이언트 관찰과 reference server call evidence가 필요하다.
5. **원작 타이밍:** EPFViewer의 팔레트 미리보기는 speed slider를 쓴다(`EPFViewer.gd:164`). 프리뷰 회전 속도를 원작 팔레트 시간으로 채택하지 않는다.

## 추가 외부 자료와 조사 한계

공식 업데이트 연혁 `https://baram.nexon.com/GameGuide/View/3`의 1998–2001 구간을 실제 읽었다. 시대별 콘텐츠 분리 단서이며 정확한 아이콘·수치·시간의 정답은 아니다. 예를 들어 공식 연혁은 미니맵을 2004년 업데이트로 적는다. 사용자 편의 미니맵 요구가 있다면 역사적 원형과 사용자 지정 기능을 분리해 기록한다.

넥슨 Peak의 `https://peak.nexon.com/en/post/1569`는 1996 복원 자료/잡지 아카이브 발견 경로를 제공한다. 1996 복원판을 이번 1998–2001 기본판으로 대체하지 않는다. 웹 텍스트만 읽었으므로 원본HTML·영상·음원 바이트 해시는 없다. 검색을 실제 수행했으나 버전/FPS/속도/타임코드가 검증된 당시 한국 행동+소리 영상을 확보했다고 보고할 수 없다.

TKViewer release3.7.2는 `95462b952f5768192505260d89d39400b36241d6`이며 공개JAR 정보만 확인했다. 바이너리는 미다운로드·미실행. 나머지 도구 release 목록은 빈 배열이었다. tags/forks 목록은 도구가400으로 막았으므로 없음으로 단정하지 않았다.

## P2 인계

`external_visual_evidence.json`의 `feature_evidence` 8개는 자료→필요 기능→정상/실패/취소 시험을 연결하고, `issues` 12개는 원인과 다음 작업을 분리한다. `p2_recipes`의 지도/캐릭터/효과+소리/UI 4개 시험은 모두 NOT_RUN이다.

- 지도: 실제 한국 MAP와 tile/object EPF+PAL+TBL 해시·원본 인덱스를 인계받아 대표 도시·사냥터 입구를 같은 조건으로 독립 대조한다. 지형 자료에서 출구·스폰을 만들어내지 않는다.
- 캐릭터: 동일 몸·머리·옷·무기를 네 방향 걷기/공격/시전으로 비교한다. 원본 offset·레이어·팔레트를 보존하며 타격 유효 시점은 별도로 계측한다.
- 효과+소리: 선택한 한국 기술의 effect/FRM/PAL/EPF와 소리 원본ID·파일·호출 조건을 먼저 연결한다. 반복 귀환/취소/맵 이동/잘못된ID에서 영구 잠김·무한반복을 검사한다. 실제 오디오 출력과 로그를 함께 남긴다.
- UI: 한국 원본 archive member와 사용자 사진을 대응시킨다. 옛 로그인 외형·로컬 프로필·실제 계정인증은 서로 다른 시험이다.

현재 **PARTIAL_INPUT_PREPARED**다. 도구 소스·해시·검증 절차는 준비됐지만 실제 한국판 포맷/ID/팔레트 대응, 플레이어 원본 시간, 소리 호출과 적격 영상은 미확인이다. 원본 inventory 담당 결과를 합친 뒤 해당 시험만 준비/차단 상태를 결정한다. P2를 실행하지 않았으며 새 게임 개발로 넘어가지 않았다.


## 최종 보강·동결: 한국 원본 테이블을 실제 읽음

원본 inventory를 반복하지 않고, `LIB-010`의 같은 NWind.dat 해시에서 **미조사였던 테이블 의미 필드만** 기존 DAT reader로 정적으로 읽었다. 정확한 canonical 경로는 `KR_4.91_491v.zip!Install/DATA1.CAB!NWind.dat!<member>`이며 `Program Files`는 이 원장 경로에 붙이지 않는다.

| 원본member ID | 테이블 | 직접 확인한 필드 | 남은 것 |
|---|---|---|---|
| LIB-010-M-6ace34fcf47c | Body.tbl | NumBodies66,ID,Palette,Starting | 부품/동작/한국아이템 대응 |
| LIB-010-M-b89c932190dc | DrwOrder.tbl | 세미콜론으로 구분한 순서토큰 | 글자 의미·프레임 인덱스 검증 |
| LIB-010-M-16ef881cf3c8 | Effect.frm | 바이너리member·헤더 존재 | 정확한 포맷대응 |
| LIB-010-M-295b87f08885 | Effect.tbl | NumEffects128,앞/뒤 프레임수·반복경계·Frame#·Delay·Alpha·Light | 시간단위·한국 기술명·실제 호출 |
| LIB-010-M-d61152c67002 | EffLayer.tbl | ID/front/back | 실제 앞뒤레이어관찰 |
| LIB-010-M-29ce0f41f465 | EffRange.tbl | ID/framecount/palette/blending,ID0dummy주석 | 버전·alpha해석 |
| LIB-010-M-dd4a60742966 | MonsFrm.tbl | monsterID그룹→walking/attacking값 | 이름·시간·배치 |

이는 중요한 포맷 차이다. **KR491의 Effect.tbl은 읽을 수 있는 텍스트다. 최신 Nexus 암호화/binary EfxTbl·DSC·Motion.tbl reader를 그대로 적용하지 않는다.** 파일 이름이 같아도 포맷이 같다고 처리하면 기존 ‘자료 보유했지만 미활용’이 재발한다. 모든 해시·byte offset은 JSON의 `original_table_observations`에 있다. Delay 필드가 존재한다고 원작 ms 단위/명중 타이밍까지 확인된 것은 아니다.

NWind.snd의163WAV는 inventory담당이 실제 읽고 `archive_members.jsonl`에 각 채널·샘플레이트·샘플폭·프레임수·길이를 저장했다. 동일입력 결과를 재사용했고 다시 디코딩/재생하지 않았다. 음원 접근 자체의 빈칸은 메웠지만 기술/행동 소리ID·호출조건·타격시점 연결은 남는다.

exact-keyword 검색으로 추가한 `EXT-VIS-007`은 `kwackjiyong/barambook-api`의 `2192f9e650bed0072a839a7681dc8442b2639bfe`다. DrwOrder 문자순서를 레이어 tie-breaker로 쓰는 실제 TypeScript 코드를 읽었다. 그러나 현대 MapleStoryWorlds동작/염색·fallback을 혼합한 자료이며 원작값으로 채택하지 않았다.9개 소스/문서/작은 파생자료는 비공개작업경로에만 확보했고101개 전체 blobSHA를 검증했다. 이 저장소의292파일 전체트리에서 .map 및 map이름의 JSON/DAT/ZIP/EPF/PAL/TBL 데이터 후보는0개다. **한국맵 부족을 해결한 자료가 아니다.**

최종source IDs는 EXT-VIS-001,002,003,004,007이다. 공식연혁은 root정본 WEB-KR004를 참조하며 중복등록하지 않는다. EXT-VIS-006박물관기사는 추가발견경로에만 남긴다. 조사범위를 여기서 동결한다. 게임·도구 실행이나 P2검증은 여전히 NOT_RUN이다.
