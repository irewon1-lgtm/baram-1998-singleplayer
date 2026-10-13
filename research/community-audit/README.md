# 1998~2001 싱글게임 제작 자료 조사 결과

**자료 수집·파일 조사·Codex 인계는 완료. 게임 실행·원본 일치·전체 재사용권 확보는 미완료.**

기존12개 모두 clone 및 추적파일 바이트/해시 검사 완료. 추가7개도 실제 수집하여 총19개 checkout, 31,098파일을 조사했다. 이 수에는 포크, 후대 데이터, npm 의존성이 포함돼 있으며 독립 게임프로젝트19개가 있다는 뜻은 아니다. 포크/공통 파일은 독립 후보에서 제외하고 원본은 삭제하지 않았다.

핵심 발견:

- Project1998에는 실제 맵2,039파일, 몬스터716/아이템2,544/마법927/NPC380 원시 행이 있다. 인덱스2,031개 지형은 파일 크기 검사 통과. 해당 데이터는 후대 RTK도 활용하며 한국2001 원본이라고 확정할 수 없다.
- Project1998에는 완성된 그래픽 클라이언트가 없고 명시 라이선스도 없다. 자체 실플레이 PASS 아님.
- MIT인 TKMapper/EPFViewer 코드는 제작 재사용 후보. 둘의 현재 Godot 설정은4.7이며 Project1998 맵과 형식이 달라 어댑터 필요.
- RTK 원본 서버/콘텐츠와2,025장 Project1998 문서 지도 이미지도 실제 수집. Public에는 원문 코드·그림 대신 경로/해시/분석만 저장.
- oldbaram 두 개는 게임 재구현이 아니라 자동화 도구. 이름만 보고 복원 게임으로 판단하면 안 된다.

| 검증 | 결과 | 증거 |
|---|---|---|
| 원래12개 수집·파일 읽기 | PASS | repository-audit.json, file-inventory.json |
| 추가7개 수집·파일 읽기 | PASS | 같은 파일; 유효성/중복은 별도 분류 |
| Git 객체 무결성 | 19/19 PASS | git-integrity-checks.json |
| P1998 맵 크기 대조 | 2,031/2,031 PASS | project1998-map-check.json |
| P1998 핵심CSV 파싱 | PASS (원시 주석 제외 행 집계만) | project1998-content-check.json |
| P1998 빌드/단위시험 | BLOCKED | .NET SDK 명령 없음, execution-results.json |
| 클라이언트 실제 플레이 | NOT_RUN | 클라이언트 미확보 |
| Godot 도구 실제 GUI | NOT_RUN | 엔진 명령 없음 |
|1998 기존 조사 구조/아카이브 해시 | PASS | validate_research.py 실제 실행 |
| 전체2001/한국 원작 정확도 | UNVERIFIED | source-quality.md |
| 전체 코드/에셋 재사용 허가 | BLOCKED | reuse-matrix.md, gaps.md |

다음 작업: [재사용 목록](reuse-matrix.md) → [Project1998 상세 평가](project1998-deep-review.md) → [설치·구현 지시](install-and-implementation.md). 실제 콘텐츠는 [파일 근거 목록](content-index.md), 미확보 자료는 [gaps.md](gaps.md).

검증 조건은VERIFICATION_CONTRACT.md. 기존1998 연구 원장/ZIP/main은 보존하며, 유료 서비스·게임 운영 배포는 하지 않았다.
