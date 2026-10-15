# 네이티브 CI 후속 도구

소실된 두 후속 Python 도구의 원문은 회수하지 못해 재구성했다. 게임 소스, 서명 파일, 원본 런타임을 수정하지 않는다.

최신 `243448ac`의 CI run `38729864952`는 Windows·Android·다중 터치 세 작업이 모두 성공했다. 실제 복호화 보고서와 설치본 바이트를 대조한 엄격한 기능 배포 관문은 **3,740/3,740 PASS**, 검증 설치본은 **READY**다. 이 판정은 게임 전체·전수 수동 플레이·성능 완료가 아니다. 성능 FAIL과 Galaxy·사람의 Windows 화면 직접 관찰·계정 동기화 NOT_RUN은 [현재 관문](NATIVE_GATE.md)과 [통합 감사](FINAL_AUDIT_20261015.md)에 남긴다.

이전 run `38724985965`의 보호 규칙 차단은 [승인 전 기록](NATIVE_GATE_BEFORE_APPROVAL_38724985965.md)이다. 사용자가 승인한 정확한 브랜치 추가 후 해결되었으며, 현재 승격 차단이나 게임 실행 실패로 표시하지 않는다.

## 실행 준비

```sh
python -m pip install cryptography
python -m unittest -v test_post_ci_tools.py
```

현재 합성·정책 시험 10건을 새로 실행해 통과했다. 실제 네이티브 게임 또는 실제 GitHub artifact 전송 완료 판정은 아니다. 시험은 AES-GCM 형식 호환과 태그 변조 차단, HTTP Range 이어받기, ZIP 경로·링크·중복·용량 차단, 인증된 원자적 추출, 원본 출력 보호, 누락된 공격기술/NOT_RUN/잘못된 OS 거부, 네이티브 CI 미실행 시 BLOCKED를 확인한다.

## 1. GitHub artifact 가져오기

연결된 GitHub `download_workflow_artifact` 도구의 임시 다운로드 URL을 로컬 파일에 저장한다. URL은 출력하거나 채팅에 붙이지 않는다. 아래의 `--url-file`은 HTTPS URL 한 줄 또는 `download_url` 한 개를 가진 JSON 파일이다. 키 파일은 경로로만 넘기며 그 내용을 출력하지 않는다.

```sh
python fetch_recovery_artifact.py \
  --url-file /absolute/private/windows-artifact-url.txt \
  --sealed-name windows-quality.sealed \
  --signing /absolute/private/android-signing.json \
  --output /absolute/fresh/windows-native-artifact \
  --report /absolute/reports/windows-transport.json
```

Android는 `android-quality.sealed`를 지정하고 새 출력 폴더를 쓴다. GitHub가 artifact ZIP의 SHA256을 제공하면 `--expected-sha256`으로 대조한다. 실패 예외에는 URL이나 서명 정보를 쓰지 않는다. TLS, 다운로드·압축 해제 크기, 경로, CRC, AES 인증을 검사한다. 인증과 ZIP 검사 모두 성공한 뒤에만 지정한 새 출력 폴더로 원자적으로 옮긴다. 전송 PASS는 플랫폼 검증 PASS가 아니다.

## 2. 네이티브 설치본 승격

`ci-run.json`은 GitHub API에서 확인한 실제 `head_sha`, `conclusion`, `jobs`를 포함해야 한다. `jobs`에는 `android`·`windows`의 이름, 결론과 Windows runner의 실제 labels를 남긴다. 실행하지 않은 항목을 채워 넣지 않는다.

```sh
python package_recovery_delivery.py \
  --android-dir /absolute/android-native-artifact \
  --windows-dir /absolute/windows-native-artifact \
  --ci-run /absolute/reports/ci-run.json \
  --source-sha FULL_40_CHARACTER_FROZEN_COMMIT \
  --signing /absolute/private/android-signing.json \
  --output /absolute/fresh/verified-delivery \
  --report /absolute/reports/delivery-gate.json
```

선택적으로 `--expected-content`로 기대한 64자리 콘텐츠 릴리스를 고정한다. 아래가 모두 있어야 한다.

- Windows: 실제 네이티브 실행 PASS, windowed 화면 렌더·message pump PASS, 정상 타이머의 레벨 1 평민→사냥→전직→레벨 6 공격기술 사용→저장→새 프로세스 복구의 필수 검사 전부 PASS, 실제 x64 EXE와 ZIP manifest 파일·해시 일치.
- Android player: 원래 패키지명, 원래 f248 인증서 지문, 기존 `1792054707`보다 큰 versionCode, APK의 실제 바이트 해시와 포함 runtime.pck 해시, 동일 APK의 실제 Android 35 OS 입력·사냥·드롭·지도·10분·업데이트 설치 저장 보존 PASS.
- 별도 Android verification: `android-verification-build.json`·`android-verification-signature.log`가 존재하고 동일 인증서·원래 동결 소스 입력·export 입력·runtime.pck·콘텐츠를 대조한다. recovery-core/restart 보고서의 실제 Android OS, 정상 타이머, 필수 레벨 6 공격기술, 저장 복구 검사가 모두 PASS여야 한다. verification APK 자체는 배송 파일에 포함하지 않는다.
- 플랫폼 간 소비자 코드 커밋과 콘텐츠 릴리스가 동일하고 모든 세부 검사 상태가 PASS여야 한다. 누락되면 BLOCKED 또는 FAIL로 끝나고 설치본 파일을 새로 배포하지 않는다.

서명 검증은 CI의 실제 apksigner 결과를 AES 인증된 artifact와 실제 player APK 해시에 연결한 attestation으로 기록한다. 이 도구가 별도로 Android SDK에서 apksigner를 실행했다고 주장하지 않는다. Galaxy 실기기, 사람의 Windows 화면 직접 관찰, 계정 동기화 및 전체 콘텐츠 완료는 추가 검증되지 않았다.
