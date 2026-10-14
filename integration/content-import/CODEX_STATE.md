# Codex 실행 인계 — BARAM_PARALLEL_V1

- 담당: 실행 코드·가져오기·통합·저장 보호. `content-work/**`는 읽기 전용이다.
- 브랜치: `codex/game-core`; 별도 폴더 `/workspace/baram-codex-core`.
- 최초 게임 기준: `dev/codex-asset-runtime-20261014`, `dea6574c9a69ebb04432d10fc32951aacd8b66cb`.
- 시작 시 Work 원격: `work/content-import`, `dea6574c9a69ebb04432d10fc32951aacd8b66cb`.
- HANDOFF_INDEX/PROTOCOL/schemas/packages: 위 고정 커밋에 없음. `WAITING_INPUT`이며 시험 FAIL이 아니다.
- 엔진: 기존 Godot 4.6.3, 독립 오프라인 런타임. 기존 숫자 정본은 `game/data/numeric.json` 생성 원본과 연구 수치이며 변경하지 않는다.
- 영구 기존 ID: `kr.*`, 제작 보완 `generated.*`, 기존 맵/배치 ID는 그대로 유지한다.
- 현재 저장: 체크섬 payload와 schema 1, `.pending` 교체 및 단일 `.backup`. 읽기 오류를 새 게임으로 취급하고 미래 schema에서도 백업을 읽는 경로가 있어 보강 대상이다.
- 사용자 원본 저장은 읽거나 초기화하지 않는다. 시험은 비공개 사본과 새 디렉터리에서 한다.

## 이번 묶음의 사전 검증 기준

1. 가져오기: 해시·크기·스키마·전체 ID·참조·확률·의존성을 검증한 immutable release와 ACTIVE 전환. 재수입 중복 0, 실패 후 이전 ACTIVE/원장 동일, 같은 batch의 다른 manifest는 CONFLICT.
2. 실행 시스템: 공통 거래/개별 장비/효과/퀘스트/강화/승급 경로의 짧은 Godot 검사. 시험 데이터는 `test.*`이며 정식 Work 콘텐츠 수에 포함하지 않는다.
3. 저장: schema 1 사본 읽기→변환→재저장→재로드. 미래 버전과 손상 실패 시 원본 유지, 자동 새 게임/미래 파일에 과거 백업 fallback 금지.
4. 통합: 실제 Work READY가 있으면 그 확정 커밋만 검증·반영하고 SHA를 receipt 후속 커밋으로 기록. 없음이면 WAITING_INPUT을 유지한다.
5. 주요 시스템 연결 후 짧은 실제 화면 통합과 사용자 실행본. 장시간 자연 육성·Windows 실제 실행은 별도 NOT_RUN.

## 재개

현재는 위 기준을 실제 코드로 구현 중이다. 완료한 자료 해독·60페이지 검토·변경 없는 기존 시험을 다시 하지 않는다.
