# 실제 콘텐츠와 동작 경로

파일별 전체 색인: `file-inventory.json`. 각 행에 저장소·경로·바이트수·SHA256·확장자와 CSV 원시 레코드 수가 있다. CSV 수는 중복/비활성/시대 필터를 적용한 게임 내 개체 수가 아니다. `csv_raw_records_after_first`는 주석도 포함할 수 있으며 Project1998 핵심 표의 주석 제외 집계는 별도 JSON에 기록했다.

## Project1998 — 36905428ff59329be28c6a4579e41f4fd9e9a967

| 항목 | 실제 파일 | 직접 조사 결과 | 관련 구현 |
|---|---|---|---|
| 지형 | `game-data/maps/*.map`, `map_index.csv` | MAP2,039파일. 인덱스2,031행 모두 xs×ys×4와 파일 크기 일치. 바이트 동일 지형941종 | `Server/MapData.cs`, `MapStore.cs`, `MapCell.cs` |
| 지도 설정 | `game-data/Maps.csv`, `Warps.csv` | 설정9,850행, 워프4,824행. 지도설정 행을 실제 맵 수로 쓰지 않음 | `Server/Content.Maps.cs`, `Session.Movement.cs` |
| 몬스터 | `game-data/mobs.csv`, `Spawns.csv`, `AreaSpawns.csv`, `MobDrops.csv` | 몬스터716행, HP/경험치/외형/배치/드롭 필드 존재 | `Server/Content.Mobs.cs`, `World.cs`, `Session.Combat.cs`, `MobScript.cs` |
| 아이템 | `game-data/Items.csv`, `ItemParams.csv`, `item_verbs.lua` | 아이템2,544행, 장비·가격·아이콘 참조 필드 | `Server/Session.Items.cs`, `Session.Shop.cs` |
| 마법 | `game-data/Spells.csv`, `SpellLearnCosts.csv`, `SpellParams.csv`, `spell_verbs.lua` | 마법927행, 효과·학습·시전 자료 존재 | `Server/Session.Spells.cs`, `SpellScript.cs` |
| NPC | `game-data/NPCs.csv`, `npc_dialog.lua`, `NpcAbilities.csv` | NPC380행, Enabled/EraFeature로 활성 상태 별도 | `Server/NpcScript.cs`, `Session.Dialog.cs` |
| 성장/저장 | `LevelExp.csv`, `Paths.csv`, `PathGrowth.csv` | 경험치 표491행; 클래스/성장 표 존재 | `Shared/CharacterStore.cs`, SQLite 의존 |
| 시대 | `Sources.csv`, `EraFeatures.csv`, `ServerTuning.csv` | 출처45행. 날짜 설정으로 일부 콘텐츠 제한 | `Server/Era.cs`, `docs/common/Era-Gating.md` |
| 그래픽/음향 | 외형ID/팔레트/효과/음악 매핑표 | PNG5개는 MapEditor 설명 화면. 실제 EPF/DAT/WAV 게임팩과 클라이언트 EXE는 없음 | 클라이언트가 원작 아카이브를 로드해야 함 |
| 로그인/통신 | `LoginServer/`, `Shared/`, `Protocol.Tk495/` | 로그인과 게임 두 프로세스 | `Shared/NetBind.cs`, `TkAcceptor.cs`, `Server/Program.cs` |

README의 1,840지도/2,545아이템/368NPC/4,621워프와 현재 체크아웃 원시 집계는 다르다. 조사값은 실제 파일 기준이고, 로더가 필터한 수는 .NET 실행 전까지 미검증이다. 2,039맵이 모두 고유하거나 2001년 콘텐츠라는 뜻도 아니다.

## 다른 유효 자료

- RTK-Server: `rtkmaps/`, `rtk/src/map/`, `rtklua/Accepted/`, `database/2020-09-02-21-55-01_RTK.sql.bak`. 맵7,082파일은 바이트 기준2,660종. Lua907파일, C/H89파일. SQL은 로컬 파일 읽기만 수행했으며 DB import/서버실행은 하지 않았다. 사용자/운영 데이터가 있을 수 있어 SQL 원문을 공개하지 않는다.
- project1998-docs: `site/img/maps/*.webp` 지도2,025장, `site/img/item-icons*.png`, `mob-sprites.png`, `site/{items,mobs,spells,atlas}.html`, `tools/data/*.csv`. 그림 자료는 확보됐지만 배포 권한과 2001년 그림 일치 여부는 미확보.
- Baram_Legacy: `app/assets/images/monsters/{items,monsters}.xlsx`. ZIP/XML로 시트1의 기록 행 각각2,181/620 확인(헤더 포함, 개체 수 아님). `app/models/{item,monster,monster_drop}.rb`, `db/seeds.rb`로 목록 웹앱임을 확인. seeds는 외부 S3 import를 사용한다. NPC/마법/지도/전투 게임 엔진은 확보 못함.
- TKClassic: PNG724개는 비교·문서용 이미지 포함, 온전한 클라이언트팩이 아니다. `documentation/mappings/`, `Monster.ts`, `Tile.ts`, `FileHandlers/`로 리소스 변환 구조 확인.
- TKViewer/TKMapper/EPFViewer/NexusTKMapEditor: 실제 포맷 파서·렌더러·편집 코드는 존재하지만 자체 완성 게임이나 1998 원본 데이터 제공 여부와 구분한다.
- oldbaram/oldbaram_sunbi: `src_v2/eyes/`, `hands/`, `workers/`, `knownmaps.txt`는 현재 게임 화면 인식·키 입력 자동화 자료. 명칭 때문에 복원 원본으로 오인하면 안 된다.
