# P1.5 검증기 보완 기록

`tools/rebuild/step01/validate_step01.py`의 기존 `available_acquired_files_match_ledger`는 실제 경로가 존재한 파일만 순회하고, 0개를 읽어도 `not bytefails`가 참이어서 PASS였다. v2.0은 `sources.jsonl`·`archive_sources.jsonl`·`archive_members.jsonl`에 선언된 전체 필수 ID 집합을 먼저 만들고 실제 읽은 ID 집합과 대조한다. 당시 원격/옛 작업경로를 현재 접근 가능한 것으로 가정하지 않는다.

검사 범위는 정적 입력 무결성이다. 현재 전체 분모는 2,489개 논리 입력 ID(출처 단위 파일·출처 내부 파일·중첩 member)이며 고유 바이트 수와 다르다. 이전 출처 파일이 manifest 집계 해시만 보유한 경우 개별 `files` 항목이 필수 입력이다. 해시가 없는 웹 문서/발견 후보는 원문 바이트 재검증 PASS로 세지 않는다. EXE/7z 검사는 헤더·경계만 확인하며 실행/전체 해독을 의미하지 않는다. 미지원 형식은 `format_result=NOT_RUN`이고 해시 일치와 별도로 남긴다. 계약이 전체 형식 검사를 요구하면 상위 결과도 NOT_RUN이다.

- 원본 누락·접근 불가: BLOCKED, 종료 코드 2.
- 읽은 바이트의 해시·길이·형식·버전·파서·설정 지문 불일치, ID 중복·참조 오류: FAIL, 종료 코드 1.
- 요구한 파서 미지원 등 미실행: NOT_RUN, 종료 코드 3.
- 선언된 정적 범위의 모든 필수 검사를 통과: PASS, 종료 코드 0.

FAIL → BLOCKED → NOT_RUN → PASS 순서로 상위 결과에 전달한다. `--scope-input`은 좁은 결과를 별도 출력하며 전체 필수 분모를 바꾸지 않는다. 전부 누락된 입력이 BLOCKED인 것과 필수 집합 자체를 비워 둔 잘못된 명시적 계약이 FAIL인 것을 구분한다. 과거 `docs/rebuild/step01/VALIDATION.json`을 덮어쓰는 경로는 차단했다.

실행 방법:

```sh
python3 tools/rebuild/step01/validate_step01.py --input-map /private/input_map.json --output /private/full_validation.json
python3 tools/rebuild/step01/validate_step01.py --input-map /private/input_map.json --scope-input LIB-009 --output /private/scoped_validation.json
python3 tools/rebuild/p1_5/test_validator_regression.py --output docs/rebuild/p1_5/validator_regression.json
```

`input_map.json`은 `{"LIB-009":"/현재/원본.zip","LIB-009-M-실제ID":"/현재/중첩파일"}` 형태다. 외부 source.files의 키는 `SOURCE-ID::relative/path`다. 경로 재지정은 원장 ID·해시·필수 여부를 바꾸지 않는다. 원장의 오래된 경로가 존재하더라도 실제 바이트를 읽어 대조한다. 맵의 알 수 없는 ID도 FAIL이다. 명시적 격리 계약 `--contract`는 schema/validator/parser/config/code 지문, 입력별 해시·길이·형식·JSON 버전 필드 검사를 지원하며 일반 P0/P1 원장 검증과 구분한다.

`validator_regression.json`에는 실제 subprocess 명령·종료 코드·상위 판정·정상/실패 입력의 종류가 기록된다. 정상 완전 입력은 직접 생성한 JSON·CSV·ZIP 세 파일이며 원작 정확성 증명이 아니다. 원장 중복 ID/끊어진 참조/문법 오류/필수 메타데이터 누락 시험은 원장 구조를 격리 복사해 변조했다. 입력 원본은 변조하지 않았다. ZIP 경로 이탈도 쓰기 없이 읽기 검사에서 거부했다.

실제 저장소 원장 실행은 합성 정상 시험과 별도로 남긴다. 초기 실행에서는 메타데이터 PASS, 전체 입력 FAIL이었다. 2,489개 중 실제 읽은 211개에서 210개 일치, 2,278개 미접근, LIB-015의 옛 작업복사본 한 개가 해시·길이·7z 경계 불일치였다. 해당 사본의 실제 길이는 123,801,600바이트이고 원장 기대 길이는 218,174,017바이트다. Library 보관 원본 자체가 손상되었다는 판정이 아니다. 새 입력 맵과 완전 재확보본을 사용하는 실행은 별도 결과 파일로 추가해야 한다. 실행 이후 원본 접근 현황은 최종 `source_access.json`/`VALIDATION.json`을 우선한다.

키 패턴 검사는 공개 정적 메타데이터에서 파일 위치만 보고하고 값을 출력하지 않는다. 원본 실행파일 안전성·악성코드 부재·원작 의미·게임·Windows/Android·실인증은 이 검사 범위가 아니며 NOT_RUN이다.

후속 실제 전수 결과는 `step01_validation.json`이다. 원본/중첩 입력 맵을 적용하고 기존 `existing_branch_checked.json`의 정확한 UTF-8 스냅샷 70개, 이전 `private-intake`/문서의 계획 입력 4개를 원장 SHA256와 대조해 복구했다. 현재 필수 2,489개(출처 단일 파일184 + 출처 내부 파일101 + 중첩 member2,204)를 모두 실제 읽고 해시·길이가 일치하여 **정적 바이트 계약 PASS / 메타데이터 PASS / 종료 코드0**이다. 1,802개는 지원되는 구문/헤더/컨테이너 검사도 통과했고, 687개의 미지원 세부 형식 해독은 `format_result=NOT_RUN`으로 유지한다. 이 687개를 형식 해독 완료라고 세지 않는다. 전체 byte PASS는 모션·대사·확률·원작 의미 판정을 대신하지 않는다.

SOBJADD.EXE는 DOS MZ 형식이었다. 처음 추가한 Windows 확장 헤더 검사에서 DOS 재배치 바이트를 e_lfanew로 오독하는 도구 결함을 실제 원본 대조로 확인하고, DOS 헤더/재배치 경계와 Windows 확장 헤더를 구분하도록 최소 수정했다. 원본을 변경하지 않았다. 올바른 DOS MZ와 잘린 EXE를 별도 합성 회귀에 추가했다.

독립 코드 검토에서 `recheck_archives.py`의 캐시 재해시 누락·새 중첩 해독 오류의 종료 코드 미전달·캐시 재사용 시 처리량 예산 누락을 발견해 통합 담당에게 전달했다. 후속 코드는 캐시 해시/길이 재검사, 저장량과 별도인 전체 처리량 예산, 원본 크기 상한, 모든 중첩 경로명 검사, 해독 오류의 BLOCKED 전파, 사용한 helper 코드 해시 기록을 추가한 것을 정적으로 재확인했다. 이것은 코드 검토이며 해당 추출기의 모든 악성 입력을 시험했다는 뜻이 아니다. 실제 42개/2,204개 재처리 결과와 새 CAB 해독 범위는 `source_access.json`이 소유한다.
