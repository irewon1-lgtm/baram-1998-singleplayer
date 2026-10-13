# Codex 제작 시작 지시

## 현재 선택과 경계

`feature/offline-prototype` 등 새 개발 브랜치를 이번 조사 브랜치에서 만들되 main을 수정하지 않는다. 기본 경로는 **Godot 싱글게임 + MIT 도구의 선별 재사용**. 클라이언트·Project1998 사용권이 확보되면 기존 클라이언트+로컬 서버 경로를 재평가한다. 유료 API·서버·운영 배포 없이 진행한다.

기존 `data/strict_1998_rules.json`과 `research/v1/`은 보존. 신규 게임 데이터는 `era=1998_confirmed | 2001_reference | later_reference | provisional`로 구분하고, 각 엔티티에 출처·원본 커밋·파일 경로·규칙 근거·권리 상태를 붙인다. 후대 자료의 숫자를 1998 원본 수치로 옮기지 않는다.

## 자료 복구/설치

이번에 받은 외부 checkout의 경로는 repository-audit.json에 기록했다. 새 환경에서는 Git/Python을 설치하고 공개 저장소 밖으로 같은 커밋을 복구한다.

```bash
git clone --branch research/community-sources-20261013 --single-branch https://github.com/irewon1-lgtm/baram-1998-singleplayer.git
cd baram-1998-singleplayer
python tools/refetch_audited_sources.py --dest ../baram-local-references --all-audited
python tools/audit_local_sources.py --root ../baram-local-references --out ../audit-check
python tools/check_project1998_content.py --source ../baram-local-references/project1998/Project1998 --out ../audit-check
```

복구 스크립트는 clone 후 원본 SHA에 detached checkout한다. 기존 경로의 SHA가 다르면 멈추며 덮어쓰지 않는다. 설치 스크립트/게임 바이너리는 실행하지 않는다. GitHub에 원본 commit이 남아 있어야 복구 가능하다. 네트워크 없이 복구할 수 있는 원본 bundle은 이번에 작성하지 않았다.

| 대상 | 설치·실행 선행조건 | 이번 실제 상태 |
|---|---|---|
| Project1998 | .NET8 SDK, NuGet 복원. Server/LoginServer를 별도 빌드. 그래픽 플레이는4.95 클라이언트 추가 필요 | SDK 없음, 빌드/테스트 BLOCKED. 설치 절차는 deep-review 참조 |
| TKMapper/EPFViewer | 해당 project.godot 기능과 맞는 Godot. EPFViewer 현재4.7 지정. Godot에서 import 후 main scene 실행. NexusTK 리소스 경로 설정 필요 | 엔진 없음, 실제 import/GUI NOT_RUN |
| TKClassic | Node/TypeScript, npm 의존, 로컬 Baram/Nexus DAT, README의 extract/convert 작업 | 패키지 설치·변환 NOT_RUN. 파일 단위 비교만 완료 |
| TKViewer | Java8+ / Maven, 루트 install 후 tk-viewer package, JAR실행 | NOT_RUN |
| ServTK | Windows Visual Studio/.NET Framework4.5/C++ crypto 프로젝트 | NOT_RUN |
| TkServer | Ruby, sqlite3/ORM 등 소스의 require 의존을 별도 확인 후 login_server.rb/game_server.rb | NOT_RUN, 불완전 서버라 우선순위 낮음 |
| NexusTKMapEditor/mithiamapeditor | Windows/.NET WinForms 도구. 원작 리소스 추가 필요 | NOT_RUN, 무라이선스라 통합 보류 |
| RTK-Server | C/Lua/MySQL 및 저장소별 의존. README의 오래된 VM설치와 Docker 구성을 별도 검토 | NOT_RUN, 원클릭 개발 기반으로 선택하지 않음 |
| Baram_Legacy | Ruby/Rails와 DB. 데이터 XLSX는 로컬 확보 | 앱실행 NOT_RUN, 내용 연구만 |
| oldbaram 두 개 | OCR/YOLO/키입력 자동화 계열 | 게임복원 설치 대상 제외 |
| jaggedsoft/nexustk·ntk-networking | Node/TypeScript 및 네트워크 프로토콜 의존 | 외부 게임 서버에 연결하지 않았음 |
| project1998-docs·ntk-utils | 문서/웹 보조 자료 | 게임 클라이언트 대체 불가 |

## 구현 순서와 각 종료조건

1. **읽기·그리기 어댑터**: Godot 빈 프로젝트와 원본과 분리된 자체 임시 타일/캐릭터로 2D격자 이동. MIT FileHandlers의 의존성만 도입하며 LICENSE/저작권 고지 첨부. P1998 headerless LE맵과 TKMapper BE헤더 맵을 서로 다른 타입으로 정의. 자체 제작 fixture에서 크기·4방향·pass·object·잘못된 길이 처리를 실제 실행해 확인.
2. **첫 플레이 구간**: 자체 작성 마을1/초보필드1, 몬스터3종, 아이템5종, 공격/회복 마법2개, 상점/NPC1개. 숫자는 provisional. 이동→벽 충돌→전투→HP/MP→경험치/레벨업→드롭→장비→상점/대화까지 연결한다. 수량은 MVP 구현 범위이지 원작 수량이 아니다.
3. **독립 저장**: 서버 불필요한 단일 게임상태, 로컬 세이브와 버전/백업. 게임종료→재시작→위치·능력·인벤토리 복구, 손상세이브 처리 실제 확인.
4. **고증 콘텐츠 도입**: 한국/미국 명칭 및 맵·외형·시대 차이를 대조표로 작성. 현재 원본게임 데이터/아트 미허가 목록은 그대로 보류하고 허가된 범위만 입력. 임시 아트와 원본 일치 검증은 별도 상태.
5. **실사용 포장**: Windows 오프라인 실행 파일, 휴대폰이 필요하면 조작 UI/성능을 별도 목표로 추가. 현재는 PC 원클릭이 기존 인계 목표. 인터넷 차단 상태에서 전체 구간·저장·종료/재시작 시험. 화면 캡처와 사용한 커밋/입력/로그를 남긴다.

실패하면 실패 증거를 남겨 해당 단계의 원인만 수정하고 재시험한다. 데이터/SDK/사용권 장벽은 BLOCKED로 유지한다. 게임 화면을 실행하지 않고 테스트 개수만으로 게임완성 PASS를 선언하지 않는다.

## 인계 첫 작업

`reuse-matrix.md`, `project1998-deep-review.md`, `gaps.md`를 읽은 뒤 Godot 환경을 확인하고 첫 자체 fixture와 임시 아트 이동 장면부터 구현한다. Project1998/RTK의 소스·CSV·원작 이미지를 공개 프로젝트에 복사하지 않는다. 타일·스프라이트가 없다고 무라이선스 자료로 대체하지 않는다.
