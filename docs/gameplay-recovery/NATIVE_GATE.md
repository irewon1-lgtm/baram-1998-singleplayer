# 현재 네이티브 실행 및 배포 관문

**Windows·Android 실제 OS 핵심 경로, 동일 player 다중 터치, 엄격한 통합 배포 관문은 PASS다. 검증된 설치본은 전달 준비됐다.** 게임 전체·모든 콘텐츠·전체 성능 완료로 표시하지 않는다. 성능 FAIL·전수 수동 플레이 NOT_RUN은 남아 있다.

최신 실행은 소스 `243448ac`의 [CI 38729864952](https://github.com/irewon1-lgtm/baram-1998-singleplayer/actions/runs/38729864952)다.

| 항목 | 판정 | 실제 확인 범위 / 실행 상태 |
|---|---|---|
| Windows 창·렌더·메시지 응답 | PASS | 실제 Windows 창 검사19개·창 관측133회, headless 시작3개 |
| Windows 신규 평민1→전직→레벨6 공격기술→저장 | PASS | 정상 입력·정상 시간의 코어51개, 실제 화염주 피해44. 코어577.050초 |
| Windows 새 프로세스 복원 | PASS | 캐릭터·몬스터·드롭·RNG4개 |
| Windows 설치본 정체 | PASS | 실제 ZIP 해시, 동결 소스 입력, 활성 콘텐츠, manifest1,833개 멤버 검증3,695개 |
| Android player 실제 OS 입력·사냥·지도·업데이트 저장 | PASS | 실제 OS25개·606.05초 세션·replace 설치 저장 바이트 보존 |
| Android 별도 verification 육성·공격기술·재실행 | PASS | 실행 관문14·정상 입력 코어53·새 프로세스4개. player와 같은 생산 소스·콘텐츠·runtime.pck이며 별도 앱 경로로 구분 |
| 동일 Android player의 실제 OS 다중 터치 | PASS | 실제 OS 두 포인터11개·player와 동일 APK 해시 |
| 최종 Android·Windows 통합 배포 관문 | PASS | 실제 세 CI 작업 성공·필수 증거·파일·소스·콘텐츠·패키지·서명·저장 관문3,740/3,740. 설치본 READY |
| 지도·콘텐츠 전수 정적/통제 검사 | PASS | 423맵 연결·접근, Work001~010 활성 정체, 기술·NPC·드롭·퀘스트·제작 참조. 전체 수동 완주와 구분 |
| 새 Linux 처음부터 코어·재실행 | PASS | 45/45 +4/4. 실제 Windows 결과와 별도 증거 |
| 비영사천문 목적지 탐색 | PASS | 실제 Windows26µs, 후보1·전체 엔티티 방문0·경로 탐색0 |
| 남은 첫 그리기·동기 저장 성능 | FAIL | Linux 첫 Work그리기339.957ms, Windows 저장 최대898.379ms, Android player 저장54회 중앙886.738ms·최대5,082.194ms |
| Android 에뮬레이터 `_process` 간격 | FAIL | 4,457개 평균94.655ms/p99 199.058ms. 생명주기·저장·계측 포함, GPU FPS·Galaxy 성능과 구분 |
| GPU 표시 FPS·Windows 지속 FPS·첫 조작 가능 프레임 | NOT_RUN | 측정된 Android 처리 간격·탐색·시작 비용으로 추정하지 않음 |
| 사용자 기기·전 맵·전 기술·전 퀘스트·네 직업1~99 완주 | NOT_RUN | 대표 경로·참조 검사를 전체 플레이 완료로 세지 않음 |

Windows 활성 `aa212082…`와 보존 `cd0c680a…`는 전체 의미 해시가 같다. 유일한 차이는 import7곳의 소비자 커밋 기록이다. Work 각 패키지의 제작·가져오기·활성 PASS와 패키지 전체 플레이 NOT_RUN은 [통합 감사](FINAL_AUDIT_20261015.md)에 개별 기록한다. 원본 미확보 자산9개, 적4모델의 원본 공격 모션 부재, 목록 아이템2개·미사용 제작 상점2개의 미연결은 남아 있다.

## 이전 차단과 실패 기록

이전 run `38724985965`는 환경의 브랜치 허용 규칙 때문에 runner/실행단계0에서 BLOCKED였다. 사용자가 정확한 복구 브랜치 추가를 승인했고, 기존 두 허용 브랜치와 다른 보호 규칙·비밀값을 유지한 채 승인된 한 브랜치만 추가했다. 해당 차단은 해결됐으며 승인 재요청 사항이 아니다.

변경 전 기록은 [이전 관문 문서](NATIVE_GATE_BEFORE_APPROVAL_38724985965.md)와 [이전 상태 JSON](NATIVE_EXECUTION_STATUS_BEFORE_APPROVAL_38724985965.json)에 원문 바이트 그대로 보존했다. 거기에 있는 승인 필요·BLOCKED·NOT_RUN은 당시 상태다. 첫 연속 플레이39 PASS/3 FAIL도 보존했고, 이후 재개5검사 및 새 전체45검사 PASS로 덮어 지우지 않았다.

현재 정본: [상태 JSON](NATIVE_EXECUTION_STATUS.json), [통합 감사](FINAL_AUDIT_20261015.md), [성능 증거](PERFORMANCE_CURRENT_LINUX_20261015.md). 설치 성공·CI 작업 성공만으로 게임 정상 플레이 또는 게임 전체 완료를 판정하지 않는다.

전달 준비 파일은 `baram-Android-243448ac.apk`(283,652,192바이트, SHA256 `236a668a5e651f84e7ee22bb3cdecf6a0b4631531ac829f5a65920c79e3b120b`)와 `baram-Windows64-243448ac.zip`(175,904,711바이트, SHA256 `58b6cb400d17063c4771d2756a0f51dde16be87db9205db1de1f16005311e042`)이다. 실제 최종 폴더의 바이트·해시를 다시 읽어 확인했다. 전체 개선 완료 여부는 계속 false다.
