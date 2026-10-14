# Windows x64 영구 자동 빌드와 비공개 전달

개발 브랜치 `codex/game-core`의 push가 Windows 빌드·시작 검사·게임 회귀·ZIP 게시를 자동 시작한다. Windows 변환을 매번 Work에 다시 요청할 필요가 없다. 수동 GUI 플레이 관찰은 자동 검사와 구분한다.

## 연결된 공급과 전달 경로

- 소스: `irewon1-lgtm/baram-1998-singleplayer`, `codex/game-core`.
- 원본 입력과 완성 ZIP: PRIVATE `irewon1-lgtm/baram-windows-private`.
- 소스 환경: `baram-windows-private`. 배포 허용 브랜치는 `codex/game-core` 하나다.
- 환경 변수 `BARAM_PRIVATE_REPOSITORY`와 Secret `BARAM_PRIVATE_REPO_TOKEN`을 연결했다. 토큰은 비공개 저장소 하나에만 Contents read/write 및 Metadata read 권한을 갖는다. 계정 권한이나 다른 비공개 저장소 권한은 없다. 토큰값은 코드·대화·로그에 기록하지 않는다.
- 원본 seed 8개 조각과 해시 명세를 비공개 저장소 커밋 `2361eb784b33613de2164421561eda728739f4e4`에 보존했다. 원격 파일의 Git blob SHA·크기도 로컬 바이트와 대조했다.
- `tools/restore_private_runtime.py`가 각 조각과 전체 ZIP SHA256, CRC, 추출 경로를 검사한 뒤 `vault/runtime/`으로 복원한다. 입력만 분할하며 플레이어 다운로드는 하나의 ZIP이다.
- `.gitattributes`의 `*.part* -text`와 `runtime/** -text`를 보존한다. 원본 그래픽·음향·콘텐츠 943개는 빌드 전후 해시로 보호한다. 사용자 저장은 빌드 입력과 전달 파일에 포함하지 않는다.

## 매번 수행하는 게이트

1. 비공개 저장소 여부와 인증을 확인한다. 공급·전달 대상이 public이면 중단한다.
2. 현재 소스와 정확히 맞는 build_info를 만들고 Godot 4.6.3으로 Windows AMD64 EXE를 export한다. 맵 캐시를 같은 콘텐츠 변환 코드로 생성한다.
3. 실제 Windows 러너에서 EXE를 일반 창 모드로 실행해 초기화·게임 진입·렌더링 프레임을 검사한다. 화면 증거는 비공개에만 보존한다.
4. 실제 Windows EXE의 headless 자동 입력으로 캐릭터 생성·이동·NPC 대화·맵 전환·몬스터 전투·실제 무작위 드롭과 획득·저장을 검사한다. 별도 프로세스 재실행으로 player/world/loot 저장 복구를 비교한다.
5. 시작 60초, 전체 시험 240초, 관찰한 프로세스 RSS 2GiB 상한을 적용하고 엔진/스크립트 오류·충돌·미실행 보고를 차단한다.
6. 같은 소스 커밋의 모든 네이티브 검사가 통과해야 ZIP을 생성하고 CRC·SHA256을 검사한다.
7. 비공개 Release에 새 버전 ZIP과 검증 로그/프레임 묶음을 게시한다. 실패하면 플레이어 배포를 차단하고 비공개 draft 진단 Release에 원인 로그를 남긴다. 이전 정상 버전은 교체하지 않는다.

일반 창 렌더링 검사는 실제 사용자 Windows 11의 더블클릭·화면 조작·음향·장시간 플레이 보증이 아니다. 자동 입력은 게임 입력 핸들러를 거치며 사람의 실제 GUI 조작 결과로 표시하지 않는다. 해당 항목은 별도 BLOCKED/미검증이다. 각 버전의 실제 실행 결과는 Actions 실행 및 비공개 Release 검증 자료가 기준이다.

## 비공개 유지와 비용

공개 소스의 표준 `windows-latest` 러너를 사용하고 비공개 저장소에서 Windows 러너를 별도 예약하지 않는다. 추가 유료 서비스는 설정하지 않았다. 공개 Actions artifact에는 직접 생성한 시험용 fixture 진단만 저장한다. 원본·게임 ZIP·실제 게임 화면은 공개 저장소나 공개 artifact에 올리지 않는다.

원본 자산이나 비공개 콘텐츠 자체를 변경할 때는 개발 작업의 일부로 비공개 공급과 해시 명세도 같은 버전으로 갱신해야 한다. 소스만 수정할 때는 기존 private 입력을 자동 재사용한다. 인증이 취소되거나 공급이 손상되면 자동 실패로 남기며 검사를 건너뛰어 배포하지 않는다.
