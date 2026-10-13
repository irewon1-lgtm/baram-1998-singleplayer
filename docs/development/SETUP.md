# 개발 도구 실행 안내

작업 디렉터리는 `/workspace/baram-1998-singleplayer`, 개인 분석 폴더는
`/workspace/baram-private`다. 이 cloud 작업은 이미 격리되어 있으므로 기존
체크아웃을 사용하고 새 worktree를 만들지 않는다. 현재 브랜치·작업물을 먼저
확인하고 `docs/development/CHECKPOINT.json`의 중단 지점에서 이어간다.

도구 설치는 아래 명령으로 실제 실행했다. `.NET8.0.425` SDK는 공식 SHA512,
Xvfb는 서명된 Debian 인덱스와 SHA256을 검증한다. 원본 에셋은 설치하지 않는다.

```bash
cd /workspace/baram-1998-singleplayer
python3 tools/setup_restoration_environment.py --private-dir /workspace/baram-private
```

Godot의 home 접근 오류를 피하려면 실제 실행했던 XDG 경로를 사용한다.

```bash
export XDG_DATA_HOME=/workspace/baram-private/setup/data
export XDG_CONFIG_HOME=/workspace/baram-private/setup/config
export XDG_CACHE_HOME=/workspace/baram-private/setup/cache
export DOTNET_ROOT=/workspace/baram-private/setup/dotnet
export DOTNET_CLI_HOME=/workspace/baram-private/setup/dotnet-home
export NUGET_PACKAGES=/workspace/baram-private/setup/nuget
export DOTNET_CLI_TELEMETRY_OPTOUT=1
```

확인된 fixture 시험은 코드/입력/환경이 바뀔 때만 영향 범위를 재실행한다.

```bash
python3 -m unittest discover -s tests -p 'test_legacy_assets.py' -v
```

실제 화면 smoke는 X11 가상 화면과 Godot를 시작하고 자신이 시작한 프로세스만
종료한다. Pillow는 현재 환경에 있다. 새 실행 폴더를 사용해 기존 증거를 보존한다.

```bash
python3 tests/smoke_asset_viewer.py \
  --private-dir /workspace/baram-private/viewer-run-4 \
  --xvfb /workspace/baram-private/setup/x11/usr/bin/Xvfb \
  --report /workspace/baram-private/viewer-run-4-result.json
```

이는 예시 재실행 위치다. 이미 있는 실행 폴더를 덮어쓰지 말고 다음 번호/새
폴더를 사용한다. fixture의 색 픽셀을 원작 캐릭터로 설명하지 않는다.

**다음 필요한 실제 작업**은 허용 목록 저장·Publish 이후 아래 원본 복구다.

```bash
python3 tools/recover_runtime_inputs.py \
  --private-dir /workspace/baram-private \
  --only archives \
  --report /workspace/baram-private/asset-recovery-resume.json
```

원본을 추출한 뒤의 CLI 형식은 다음과 같다. 값이 실제 원장·추출물에서
확인되기 전에는 아래 자리를 임의의 값으로 채우거나 실행 PASS로 기록하지 않는다.

```text
python3 tools/render_legacy_assets.py
  --container <원장과 해시 대조한 DAT>
  --container-sha256 <DAT SHA256>
  --epf <확인한 EPF 엔트리>
  --palette <PAL 엔트리 또는 개인 폴더의 PAL>
  --palette-sha256 <PAL 페이로드 SHA256>
  --palette-index <확인한 팔레트 번호>
  --frames <확인할 실제 0-based 프레임 범위>
  --version <KR-4.91 또는 NA-4.03/NA-4.66/NA-4.95>
  --out <새 개인 이미지 폴더>
  --report <메타데이터 JSON>
```

Godot 실제 뷰어는 `--report=<해독 결과>`를 받는다. `--capture`를 쓸 때는 실제
X display가 필요하며 headless 모드는 화면 시험으로 인정하지 않는다.

```text
godot --path tools/asset_viewer --display-driver x11 --rendering-method gl_compatibility
  -- --report=<개인 해독 결과 JSON>
  --capture=<새 개인 캡처 PNG 경로>
  --screen-report=<메타데이터 JSON>
  --exercise --exit
```

Project1998 비교 준비 출력은 저장소 밖에 있다. 기존 실행의 소스·SDK·조건을
확인하여 재사용하고, 소스/빌드가 바뀌면 필요한 범위만 다시 실행한다.

```bash
cd /workspace/baram-private/repos/project1998/Project1998
/workspace/baram-private/setup/dotnet/dotnet build Project1998.Server.slnf -m:2 --nologo
```

외부 전체 시험은 2033 PASS/1 FAIL이다. `README.md`의 진단과 TRX 해시를 참고하고,
조건 변경 없이 전체 시험을 되풀이하지 않는다. 한국 게임 시험37개와 별개다.

로컬 프로토콜 검사가 새로 필요할 때만 실행한다. 실제 그래픽 클라이언트나
한국 초보 게임이 작동한다는 증거로 사용하지 않는다.

```bash
cd /workspace/baram-1998-singleplayer
python3 tools/run_local_server_probe.py \
  --source /workspace/baram-private/repos/project1998/Project1998 \
  --dotnet /workspace/baram-private/setup/dotnet/dotnet \
  --state /workspace/baram-private/probe-state \
  --logs /workspace/baram-private/probe-logs-next \
  --ready-timeout-seconds 45
```

동작 프로세스는 snapshot에 유지되지 않는다. 상시 서비스를 요구하는 게임
방식은 아직 결정하지 않았으며 현재 명령은 임시 검사 프로세스만 실행한다.
