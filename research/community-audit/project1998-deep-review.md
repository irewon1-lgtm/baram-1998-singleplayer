# Project1998의 오프라인 2001 게임 활용 평가

결론: **2001 NexusTK 동작을 조사하는 가장 강한 후보지만, 현재 그대로 가져와 실행 가능한 게임으로 납품할 수 없다.** 서버 소스와 세계 데이터는 실제 확보됐고, 클라이언트와 재사용 허가는 미확보다. 한국 바람의나라와 미국판 NexusTK의 콘텐츠·언어·발전 시점을 별도로 비교해야 한다.

## 확보와 직접 확인

커밋 `36905428ff59329be28c6a4579e41f4fd9e9a967`. 총2,770파일, C#333파일, Python195, CSV90, Lua4. 핵심 CSV/맵 실측은 `project1998-content-check.json`, `project1998-map-check.json`.

실제 `Session.Movement.cs`에는 보행 요청과 충돌/워프 처리, `Session.Combat.cs`에는 공격 처리, `Session.Spells.cs`에는 마법, `Session.Items.cs`에는 아이템 처리가 있다. `Shared/CharacterStore.cs`와 SQLite 패키지 참조는 로컬 상태 저장 구조의 근거다. 정적 코드 존재 확인이며 실제 플레이 성공은 아니다.

`Directory.Build.props`는 net8.0. Shared는 BCrypt.Net-Next4.0.3·Microsoft.Data.Sqlite8.0.10, Server는 MoonSharp2.0.0, Tests는 xUnit 등 NuGet 의존이 있다. 첫 빌드/의존 다운로드 이후에도 오프라인 재시작 시험을 별도로 해야 한다.

## 2001년 고증의 한계

프로젝트 목표는 2001-07-09 NexusTK4.95. 게임 데이터의 상당 부분은 후대 RTK/Mithia7.x에서 생성됐다. 이름·구조·배치와 실제 2001 수치·외형은 별개다. README와 game-data README 스스로 후대 밸런스·아이콘ID 차이를 설명한다. 시대 제한 설정을 켜도 모든 표의 수치와 맵이 2001년 원본으로 바뀌는 것은 아니다.

문서 내부 충돌도 있다. `docs/4.x/README.md`는 4.95 로컬 맵 사용을 설명하지만 `Server/MapData.cs`는 로컬 파일이 캐시이며 양쪽 클라이언트에 지형을 스트리밍한다고 설명한다. 현재 구현을 먼저 읽고 실제 4.95 클라이언트 요청으로 재검증해야 한다. 지도 크기 검사가 네트워크/렌더링 검증을 대신하지 않는다.

## 경로 A: 기존 클라이언트 + 로컬 서버

전제: 사용할 수 있는4.95 클라이언트/아카이브를 사용자 측에서 확보하고, Project1998 코드·데이터를 수정/사용할 허가 범위를 확인. 이번 체크아웃에는 해당 클라이언트가 없다. 별도 `Essorcal/project1998-testclient`는 clone 실패(공개 접근 불가), 직접 테스트 클라이언트도 확보 못했다.

준비 후에는 .NET8과 패키지를 설치하고 다음 순서로 시험한다. 아래는 **실행 계획이며 성공 명령 이력이 아니다**.

```powershell
dotnet build Server/Server.csproj
dotnet build LoginServer/LoginServer.csproj
dotnet test Tests/Tests.csproj
dotnet run --project Server -- --selftest
$env:P1998_BIND='127.0.0.1'
dotnet run --project LoginServer -- --ports 2000,2001
# 별도 터미널에도 같은 P1998_BIND 설정
dotnet run --project Server -- --ports 2005,2006
```

게임의 기본 바인딩은 전체 인터페이스다. 오프라인 목적에는 loopback을 명시한다. `run-server.bat`만 무조건 실행시키는 설치안은 채택하지 않는다. 4.95 Inter.dat의 IP 교체 도구는 기본127.100.10.1을 사용하는 반면 Serve.ps1은127.0.0.1 기본이다. **클라이언트 대상 주소와 서버 바인딩을 같은 주소로 맞추거나, loopback 주소별 청취를 검증**해야 한다. 사용할 IP 문자열 길이도 Tools의 조건을 확인한다.

통합 런처는 두 프로세스 시작/종료, 포트 중복, 저장 DB, 클라이언트 실행을 감싼다. PC 인터넷을 끊고 로그인→캐릭터 생성→이동→공격→마법→상점→저장→프로세스 종료→재시작을 실측해야 원클릭 오프라인 가능으로 판정할 수 있다. Windows4.95 실제 화면/소리/조작 시험도 필요하다.

현재 상태: SDK 부재로 빌드/테스트 BLOCKED. 실제 클라이언트 플레이 NOT_RUN. 라이선스/클라이언트 확보 BLOCKED. 작성자의 Playable 주장은 별도 주장으로 기록하며 우리 PASS에 포함하지 않는다.

## 경로 B: Godot 단일 게임

MIT 지도·EPF 도구에서 필요한 부분을 도입하고 자체 게임 로직을 작성한다. 원작/무라이선스 파일을 코드로 복제하지 않는다. 자료의 ID·규칙·시대 차이를 분석해 독립 구현하고 권리 확인된 자료만 게임 데이터로 넣는다. 현재 확인한 EPFViewer의 project.godot은4.7 기능을 지정하므로 임의의 Godot4.x에서 실행된다고 약속하지 않는다.

중요 호환 문제: Project1998 MAP은 인덱스에서 크기를 얻는 헤더 없는 LE4바이트/셀이고, TKMapper의 MapFileHandler.gd는 BE크기 헤더와4/6바이트 셀을 읽는다. **그대로 열 수 있다고 판정하지 않는다.** 자체 어댑터로 두 형식을 명시하고 ground 하위14비트/상위2비트 pass와 object를 분리한다. 맵 숫자와 실제 타일 아트ID·충돌은 렌더링 시험으로 맞춘다.

현시점 추천은 B. A는 그래픽·조작 유사도를 빠르게 높일 가능성이 있지만 확보조건에 막혀 있다. B는 제작을 시작할 수 있고 단일 저장·실행 구조를 만들기 쉽다. 원본 아트가 미확보인 상태에서는 외형 일치까지 완료로 표시하지 않는다.
