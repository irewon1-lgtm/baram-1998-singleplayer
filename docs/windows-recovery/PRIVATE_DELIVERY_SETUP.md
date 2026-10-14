# Windows 자동 빌드의 남은 1회 연결

코드·워크플로는 구현됐지만, 비공개 입력 및 전달 인증은 아직 연결되지 않았다.
이 파일은 활성화 완료 보고가 아니다. 원본 자산은 공개 저장소에 넣지 않는다.

## 준비된 구조

- 개발: `irewon1-lgtm/baram-1998-singleplayer`, `codex/game-core`.
- 비공개 입력/다운로드 저장소 예정 이름: `irewon1-lgtm/baram-windows-private`.
- 공개 소스 변경 시 `windows-source.yml`은 직접 생성한 그림으로 Windows 소스 시작 및 포장 검사만 한다.
- `windows-player.yml`은 비공개 저장소임을 API로 재확인한 뒤 원본을 읽는다.
- 현재 소스에서 EXE 생성 → 네이티브 EXE 시작 → 정상 입력에 따른 생성/이동/NPC/맵전환/전투/획득/저장 → 별도 프로세스 복구 → ZIP CRC/해시 순서다.
- 하나라도 실패하면 플레이어 ZIP을 공개하지 않는다. 실패 로그는 비공개 저장소의 draft diagnostic release에 보존한다.
- 성공한 ZIP은 비공개 Release에 저장한다. GitHub 로그인 후 Release의 ZIP을 누르면 된다. 과거 버전은 교체하지 않는다.
- 실제 Windows GUI, 더블클릭, 화면/음향, 사용자 PC 호환성은 자동 headless 검사와 별도로 미검증이다.

## Work가 이어서 수행할 설정

1. GitHub 웹 설정 경로 사용이 승인되면 계정을 확인하고 위 비공개 저장소를 생성한다. 공개 생성 후 변경하는 방식을 쓰지 않는다.
2. 준비된 private runtime seed의 `runtime/` 및 `.gitattributes`를 비공개 저장소에 보존한다. 그래픽·음향·콘텐츠 943개 원본 바이트는 그대로 유지한다.
3. 해당 비공개 저장소 하나에만 Contents read/write와 Metadata read 권한을 갖는 인증을 연결한다. 토큰을 대화/로그/공개 Git에 출력하지 않는다.
4. 소스 저장소 환경 `baram-windows-private`에 `BARAM_PRIVATE_REPO_TOKEN` Secret 및 `BARAM_PRIVATE_REPOSITORY` 변수(다른 실제 이름이면 그 이름)를 등록한다. 개발 브랜치에서만 이 환경을 사용한다.
5. 동일 수정 소스의 전체 Windows EXE 자동 실행을 실시하고 오류가 있으면 원인부터 최소 수정한다. Linux나 fixture 결과로 Windows 전체 PASS를 쓰지 않는다.
6. 통과 뒤 새 비공개 ZIP 다운로드 링크를 제공한다. 공개 Actions artifact에 원본/화면/음향/저장/게임 ZIP을 넣지 않는다.

현재 연결된 GitHub 도구에는 저장소 생성·환경 Secret 설정·Release 업로드 기능이 없다.
Git CLI push도 인증 부재로 실패했다. 코드 게시 및 공개 Actions 실행은 연결된 GitHub 도구로 가능했다.
이 장벽을 Windows 시험 실패나 실제 GUI 통과로 바꾸어 보고하지 않는다.

## 이후 Codex 업무

Windows 변환을 Work에 다시 요청할 필요가 없도록 위 연결은 한 번만 설정한다.
게임 코드 변경은 개발 브랜치에 정상 커밋하면 된다. 원본 자산/비공개 콘텐츠를 변경한 경우에는 개발의 일부로 비공개 runtime 및 해시 명세도 같은 버전으로 갱신한다.
`.gitattributes`의 `runtime/** -text`를 보존해 Windows checkout의 CRLF 변환으로 원본 해시가 변하지 않도록 한다.
누락되거나 손상된 비공개 runtime은 자동으로 빌드/배포를 중단한다.
