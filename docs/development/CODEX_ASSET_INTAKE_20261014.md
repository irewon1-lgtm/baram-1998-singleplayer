# Codex 인계 — 사용자 제공 원본 파일과 추출한 14,835개 타일 (2026-10-14)

## 무엇을 저장했나

- 기존 게임 저장소: `irewon1-lgtm/baram-1998-singleplayer`.
- 기존 개발 기준 브랜치: `dev/restoration-runtime-20261014`, 기존 SHA `492de39ba848522597e49f7b48915c87ab19280f`.
- 공개 GitHub에는 **소스 코드, 원장, 해시, 재현 가능한 가져오기 도구만 보관**한다.
- 원본 클라이언트, 지도 그래픽 및 유래가 불명확한 원작 파생 그림은 비공개 자료로 취급한다.
- 사용자가 업로드한 자료들은 ChatGPT 개인 Library의 `/Baram1998Assets/`에 **실제 파일로 별도 보관**되어 있다. 이것은 GitHub 저장이나 Codex의 자동 읽기 권한을 뜻하지 않는다.

## Codex가 받아야 하는 핵심 실제 파일

`baram_tile_atlases_PRIVATE.zip` (7,008,649 bytes, SHA-256 `18581f104aa725eb615a205d428a10b46bd670b956876b99fa92ce32ebdc1514`).

`MANIFEST.json`, `README.txt`, 세 장의 PNG 아틀라스, 세 개의 `TileA/B/C_frame_map.json` 총 8개를 포함한다.

| 세트 | 프레임 | 타일 크기 | 사용한 팔레트 | 지금 검증된 것 |
|---|---:|---:|---|---|
| TileA | 4,897 | 24×24 | A0 | PNG 변환, SHA/좌표 검사 |
| TileB | 2,973 | 24×24 | B0 | PNG 변환, SHA/좌표 검사 |
| TileC | 6,965 | 24×24 | C0 | PNG 변환, SHA/좌표 검사 |
| 합계 | 14,835 | 24×24 | 그룹별 0번 | 전체 변환 완료, 실제 게임 연결 미실행 |

- 아틀라스당 128열, 한 셀 24×24 px.
- 타일 `i`의 위치: `x=(i%128)*24`, `y=(i//128)*24`.
- 프레임맵 JSON에는 원본 EPF의 left/top/w/h와 불투명 픽셀 수도 기록했다.
- **출처:** 사용자가 첨부한 `Baram Map Editor.7z` 내부 `TileA/B/C.epf`와 `TileA0/B0/C0.pal`. 에디터의 제작 연도 및 1998~2001 한국판 원작 일치는 미확인.
- 실제 Godot 맵, 충돌, 이동, 사운드 및 원작 일치 검증은 **NOT_RUN**. 그림 변환 성공을 게임 완성으로 주장하지 않는다.

### Codex 실제 사용법

1. Codex 작업 세션에 사용자가 `baram_tile_atlases_PRIVATE.zip` 파일을 **한 번 첨부하거나**, 접근 가능한 **비공개 GitHub 자료 저장소**에 파일을 업로드한다. ChatGPT Library에 있다고 해서 Codex가 자동 조회하는 것은 아니다.
2. 게임 저장소 작업 폴더에서 아래 명령으로 ZIP 무결성과 내부 모든 PNG·JSON 해시/좌표를 검사하며 압축 해제한다.

```bash
python3 tools/import_private_tile_atlases.py \
  --bundle /path/to/baram_tile_atlases_PRIVATE.zip \
  --out private_assets/baram_tiles
```

3. `private_assets/`는 `.gitignore` 대상이다. ZIP/원작 그림/추출 PNG는 공개 GitHub 커밋 대상이 **아니다**.
4. `tools/godot_private_tile_atlas.gd`를 Godot 4 프로젝트에 포함하거나 코드만 이식한다. 예: `var tiles = BaramPrivateTileAtlas.new()` → `tiles.load_directory(<절대경로>)` → `tiles.configure_sprite(sprite, "A", 0)`.
5. 실제 맵의 레이어·타일 ID·좌표 대응을 조사 후 연결한다. 타일 ID는 스프라이트 번호이며 타일 배치와 충돌이 자동으로 증명되지는 않는다.
6. 새 그래픽을 추가할 때도 원본 버전·팔레트·해시·의미 근거·구현 상태를 분리해 기록한다.

## 다른 원본 자료 — Library에서 중복 제거 후 보관 완료

- `KR_1.25_winbaram.zip`
- `KR_4.91_491v.zip`
- `NA_4.03_NexusTK.7z`
- `NA_4.66_NexusTK.7z`
- `NA_4.95_Nexus495.exe` (원래 `.crdownload` 업로드명, 내용 해시와 크기가 보존 원장 일치)
- `NA_5.0_or_older_clients_ALL.7z` (다수 구버전 묶음, 약 218 MB)
- `NA_4.03_french.exe`
- `Baram_Map_Editor.7z`, `Judge_Map_Editor.7z`, `mithiamapeditor-master.zip`
- `EPFTool.exe`, `BARAM.PAL`

실행 파일은 **직접 실행하지 말고** 정적 검사/추출 위주로 활용한다. 원본의 SHA는 `research/world-audit/acquired-original-files.json`, 추가 조사 원장과 대조한다.

## 사용자가 확정한 콘텐츠 대체 정책 (기존 기준 보완)

목표는 연도 증명만 하다가 게임 제작을 중단하는 것이 아니라, **1998~2001 한국 바람의나라와 최대한 유사한 오프라인 싱글플레이 완성**이다.

자료 적용 우선순위:

1. 당시 한국판 확인 자료
2. 이후 연도의 한국판 그래픽·기술·콘텐츠로 빈 부분 보완
3. 북미 NexusTK 및 검증 가능한 다른 복원 프로젝트 자료
4. 여러 스크린샷·버전·코드의 공통점으로 자체 제작/추정값을 명시하여 임시 구현
5. 더 정확한 자료가 들어오면 기존 적용값을 버리지 않고 이력과 함께 교체

단, 후대·북미 자료를 **1998년 한국 원본**이라고 허위 표기하지 않는다. 충돌하는 수치를 무조건 평균하지 않고 비교 가능한 같은 의미의 수치만 따로 처리한다. 영상·스크린샷만으로 구현 불가능한 동작도 추론 프로필로 제작해 실제 플레이를 진행한다.

## 다음 실제 작업 순서

- 먼저 보유 타일을 게임 런타임에서 테스트 지도 1장에 실제 배치해 표시한다.
- 확인된 `TileA/B/C.epf`를 전체 세트로 재사용하고, 비어 있는 지도는 이후 버전이나 직접 만든 타일로 대체한다.
- 한국 4.91 및 북미 4.03/4.66/4.95에서 캐릭터·몬스터·마법·아이템 EPF/팔레트 추출을 추가한다.
- 한 캐릭터 4방향 보행/공격/피격/사망과 토끼·다람쥐를 실제 런타임에 먼저 연결한다.
- 원본 서버·연구 메타데이터와 지도/충돌/이동/타격/아이템/상점을 통합하고, **실제 실행한** 검증 결과만 PASS 처리한다.
- `main`과 기존 연구 브랜치는 보존하고, 변경은 현재 개발 브랜치 계보에서만 진행한다.

**상태:** 사용자 원본 실제 업로드/Library 보관 = PASS, 타일 프레임 14,835 변환 = PASS, 비공개 Codex 작업폴더로의 전송 = 필요(이 채팅에서 자동 전송 불가), 게임 적용 = NOT_RUN.