# 콘텐츠 준비 Python 복구 근거

`tools/prepare_recovery_content.py`의 소실된 원본 Python 파일 자체는 회수하지 못했다. 이 파일과 가져오기 어댑터는 남아 있는 대화의 작성·수정 기록, `b18e67f`의 기존 `PackageStore` 구현, 고정 Work 패키지로 재구성했다. 이전 회차의 PASS를 이번 실행 결과로 옮기지 않는다.

고정 입력은 Work 커밋 `c919cf1bdffe0e318d4058dc3fc17be4a2844203`, 기존 릴리스 `9e30ec651489a4f5bdbf5c4e727a41a3c7a2b2825a373262056c1e896a82fb7c`, 보존된 후보 릴리스 `cd0c680ab5fc8fb223ef2d14ff0b991b18e3e100fecba693bd608040f8a66e57`이다. 공개 Work 변환 도구의 코드 바이트는 검증하지만 실행하지 않는다.

복구 범위는 기존 입력·가드의 유지, 이미 검증된 활성 번들 멤버 재사용, 그리고 CONTENT008/010의 공개된 정확한 NPC 필드 쌍 병합이다. NPC 병합은 두 패키지의 커밋·manifest 해시, 원래 제안, services/dialogue 전체 상태를 모두 대조한다. 일반 필드 가드와 Codex 소유 필드 보호는 계속 실행한다. 관련 없는 NPC 필드는 바꾸지 않는다. Windows에서 지원하지 않는 `os.O_DIRECTORY`를 사용하지 않도록 파일 flush/replace 뒤 디렉터리 fsync만 POSIX에서 실행한다.

재구성한 준비 과정은 별도 임시 디렉터리에서 가져오고 최종 출력에는 원본 파일과 최종 릴리스만 복사한다. 원본 캐시는 증거 폴더로 보존하고 새 캐시 생성을 요구한다. 최종 manifest의 실제 파일 목록·크기·해시를 다시 검증한다. ASSETS001의 기존 983개 적용/9개 보류는 그대로 명시하며, CONTENT001~010과 ASSETS003은 전부 적용되어야 데이터 준비 PASS가 된다.

이번 실행에서 새로 확인한 결과:

| 검사 | 결과 | 범위 |
|---|---|---|
| 기존 가져오기 회귀 시험 | PASS — 31건 | 현재 수정된 Python을 직접 실행 |
| 재구성 helper 안전 시험 | PASS — 6건 | 경로·기존 출력 보호, 해시, 제한된 의미 비교, 기존 멤버 재사용, NPC 병합 가드, Windows 분기 |
| 보존 후보 읽기 전용 검증 | PASS | cd0c 후보 전체 입력 1,835개 불변, 13개 패키지 고정 파일·스키마·원장 재검증 |
| 첫 재가져오기 의미 비교 | PASS | 소비자 코드 커밋 필드만 제외하고 보존 cd0c 릴리스와 전체 데이터 동일 |
| 첫 재가져오기 외부 manifest 검사 | FAIL | 같은 프로세스에서 삭제한 중간 릴리스가 다음 실행에서 관측됨. 원인은 확정하지 못함 |
| 수정 후 최종 재가져오기 | PASS | 초기 9e30에서 CONTENT005~010·ASSETS003 실제 적용, NPC 정확한 병합 2건 |
| 수정 후 별도 실행의 manifest 검사 | PASS | 최종 출력 2,710개 파일의 실제 목록·크기·해시 일치, 중간 6개 릴리스는 최종 출력에 생성하지 않음 |
| 보존 cd0 후보와 최종 재생성 데이터 비교 | PASS | 의미 해시 `6842599b0180934b1d51a0e840f70daf07354a30cf917ac3b3345fed24491825` 일치; 소비자 코드 커밋 필드만 제외 |
| 실제 Windows OS 실행 | NOT_RUN | Windows 분기 단위 시험과 구분 |
| 게임 플레이·Android·성능 | NOT_RUN | 다른 검증 및 설치본 시험에서 별도 판정 |

첫 회귀 시험에서는 `jsonschema` 미설치 때문에 1건이 실패했다. 무료 `jsonschema==4.25.1` 설치 후 위 31건을 다시 실행해 통과했다. CI에도 이 의존성이 필요하다. 원본에 공격 시퀀스가 없는 모델의 기존 제한과 4개 적의 걷기 프레임 대체 표시는 별도 게임 검증 대상이며, 콘텐츠 준비 PASS가 원본 공격 픽셀의 존재를 뜻하지 않는다.

이번 최종 재생성 릴리스는 `406043bbf934fddb0a6ff71338348e879bdb9da154546c5a90c99993eb95a098`이다. 소비자 커밋은 실행 당시 저장소 HEAD `b18e67f`였으며 새 커밋으로 CI를 실행하면 이 메타데이터와 전체 릴리스 해시는 달라진다. 소스 런타임 1,835개 파일은 실행 전후 동일했다. 보존된 입력에 기존 9e30과 cd0 릴리스가 모두 있어 두 원본 릴리스와 새 최종 릴리스를 모두 출력에 남겼다. 초기 9e30만 있는 native CI 입력에서는 초기 릴리스와 새 최종 릴리스를 남긴다.

CI에서 보존된 초기 seed를 사용하는 명령:

```sh
python -m pip install jsonschema==4.25.1
python tools/prepare_recovery_content.py --runtime ../vault/runtime --output ../runtime-recovery --report content-activation.json
```

최종 후보와 초기 seed가 함께 있는 입력에서 실제 재가져오기를 강제하려면 `--seed-release 9e30ec651489a4f5bdbf5c4e727a41a3c7a2b2825a373262056c1e896a82fb7c`를 추가한다. 이 선택은 복사본에만 적용된다. `--verify-only`는 보존 후보의 고정 해시·패키지 파일·스키마·원장을 다시 읽으며 캐시와 실행 데이터를 변경하지 않는다.

생성 보고서는 `implementation_origin=RECONSTRUCTED_PYTHON_ORIGINAL_RAW_SOURCE_NOT_RECOVERED`와 `gameplay=NOT_RUN`을 남긴다. 새 소비자 코드 커밋 때문에 릴리스 전체 해시는 달라질 수 있다. 보존 후보와의 의미 비교에서 제외하는 필드는 `imports.*.applied_before_game_commit` 하나뿐이다.
