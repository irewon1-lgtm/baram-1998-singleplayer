# 재사용 판정

모든 경로는 각 외부 저장소 기준. 공개 프로젝트에는 이번 조사에서 외부 코드나 게임 파일을 복사하지 않았다. 전체 커밋과 파일 해시는 `repository-audit.json`, `file-inventory.json` 참조. PASS는 수집/파일 검사에만 적용된다.

| 프로젝트 | 실제 확보 | 코드 판정 | 콘텐츠·그래픽 판정 |
|---|---|---|---|
| Project1998 | 2,770파일, C#333, Python195, CSV90, Lua4, 맵2,039 | 루트 LICENSE 없음, README도 미선택 명시. 직접 통합 보류 | 맵·CSV는 원작/RTK 파생. 연구용, 공개 복제 금지 |
| TKClassic | 777파일, TypeScript29, PNG724, CSV7 | GPLv3 조건부 재사용 또는 별도 도구 | PNG/매핑은 원작 파생 가능. GPL을 에셋 허가로 해석하지 않음 |
| TKViewer | Java35, Kotlin19, 총64파일 | 루트 LICENSE 없음. 참고용 | 뷰어이며 완성 클라이언트/콘텐츠팩 아님 |
| TKMapper | 총214파일, 자체 GDScript35 | MIT 직접 재사용 후보, LICENSE 고지 유지 | 실제 게임 DAT/EPF는 외부 필요. 리소스 권리 별도 |
| EPFViewer | 총147파일, 자체 GDScript50 | MIT 직접 재사용 후보, LICENSE 고지 유지 | 스프라이트 뷰어. 게임 그래픽팩 아님 |
| ServTK | 총52파일, C#23(생성코드 포함), C1/H1 | GPLv2 조건부. Windows .NET4.5/C++ Crypto 의존 | 완전한 게임 콘텐츠팩 없음 |
| TkServer | 총16파일, Ruby13, SQLite1 | 루트 LICENSE 없음. 구조 참고 | 경량 로그인/패킷/이동 뼈대. 완성 게임 아님 |
| Baram_Legacy | 총225파일, Ruby98, XLSX2 | 루트 LICENSE 없음. 참고용 | 한국 콘텐츠 연구 가치. 데이터 시트 존재, 게임 실행 코드 아님 |
| NexusTKMapEditor | 총90파일, C#64 | 무라이선스, nmanley/mithiamapeditor의 포크. 통합 보류 | 지도/아카이브 편집 도구 |
| oldbaram | 총463파일, Python370 | 무라이선스, 제작 기반에서 제외 | 자동사냥/입력 자동화. 원작 게임 서버 소스가 아님 |
| oldbaram_sunbi | 총285파일, Python245 | 무라이선스, 제작 기반에서 제외 | oldbaram과 대량 코드 공유. 같은 자동화 계열 |
| jaggedsoft/nexustk | JavaScript3, PCAP4, 총7파일 | 무라이선스, 참고용 | 네트워크 클라이언트 실험. 온라인 호스트 사용 코드 실행 안 함 |
| RTK-Server (추가) | 총8,404파일, MAP7,082, Lua907, C42/H47 | 루트 LICENSE 없음. 참고용 | 후대 Mithia/7.x 자료. 1998~2001 원본 수치로 채택 금지 |
| RTK-Server-1 (추가) | 총8,361파일 | 위 저장소와 공통8,303경로 중8,298 동일. 별도 후보 집계 제외, 차이는 보존 | 같은 데이터 계열, 삭제하지 않음 |
| project1998-docs (추가) | 총2,081파일, 지도WEBP2,025, PNG9 | 무라이선스, 참고용 | 게임 클라이언트에서 렌더한 그림이라고 README 명시. 재배포 허가 미확보 |
| ntk-networking (추가) | 총7,005파일(대부분 node_modules), 자체코드19 | package.json에 ISC만 선언, 루트 허가문 없음. 통합 전 확인 필요 | 네트워킹 엔진. 게임 맵 아님; .map300은 JS source map |
| ntk-utils (추가) | 총48파일, 코드24 | package.json MIT만 선언, 루트 허가문 없음. 확인 필요 | 웹 검색/보조 서비스. 게임 제작 우선순위 낮음 |
| olds463/EPFViewer (추가) | Python3, GPLv3 LICENSE, 총7파일 | GitHub상 TKViewer 포크, 별도 유사게임 후보 제외 | 뷰어 대안으로 기록만 유지 |
| mithiamapeditor (추가) | 총82파일, C#61 | 무라이선스, NexusTKMapEditor 원류 | 도구 계열 중복으로 신규 게임 후보에 포함 안 함 |

`docs/license_schema.sql`은 oldbaram의 사용자 이용권 인증 DB 스키마다. 오픈소스 LICENSE가 아니다. node_modules의 허가문도 상위 프로젝트 자체 코드 권리를 부여하지 않는다.

## Codex가 바로 검토할 재사용 파일

- TKMapper: `FileHandlers/{DatFileHandler,EpfFileHandler,PalFileHandler,MapFileHandler,BaseMapFileHandler,SObjTblFileHandler,TileTblFileHandler}.gd`, `DataTypes/`, `Renderers/`. 현재 체크아웃의 LICENSE는 MIT. 의존성 그래프와 Godot autoload를 함께 확인한 뒤 필요한 범위만 고지와 함께 도입.
- EPFViewer: `FileHandlers/`, `DataTypes/`, `Resources/`, `Renderers/`. MIT. 두 도구가 공유하는 파일은 해시 중복 원장에서 확인하고 한 계열만 선택.
- `addons/godot-sqlite/`는 별도 MIT LICENSE 존재. 외부 바이너리는 이번에 실행하지 않았으며 파일 해시만 확보했다. 필요할 때 정식 빌드/공급경로 검증 후 사용.
- TKClassic: `FileHandlers/`, `classic.ts`, `Monster.ts`, `Tile.ts`, `analyzeMappings.ts`. GPLv3 도구로만 먼저 검토. 원작 DAT·PNG·CSV는 승인된 코드 범위에 자동 포함하지 않음.

최우선 선택: **MIT Godot 도구의 필요한 부분 + 새로 작성한 싱글게임 코드**. Project1998를 그대로 게임 기반으로 복사하는 경로는 현재 허가가 없어 막혀 있다.
