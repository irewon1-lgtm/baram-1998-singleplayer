# 시대·독립성·중복 판정

- 기존1998 조사 원장과 ZIP을 그대로 보존. 신규 미국판 자료로 원본 확정 필드를 덮어쓰지 않음.
- Project1998: 2001년4.95 목표를 가진2026 재구현. 실제 원작 서버 소스 아님. 시대 설정과 후대 RTK숫자 혼합을 동시에 표시.
- RTK-Server: 후대 Mithia/7.x 기준, 구조/포맷 비교용. Project1998가 여기서 데이터를 가져왔으므로 둘의 같은 값은 독립적인 두 근거가 아니다.
- project1998-docs: 같은 서버 CSV에서 생성된 목록과 클라이언트 기반 렌더. 별도 저장소여도 독립2001 데이터 근거로 세지 않음.
- TKClassic: 한국 Baram과 Nexus 리소스 비교용. pre5.0 외형 관련성이 있으나 모든 그림의1998 날짜가 확정된 것은 아님.
- Baram_Legacy: 한국 명칭·목록 연구에 유용. 2016년 이후 웹앱이라는 저장소 구조가1998/2001 원본 데이터의 날짜를 증명하지는 않음.
- 이름만 oldbaram인 두 저장소는 자동화 도구로 확인, 복원 엔진 후보에서 제외.

## 포크·중복 정리(파일은 삭제하지 않음)

GitHub API에서 unkmc/Project1998와 Essorcal/Project1998는 project1998/Project1998의 포크로 확인해 신규 수집 후보에서 제외. ShadoMagi/NexusTKMapEditor는 nmanley/mithiamapeditor 포크여서 원류를 추가 확인하고 한 계열로 묶음. olds463/EPFViewer는 TKViewer의 포크로 확인, GPL Python뷰어 차이는 기록하지만 독립 게임자료로 세지 않음.

RTK-Server-1은 API상 fork=false이나 실제 파일 대조에서 공통8,303경로 중8,298이 바이트 동일. 같은 자료 계열로 집계하고 바뀐5개 공통파일과 별도경로는 삭제하지 않음. oldbaram과oldbaram_sunbi는 경로가 바뀐 동일 바이트 코드도 다수 있어 해시 색인으로 중복 묶음.

`cross-repository-duplicates.json`에 저장소를 넘는 동일 SHA256 경로가 모두 기록돼 있다. 빈 파일/공통설정도 포함하므로 그것만으로 전체 프로젝트 동등성을 판정하지 않는다. npm 의존성도 별도로 포함되며 게임콘텐츠 수에 더하지 않는다.

## 추가검색 범위

`search-results.json`과`search-results-extra.json`에 실제 GitHub 검색어·응답 목록 보존. NexusTK/Kingdom of the Winds/Project1998/한국 게임명/서버/1998/2001을 조사. 검색 결과 첫30~50개 범위이므로 GitHub 전체를 빠짐없이 조사했다는 뜻은 아니다. 자동화·보조웹앱·무관한 RTK GPS저장소·동명 프로젝트는 자료 후보에서 제외.

추가 검색의 ruddlf221-prog/-는 size0 메타데이터로 유효한 소스가 없음을 확인. Essorcal/project1998-testclient는 README에 링크가 있지만 현재 공개 다운로드 불가. 이를 수집 PASS로 집계하지 않음.
