# Codex 개발 재개 지점

개발 기준: `2775b1166a760b6a1757f09f2faf1e799d3fd59e`.
브랜치: `dev/restoration-runtime-20261014`. 날짜는 Asia/Seoul 기준이고 로그는 UTC다.
최상위 기준은 `../RESTORATION_WORKFLOW_LOCK.md`, 원래 인수인계는
`../../research/restoration-integrated-20261013/CODEX_HANDOFF.md`다.

**현재 4단계에서 원본 다운로드 접근을 기다리는 상태다.** 해독기와 프레임
검사 뷰어를 실제 실행했지만 원본 이미지 해독·개체 식별·동작 연결은 0건이다.
5단계 방식 결정과 6~9단계 게임 구현을 완료했다고 처리하지 않는다.

## 구현과 실제 실행

- `tools/legacy_assets.py`: DAT 디렉터리 경계 검사, EPF 원시 픽셀/행별 투명
  스텐실, 음수 기준점, DLPalette 단일/다중 팔레트, 768-byte RGB PAL, PNG 출력.
- `tools/render_legacy_assets.py`: 컨테이너와 PAL 해시 확인, 명시적 프레임·팔레트
  선택, 원본 버전 분리, 이미지의 저장소 외부 저장, 메타데이터 출력.
  팔레트 자동 대체와 개체·동작 추측을 하지 않는다. 애니메이션 범위는 기록만
  하고 PAL 색 순환 재생은 아직 구현하지 않았다.
- `tools/asset_viewer/`: Godot 4.6.3에서 해독 PNG의 RGBA 해시를 다시 비교하고
  기준점으로 표시한다. 좌우 키/버튼은 선택 프레임을 바꾼다. 검사 뷰어이며
  게임·캐릭터·원작 애니메이션 구현이 아니다.
- `tools/recover_runtime_inputs.py`: 기존 원장에서 5개 우선 원본과 3개 고정
  외부 참조만 복구한다. Work 조사 원장을 덮어쓰지 않고 불일치 파일을 보존한다.
- `tools/setup_restoration_environment.py`: 개인 폴더에 체크섬 검증된 .NET 8.0.425,
  서명된 Debian 인덱스와 패키지 해시로 검증된 Xvfb를 준비한다. 관리자 권한이
  필요 없다. Godot은 환경에 있던 4.6.3을 사용한다.
- 기존 `tools/run_local_server_probe.py`에 선택적 시작 대기 시간을 추가했다.
  기본 8초는 유지하고 이번 실행은 45초를 사용한다. 실제 프로토콜 로그인·생성·
  월드 진입 성공 조건을 유지한다. 외부 서버 코드는 수정하지 않았다.

| 단계/시험 | 조건·버전 | 실행/재사용 | 결과 | 증거 |
|---|---|---|---|---|
| 해독기 회귀 12개 | 독자 작성 fixture | 실제 실행; 핵심 파서 변경 없음. 출력 링크 보호 변경 후 해당 CLI 시험 1개만 재실행 | PASS, fixture 범위 | `runs/20261014/decoder-tests.log`, `exporter-guard-tests.log` |
| Godot 실제 화면 | OWN_FIXTURE, Godot4.6.3, X11/llvmpipe | 실제 실행, viewport 12픽셀·좌/우 입력 | PASS, 뷰어 범위 | `viewer-smoke-3.json`; 화면은 개인 폴더 |
| 원본 확보 | KR4.91, NA4.03/4.66/4.95, 보조 PAL | 실제 URL 요청 | BLOCKED, 5/5 proxy403 | `initial-input-recovery.json` |
| 외부 참조 확보 | EPFViewer2bc585b, TKMapper13c6dc3, P1998 3690542 | 실제 고정 커밋·fsck 검사 | PASS, 소스 확보만 | `reference-recovery.json` |
| Project1998 빌드 | 3690542, .NET8.0.425, Server.slnf | 실제 실행 | PASS, 경고/오류0 | `project1998-build.log` |
| 외부 서버 시험 | 같은 소스·SDK, SQLite 임시 상태 | 실제 실행 | **FAIL: 2033 PASS / 1 FAIL / 0 SKIP** | `project1998-tests.json`, `project1998-tests.log` |
| 로컬 프로토콜 생성/진입 | localhost3100/3105, 실제 LoginProbe | 실제 실행 | PASS, headless 프로토콜만 | `server-probe-pass.json` |
| 종료/재시작·기존 캐릭터 진입 | 같은 개인 상태 DB, 새 서버 프로세스 | 실제 실행 | PASS, headless 프로토콜만 | `server-probe-restart.json` |
| 원작 그림/방향/동작/공격 음향 | 실제 원본 미확보 | 미실행 | BLOCKED | `CHECKPOINT.json` |
| 5단계 방식 결정·한국판 호환 | 실제 NA4.95/KR4.91 화면 없음 | 미실행 | NOT_RUN | 선행 4단계 대기 |
| 6단계 실제 초보 게임 화면 | 개발 방식 미결정 | 미실행 | NOT_RUN | 기능 30개 기존 상태 유지 |
| 7단계 한국 프로필 계산 시험37개 | BALANCE_TESTS.json | 미실행 | NOT_RUN | 외부 서버 시험2034개와 별개 |
| 8~9단계 확대·원작 대조·완주 | 선행 단계 미완료 | 미실행 | NOT_RUN | 기존 순서 유지 |

위 표의 축약 증거 경로는 `runs/20261014/` 아래에 있다. 원본 캡처·바이너리·
이미지는 `/workspace/baram-private/`에만 두었다. MIT 형식 참고 고지는
`THIRD_PARTY_NOTICES.md`에 있다. main과 조사 브랜치, 기존 조사·수치 입력은
변경하지 않았다. 당시 한국 확인 필드600/4216, 제작 입력4216/4216은 그대로이며
이번 작업에서 원작 확인률이나 게임 완성률이 증가했다고 주장하지 않는다.

## 실패 원인과 보존

- 네트워크: 지정된 Archive.org/Wayback URL에서 연결 터널 proxy403을 받았다.
  같은 요청을 계속 반복하지 않았다. 허용 호스트 설정을 초안에 저장했으며
  환경 설정 저장·Publish 이후 영향을 받는 다운로드만 재시험한다.
- 뷰어 첫 시험: 45초 시간 초과. Xvfb의 socket 디렉터리 생성 경고가 있었다.
  비관리자 환경에서 디렉터리를 미리 준비하고 타임아웃에도 로그를 보존하도록
  수정한 뒤 실제 화면 시험을 통과했다. 최초 stdout을 보존하지 못했으므로
  그 첫 실패의 단일 근본 원인은 확정하지 않는다. `viewer-smoke-1.json` 보존.
- Godot 최초 import: 읽기 전용 home 때문에 XDG 데이터/설정 저장 오류.
  XDG 디렉터리를 개인 폴더로 지정하여 `godot-import-fixed.log`에서 해소했다.
- 서버 최초 시작: 8초 안에 게임 포트가 준비되지 않았다. 종료 당시 로그는
  서버 초기화 중이었다. 프로토콜 조건은 유지하고 45초 시작 대기로 재시험하여
  성공했다. `server-probe-fail.json` 보존.
- 외부 서버 시험 실패: `StatusFileTests.TheMemoryFieldsRenderInTheRelationsTheRuntimeGuarantees`.
  실제 `gcHighLoadMb=29491`, `gcAvailableMb=24576`; 시험은 전자가 후자 이하여야
  한다고 가정한다. `Server/StatusFile.cs`는 두 값을 각각
  `GC.GetGCMemoryInfo().HighMemoryLoadThresholdBytes`와 `TotalAvailableMemoryBytes`에서
  읽는다. 현재 컨테이너의 32GiB 제한·.NET8.0.425에서 이 가정이 성립하지 않는다.
  외부 코드 결함/런타임 메모리 가정 문제로 분리하여 FAIL을 보존한다. 그 시험을
  제외하거나 GC 설정/기대값을 바꿔 PASS로 만들지 않았다. 게임 계산 실패라고
  확대하지도 않는다. 필수 원본 클라이언트 호환 검증을 대신할 수 없다.
- 재사용 설치 스크립트 첫 실행: APT가 이미 받은 패키지의 `--print-uris` 항목을
  생략해 3개 기대 조건을 충족하지 못했다. 별도 빈 폴더에서 서명된 인덱스의
  다운로드 계획을 읽고 실제 캐시를 SHA256으로 검사하도록 수정했다.
  `setup-first-fail.log`와 수정 후 `setup-fixed.log`, `setup-report.json`을 보존한다.

## 다음 실행 — 여기서 이어갈 것

1. 환경 설정의 네트워크 추가 호스트 초안을 저장하고 Publish한다. 필요한
   호스트: `archive.org`, `web.archive.org`, `ia600905.us.archive.org`,
   `ia601903.us.archive.org`, `ia601602.us.archive.org`, `ia600702.us.archive.org`.
   새 리다이렉트가 실제로 차단될 때만 원장에 오류를 기록하고 추가한다.
2. `tools/recover_runtime_inputs.py --only archives`를 실행한다. 기존 PASS 참조
   소스와 연구 데이터 검사는 다시 실행하지 않는다. 다음 실행의 정확한 명령은
   `SETUP.md`에 있다. 해시 불일치가 있으면 사용하지 않는다.
3. 검증된 KR4.91/NA4.03 설치 아카이브를 격리된 개인 폴더에서 정적 추출한다.
   기존 `ASSET_CATALOG.jsonl`, `ASSET_CONTAINER_INDEX.json`, world-audit의 DAT
   해시와 비교한 뒤 명시적 EPF/PAL/프레임을 새 해독기로 PNG 출력한다.
   NA4.66/4.95 완전 페이로드 추출은 여전히 미완료이며 설치 EXE를 검증 없이
   실행하지 않는다.
4. 원작 PNG의 실제 Godot 표시와 프레임·방향·팔레트를 기록하고 한국 당시
   화면과 대조한다. 우선 대상: 캐릭터4방향과 걷기/공격/피격/사망, 토끼/다람쥐,
   목도/목검 아이콘·착용, 기술 효과·공격 음향. 북미 복원 외형 ID를 한국 원작
   ID로 확정하지 않는다. 뷰어 성공을 개체·동작 연결 성공으로 옮기지 않는다.
5. 그 결과로 5단계의 NA4.95+Project1998 실제 클라이언트 화면과 Godot 독립
   실행을 비교하고 한 방식을 결정한다. 현재 headless 로그인·외부 시험 PASS는
   준비 증거로만 쓰고 원본 호환 PASS로 재사용하지 않는다. 이후 6→7→8→9 진행.

추가 과금·운영 배포·main 병합은 실행하지 않았다. 공개 저장소에 원본이나
무라이선스 외부 코드를 넣지 않았다. 전체 게임 완료 기준은 충족하지 않았고,
4단계 원본 접근이 종속 작업의 재개 조건이다.
