# Work P2 GEN003 코드+비공개 입력 복원

기본 담당은 Work다. 먼저 STATE_WORK_P2.json·RESULTS.md·실제 원격HEAD를 확인한다. 같은 해시의 P1.5 조사·전수 해독·동일 합성시험을 반복하지 않는다.

## 고정 코드와 입력

원본 실행 앱 소스 체크포인트: `b55c7ed0061301820d15a780f08ddb1d8a4e8832`.
최종 결과 커밋이 이보다 앞서면 보존하고 이어간다. 과거로 reset하지 않는다.

입력 세대: WORK-P2-GEN003.
ZIP SHA256: `e3468bd90333967e28cdadc35604098a7d2bf8403b73a4ef8435a119bf96e5b9`.
길이: 7,847,930 bytes.
내부 runtime.json SHA256: `ddf88ca05f63ab67c73f12f474005310eed39b31996f8d6c70b9015703922973`.

지속 private Git 경로:
`irewon1-lgtm/baram-windows-private` / `work/rebuild-p2-inputs-gen003-20261016` /
commit `eee75026c9ac50bb10c9c78dab986170d279ab38` /
`p2-work/WORK-P2-GEN003/runtime.zip`.
기존 main·입력 GEN002는 보존했다. 현재 GitHub connector의 binary blob 읽기는 UTF8 decode 오류로 차단되었으므로, 같은 계정의 비공개 파일 `BARAM_P2_PRIVATE_INPUT_GEN003.zip`은 `libfile_d19402f30ab881918f3d82665e5fbd86` version0이다. 실제 재수신·SHA 대조·깨끗한 코드47검사 재현을 완료했다. PRIVATE_DELIVERY.json의 영수증을 사용한다. 공개 파일 목록을 원본으로 대체하지 않는다. Git 인증 토큰·임시URL을 보고서나 명령에 넣지 않는다.

## 새 디렉터리에서 복원

1. Work 브랜치를 새 별도 경로에 clone한다. 다른 작업자의 checkout/reset/clean은 하지 않는다.
2. 위 비공개 입력 파일을 정확한 저장ID로 새 private 경로에 가져온다. ZIP 길이·SHA를 대조한다.
3. 새 출력 디렉터리로 다음 도구를 실행한다. 이미 있는 세대를 덮어쓰지 않는다.

```bash
python3 tools/rebuild/p2/restore_work_runtime.py \
  --zip /private/input/BARAM_P2_PRIVATE_INPUT_GEN003.zip \
  --sha256 e3468bd90333967e28cdadc35604098a7d2bf8403b73a4ef8435a119bf96e5b9 \
  --destination /private/new-run/WORK-P2-GEN003
```

4. Godot4.6.3 `7d41c59c4`에서 동일 검수 프로젝트를 실행한다.

```bash
BARAM_P2_RUNTIME=/private/new-run/WORK-P2-GEN003 \
BARAM_P2_REPORT=/private/new-run/original-smoke.json \
Godot_v4.6.3-stable_linux.x86_64 --path rebuild/p2 -- --p2-original-smoke
```

외부 asset hash·참조·형식 오류는 차단한다. headless 실행은 화면 캡처가 아니다. GUI/오디오 서버가 필요한 환경에서는 tools/rebuild/p2/work_platform.py의 linux-run을 사용한다. 시스템 한글폰트를 설치·참조하며 폰트파일을 앱에 넣지 않는다. 동일 project·runtime을 Windows/Android로 export할 때는 같은 도구의 export를 쓴다. 역사적 Codex export_presets의 임시경로를 그대로 실행하지 말고 wrapper가 만든 새 private project 사본에서 고정템플릿 경로·새 시험서명을 지정한다.

## 원본 재변환이 필요한 경우만

INPUT_MANIFEST.json의 Library IDs와 길이·SHA를 사용한다. 한국1.25는 LIB-009, 한국4.91은 LIB-010이며 자기 DAT·팔레트를 사용한다. LIB-018 아틀라스는 판본 미확정으로 이번 한국1.25에 미사용이다. parser는 고정 core+참고3분할의 legacy_parser_tools에서 SHA 대조 후 가져온다. 원본 파일명·목록만으로 확보를 선언하지 않는다. mapper의64격자는 저장 블록이며 서버 활성범위는 미확정이다.

새 원본·변환코드·팔레트·설정·프로필·스키마가 달라지면 새 입력 세대를 만든다. DLGNEW02 정정은 correct_kr491_ui_palette.py와 UI_PALETTE_DIAGNOSIS에 있다. GEN002의 잘못된 결과·마스크3건·NA154·Wine12 실패는 지우지 않는다.

## 외부 환경이 필요한 남은 시험

네이티브 Windows는 기존 `baram-windows-private` 시험 환경의 branch 보호 규칙이 Work 브랜치를 허용한 뒤에만 실행한다. 이번 요청에서는 규칙을 변경하거나 다른 허용 브랜치에 우회 push하지 않았다. 재개 시 새 native 요청에는 GEN003의 정확한 path/SHA를 사용한다. 기존 NATIVE_REQUEST.json은 당시 실제 거부된 GEN002 요청의 역사다.

Galaxy·실제 IME·하드웨어 실청취·실계정 HTTPS 왕복은 별도이며, 에뮬레이터/문자열 직접주입/믹서신호/저장 checksum과 구분한다. P3/P4·운영 배포·main병합·유료 자원은 이번 재개 명령만으로 허용되지 않는다.
