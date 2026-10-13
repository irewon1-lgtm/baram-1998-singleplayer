# 통합 복원 데이터와 Codex 입력

기준: 사용자 2026-10-13 지시. 정본은 `../../docs/RESTORATION_WORKFLOW_LOCK.md`다. 기존 한국판 조사와 두 조사 브랜치를 파일별로 인수인계했다. 기존 파일은 덮어쓰지 않았다.

이 디렉터리는 조사·제작용 데이터 준비 결과다. 게임 코드·실행 파일·원작 리소스 번들을 제공하는 디렉터리가 아니다. 제작용 숫자 초안을 원작 수치나 플레이 검증으로 표시하지 않는다.

## 시작할 파일

| 파일 | 용도 |
|---|---|
| `CONTENT_CATALOG.jsonl` | 한국판 고유 후보와 북미 복원 ID를 별도 이름공간으로 관리 |
| `NUMERIC_MASTER.jsonl` | 콘텐츠 ID/필드별 적용 초안, 단위, 출처, 근거 분류, 적용 상태 |
| `NUMERIC_SOURCES.jsonl` | 원래 수치와 토큰, 출처·행·연도·변환 연결 |
| `NUMERIC_GAPS.jsonl` | 빠진 필수 숫자와 우선순위·재개 조건 |
| `BALANCE_TESTS.json` | 동일 게임 계산 코드로 실행해야 할 37개 시험 정의 |
| `DROP_RULES.jsonl` | 개체-아이템 연결, 확률, 대체 드롭 그룹 의미 |
| `ASSET_CATALOG.jsonl` | 해시로 중복 제거한 파일 메타데이터·버전·동작 연결 상태 |
| `ASSET_BINDING_GAPS.jsonl` | 그림·동작·방향·음향 연결 공백 |
| `ASSET_BINDING_HINTS.json` | 외부 소스의 시각 ID 후보; 한국판 프레임 일치 증거는 아님 |
| `FEATURE_MATRIX.json` | 자료/외부 코드/게임 구현/자동시험/실제 화면의 독립 상태 |
| `CONTENT_FIELD_MATRIX.jsonl` | 숫자 밖의 필수 콘텐츠 필드와 연결·구현 공백 |
| `SOURCE_VERSION_RIGHTS_LEDGER.json` | 출처·버전·권리와 원본 아카이브 재확보 경로 |
| `SERVER_KR_COMPARISON.json` | 외부 서버·클라이언트 9종 비교와 읽은 코드의 해시 |
| `DEVELOPMENT_PATH_COMPARISON.json` | 5단계 결정을 위한 비교; 최종 방식은 아직 결정하지 않음 |
| `PRODUCTION_ASSUMPTIONS.json` | 원작 미확인 필드의 제작 추정 규칙 |
| `IMPLEMENTATION_MEANS.json` | 한국판 확인값의 사용자 지정 평균과 원래 관측값 |
| `CANDIDATE_REVIEW.jsonl` | 1,674개 입력 ID별 대조·분류·오류·보류 기록 |
| `REPORT.md`, `CODEX_HANDOFF.md` | 완료 범위·남은 장애·다음 작업 순서 |

## 수치 해석

`classification`은 `KR_CONFIRMED`, `KR_MEAN`, `EXTERNAL_REPLACEMENT`, `DEV_ESTIMATE`, `GAP` 중 하나다. `KR_CONFIRMED`도 출처 기재 확인이며 실제 원작 서버와의 일치 시험을 뜻하지 않는다. 실제 패치 유효기간을 모르면 null을 유지한다.

JSONL 한 줄이 필드 하나다. `content_id + field + production_profile`로 읽고, `source_observation_ids`를 `NUMERIC_SOURCES`에 연결한다. 후속 고증에서는 새 관측을 추가하고 그 필드의 적용값만 교체한다. 한국 연도별 원장과 외부 값은 삭제하지 않는다.

가격 방향은 `vendor_buy_price` = 플레이어가 NPC에게 지급, `vendor_sell_price` = NPC가 플레이어에게 지급이다. 안내 가격은 별도 `guide_listed_price`로 남긴다. 방향이 불명확한 가격을 한국 원본 구매·판매 가격이라고 하지 않는다.

누적 경험치는 레벨 L에서 L+1로 올라가기 위한 누적 문턱이다. `exp_band_to_next`는 그 문턱과 이전 문턱의 차이다. 레벨업마다 누적 XP를 빼면 안 된다. 다람쥐 평균 XP7.5는 각 처치마다8로 반올림하지 않는다. 고정 소수점 배율은 추정 원장의 `xp_fixed_point_scale`을 사용한다.

정수 레벨은 평균을 올림한다. 건곤대나이 71.5는 제작 적용72이고, 원본80/63은 유지한다. AC 평균-11.5는 제작 적용-12다. 성장표의 외부 최댓값은 코드에서 배타적 상한이므로 실제 포함 최댓값은 원래 표 숫자보다1 작다. 원래 토큰과 변환은 출처 원장에 남긴다.

1~30 입력률은 필수 스칼라 숫자 초안의 입력률이다. 지도·NPC 임시 좌표195필드도 포함하므로 이것을 실제 배치 완료율로 해석하지 않는다. `(4,4)` 등 임시값은 실제 추출 맵의 좌표가 아니다. 충돌·포털·내부 지도 검증 전 활성화하지 않는다. 이름·원작 ID·대화·직업/성별 제한·기술 효과·그래픽 권리·연결은 `CONTENT_FIELD_MATRIX`와 별도 확인한다.

## 후보와 에셋

확인 성공1,348 / 중복42 / 오류36 / 자료 부족240 / 보류8 = 1,674행이다. 한 행은 출처의 한 표 기록이다. 완전한 고유 게임 개체1,674개가 아니다. 오류 행의 원래 값과 교정된 사실을 함께 보존했다. 보류된 효과·이름을 자동 적용하지 않는다.

추가 팬사이트 대조23행 중 기존에 없던 필드 연결은10개, 이미 알려진 값 재대조는13개다. 조사 건수를 늘리기 위한 재열람으로 세지 않는다. 후대 클래식 검색 결과는 당시 원본값으로 편입하지 않았다. V챔프4페이지를 재요청하지 않았다.

에셋808은 고유 파일 페이로드 해시의 메타데이터 수다. 실제 해독 그림 수는0이다. 기존 세계 조사에서 해독한 DAT 목록을 동일 아카이브 해시 조건으로 재사용했고, 이번에 스프라이트를 다시 해독했다고 표시하지 않았다. NA4.66/4.95는 설치파일 재확보와 완전한 그래픽 페이로드 추출을 분리한다.

## 재현과 검사

외부 자료 작업 디렉터리는 이 공개 저장소 밖이어야 한다.

```sh
python tools/recover_restoration_inputs.py --private-dir /absolute/private-directory
python tools/review_restoration_candidates.py --private-dir /absolute/private-directory
python tools/extract_restoration_gap_facts.py --private-dir /absolute/private-directory
python tools/build_restoration_data.py --private-dir /absolute/private-directory
python tools/prepare_codex_handoff.py --private-dir /absolute/private-directory
python tools/catalog_restoration_assets.py --private-dir /absolute/private-directory
python tools/validate_restoration_data.py
```

`build_restoration_data.py`는 이 디렉터리의 통합 콘텐츠 목록을 입력으로 사용한다. 외부 파일을 실행하지 않고 명시적 데이터만 읽는다. 기존 XLSX 파일 검토는 읽기 전용이다. 콘텐츠 목록의 새 추가·통합은 원래 출처 ID와 연결된 새 입력을 먼저 검토한 뒤 수행한다.

형식 검사 결과는 `VALIDATION.json`과 `validation.log`다. 게임의 동일 계산 코드로 시험을 실행하기 전 `BALANCE_TESTS`의 상태를 바꾸지 않는다. 기존 한국판 검사도 원본 디렉터리를 변경하지 않는 복사본에서만 재검사한다.
