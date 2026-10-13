# 옛 바람의나라(1998~2001) 커뮤니티 소스 인수인계 — 2026-10-13

## 결정 및 목표

- 최종 목표: **사용자가 혼자 오프라인으로 즐길 수 있는, 1998~2001년 바람의나라와 최대한 비슷한 게임**.
- 1998년 12월판만 강제하지 않는다. 2001년판 NexusTK 4.95도 비교·구현 자료로 허용한다.
- 다만 1998년판 원작 수치·화면이라고 표기할 때만 1998년 확정 자료를 요구한다. 2001, 추정, 임시값은 다른 테이블로 관리한다.
- 서버/네트워크 설치 경험을 사용자에게 요구하지 않는다. 가능하다면 Windows 오프라인 원클릭 실행.
- 기존 `research/v1`, `research/archive`, 원본 무결성 파일, main 모두 보존.
- 본 문서는 **수집 계획 + 기초 저장소/라이선스 확인 결과**이지, 실제 12개 프로젝트의 소스 다운로드나 게임 실행 PASS가 아니다.

## 확보된 참고 저장소 목록

정본: `research/community_sources_20261013.json` (12개)
로컬 다운로드: `python tools/fetch_community_refs.py --list` 또는 `python tools/fetch_community_refs.py --all`
(다운로드는 사용자의 개발 환경/Work의 격리 워크스페이스에서 실행. 본 채팅에서 실행하지 않았음.)

| 우선 | 프로젝트 | 쓰임새 | 확인된 권리 상태 |
|---|---|---|---|
| P1 | [Project1998](https://github.com/project1998/Project1998) | 2001-07-09 NexusTK 4.95를 목표로 한 C# 서버·세계 규칙 및 콘텐츠 참고 | README상 명시 라이선스 없음. **코드/CSV 통합 보류** |
| P1 | [TKClassic](https://github.com/unkmc/TKClassic) | 옛 그래픽과 현재 그래픽의 매핑·변환 | GPLv3 / 게임 에셋은 별도 |
| P1 | [TKViewer](https://github.com/DizzyThermal/TKViewer) | DAT/EPF/MAP 등 리소스 포맷 확인 | 루트 LICENSE 미확인, 이용 범위 조사 |
| P1 | [TKMapper](https://github.com/DizzyThermal/TKMapper) | Godot 지도 편집기 | MIT |
| P1 | [EPFViewer](https://github.com/DizzyThermal/EPFViewer) | Godot 그림·애니메이션 뷰어 | MIT |
| P2 | [ServTK](https://github.com/ServTK/ServTK) | 서버 구조 대조 | GPLv2 |
| P2 | [TkServer](https://github.com/jeedee/TkServer) | 경량 서버 구조 | 루트 LICENSE 미확인 |
| P2 | [Baram_Legacy](https://github.com/mun5424/Baram_Legacy) | 옛 콘텐츠에 대한 참고 기록 | 루트 LICENSE 미확인 |
| P3 | [NexusTKMapEditor](https://github.com/ShadoMagi/NexusTKMapEditor) | 지도 편집 대체 후보 | 미확인 |
| P3 | [oldbaram](https://github.com/kimjs3374/oldbaram) | 바람 복원 자료 후보 | 내용·권리 미확인 |
| P3 | [oldbaram_sunbi](https://github.com/kimjs3374/oldbaram_sunbi) | 바람 복원 자료 후보 | 내용·권리 미확인 |
| P3 | [nexustk](https://github.com/jaggedsoft/nexustk) | 파일·통신 도구 후보 | 내용·권리 미확인 |

**원본 서버/게임이 포함됐다는 의미가 아니다.** 각 저장소의 README, 실제 코드, 저작권, 실행 여부를 별도로 검증해야 한다.

## 권한/보안 게이트

1. Public 저장소에 **원작 클라이언트, 원작 그래픽/음악, 비공개 파일, 타인의 무라이선스 소스/CSV를 대량 업로드하지 않는다.**
2. GitHub에서 보인다는 사실만으로 복제·재배포·2차 저작물 허가를 추정하지 않는다.
3. MIT 코드는 저작권 표시 및 허가 문구를 유지하는 등 조건을 준수한다. GPL 코드 통합은 전체 배포 방식과 GPL 의무를 먼저 검토한다.
4. 외부 프로젝트 코드는 우선 `.third_party_sources/` 폴더에 **로컬 연구용**으로만 내려받는다. `.gitignore`로 원격 커밋 차단.
5. 실행 파일, DLL, 빌드 스크립트는 내용을 검토하고 격리 환경에서 시험한다. 출처 불명 실행 파일을 사용자 PC에서 실행하지 않는다.
6. 외부 개발자의 소스가 README에 `no license`라고 되어 있으면 별도 허가가 있기 전까지 프로젝트 코드나 데이터로 복사하지 않는다.
7. 유료 서비스, 클라우드 서버, 운영 배포, 공개 배포, main 병합은 사전 승인.

## 담당 — Work 먼저

**Work 조사·수집 작업 지시:**

> 기존 GitHub `irewon1-lgtm/baram-1998-singleplayer`를 열고 `research/community-sources-20261013` 브랜치부터 이어간다. 원본 자료 및 main은 수정하지 않는다. `research/community_sources_20261013.json`의 12개 GitHub 저장소를 각각 검사하라. 가능하다면 격리 워크스페이스에서 `tools/fetch_community_refs.py --all`로 로컬 다운로드하고, 실제 다운로드된 각 SHA, 소스 파일 개수, 라이선스/이용조건, 바이너리·자산 포함 여부, 실행/빌드 선행조건, 실제 확인한 주요 데이터 파일 경로를 기록하라. 바람의나라/Baram/NexusTK/Kingdom of the Winds/4.0/4.95/old client 검색으로 다른 유용한 저장소도 추가 탐색하라. 1998년·2001년·불명 버전 분리, 포크/중복 제거, 게임원본-개발도구-후대 재구현 구분을 엄수하라. 결과는 `research/community-audit/`에 출처와 검증 상태를 포함해 저장하라. 외부 코드를 Public 저장소에 일괄 복사하거나 원작 자산을 올리지 마라. 검증되지 않은 빌드/실행/파일 검사를 PASS로 표시하지 마라. 오류가 나면 원인을 남기고 실패 단계에서 재개하라. 결과는 조사 브랜치에만 커밋하라.

**Work 산출물 최소조건:**

- `research/community-audit/repository-audit.json`: 프로젝트별 commit SHA, LICENSE 여부, 소스/데이터/아트 경로와 확인 상태
- `research/community-audit/reuse-matrix.md`: **직접 재사용 가능 / 별도 도구로 실행 / 설계 참고 / 권한 불명** 4등급 분류
- `research/community-audit/content-index.md`: 지도·몬스터·아이템·마법·NPC·UI·그래픽·효과음의 실제 근거 경로
- `research/community-audit/gaps.md`: 게임 실제 시작에 필요한 외부 클라이언트/라이선스/맵/아트/데이터 부족 목록
- `research/community-audit/source-quality.md`: 1998/2001/후대 출처 등급 및 서로 충돌하는 주장
- 실제 clone/빌드/실행 여부는 각각 `PASS | FAIL | BLOCKED | NOT_RUN`으로 별도 판정

## 담당 — Codex 다음

**Codex 개발 작업 지시:**

> 위 Work 조사 산출물을 읽고 먼저 2개의 구현 경로를 평가하라.
>
> A) **로컬 NexusTK 4.95 클라이언트 + 호환 로컬 서버**: 법적으로 사용할 수 있는 클라이언트와 코드가 확보된 경우에만 검토. 네트워크 서버 운영/대외 개방 없이 localhost 원클릭 시작. 기존 Project1998 코드의 무허가 복제 금지.
>
> B) **Godot 4 단일 실행 파일**: 공인 사용 가능 개발도구와 자체 제작 또는 사용 허가된 리소스로 1998~2001 시기의 조작감과 외형을 재현한다. 1998/2001 정확한 데이터와 임시값을 분리한다.
>
> 라이선스와 리소스 확보 가능성, 게임 유사도, Windows 설치 난도, 오프라인 실행, 테스트 난도, 유지보수를 실제 근거로 비교하고 선택하라. 최우선은 일반 사용자가 한 번 실행해서 옛 바람의나라처럼 이동·사냥·성장을 할 수 있는 것이다. 1개 마을/초보필드에서 이동→벽 충돌→몬스터 전투→경험치·레벨업→아이템→저장·불러오기까지 **실제 플레이되는 구간**을 feature 브랜치에서 제작하라. 구현을 완료했다면 자동 테스트와 실제 실행 증거를 남겨라. 수치와 화면의 원작 일치 검증은 별도 상태로 구분하라. main 병합/외부 배포/과금 금지.

## 실행 판단

- **현재 완료:** 연구 후보 12개 GitHub 링크와 라이선스 4건(MIT 2, GPL 2) 확인, 프로젝트 설명서 조사, 수집용 스크립트 저장.
- **현재 미완료:** 외부 저장소 12개 전체 로컬 clone, 코드 비교, 원작 자산 사용권, Project1998 실게임 빌드/접속, Godot 게임 제작.
- **선택해야 할 게임 엔진:** Work의 권한·자산 및 클라이언트 가용성 보고 전까지 `HOLD`; 2001을 허용한다고 1998 원본 검증을 없애지는 않는다.
