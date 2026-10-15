# P1.5 메타데이터·저장 계약 감사 범위

이 파일은 통합 REPORT/VALIDATION을 위한 보조 근거다. 원본 `step01/sources.jsonl`197행과 `requirements.csv`120행을 수정하지 않았다. 새 게임·기준 서버·실인증·설치·기기 시험은 수행하지 않았다.

## 출처 정리

`sources_delta.jsonl`의 기존197 ID에 `UPDATE_EXISTING_METADATA` 보완을 기록했다. 누락79개 `source_type`은 실제 파일/문서/데이터/서버 재구현/도구/차단된 웹 발견으로 구분했다. 기존118개 유형은 보존하고 `material_kind`로 내용 종류를 보충했다. `source_family`는 출처 레코드의 명시 계보와 실제 경로를 기준으로 보수적으로 묶었다.

Project1998은 기존 명시 계보상 RTK/ClassicTK 파생이므로 RTK와 공통 계보로 묶었다. TKViewer/TKMapper/EPFViewer와 olds463 포크는 공통 설계 계보로 묶었다. 개인 파생 아틀라스/공유 ZIP은 개별 member가 KR491과 일치해도 묶음 전체를 독립 한국 원본으로 승격하지 않았다. 단독 BARAM.PAL과 판본 불명 `1997` 이름 묶음은 계보 미확정을 유지했다. 차단 웹은 원문 확보로 바꾸지 않았다.

이 보완만으로 원본197행의 `fact_status`, `use_status`, `test_status`, SHA를 승격/변경한 건수는0이다. 메타 분류는197개 파일을 새로 확보했다는 의미가 아니다. 신규 확보 출처는 통합 담당이 이 파일 끝에 별도 ID로 추가한다.

## 우선순위와 요구 추가

`requirements_delta.csv`는 기존120 ID와 원래 정상/실패/취소360개 설계를 그대로 유지한다. 각 행에 이전우선순위·이유·실제차단단계를 추가하고 우선순위를 개별 재평가했다. 기존114 P0/6 P1에서70 P0/47 P1/3 P2로 바뀌었다. 우선순위P2와 개발단계P2는 다른 필드다. P2 우선순위3개(승급, 자연회복/안전구역, BGM/MIDI)는 제거하지 않고 P5/P7 등 명시 단계에서 검증한다.

RQ-121~150의30행은 NPC 개별 외형, 대사 원문/설명/재구성, 퀘스트 전상태, 확률 형식/관측 오차, 스폰 종류/상한, 제작 시대/실패/수리, 실제 모션/단위, 기술 효과/음향, 목표시기 지도, 각 이동기능, 생성 순서/빈 UI, 맵 이전/저장 검증/중단, 검증기 필수집합, 계보/전수분모/사용상태 구분을 추가한다.90개 정상/실패/취소 설계가 추가돼 총150행/450설계이며 실행 결과는 아니다. 현재 상세 지시문 source ID는 `PLAN-P1_5-INSTRUCTIONS`다.

## 저장·이어하기: 실제 재사용과 미해결

고정 커밋의5개 기존 소스를 GitHub로 다시 읽고 기존 size/SHA와 대조했다. OLD-SAVE-STORE, OLD-CONTINUITY-CLIENT/JOURNAL/ACCEPTANCE, OLD-CLOUD-README 모두 일치했다. 정확한 SHA·메서드 위치·관측값·필요한 구현·정상/실패/취소는 `selected_content/save_contracts.json`의8개 참조 계약을 정본으로 둔다. 재독한 기존 코드5개는 신규 한국 원작자료5건으로 세지 않는다.

기존 payload SHA·bounded pending→validate→backup→rename, future-version 거부, 계정별 dirty/lease/CAS/request/replay/conflict 사본 패턴을 좁은 참고 입력으로 골랐다. 새 저장스키마는 미선정이며 `selected_for_build=false`, 게임 BOUND/EXERCISED=0이다.

추가로 드러난 범위 제한은 다음과 같다.

- 기존 저장 validate는 기본 player 수치와 사전 형태를 검사한다. inspected 모듈 안에서 map 좌표 유효성, owner identity, 깊은 world/장비/퀘스트 구조·안정 ID 참조 검증은 확인되지 않았다. 저장 유효성 전부를 통과시키는 부품으로 재사용할 수 없다.
- SHA는 payload 문자열만 덮고 바깥 content_version/game_build는 덮지 않는다. 단순 checksum을 인증/서명 또는 완전한 envelope 검증으로 보고하지 않는다. 이 사실은 코드 구조 관측이며 원격 공격이 실증됐다는 뜻은 아니다.
- flush/rename 호출이 있다는 사실과 Windows/Android별 실제 교체·전원/강제종료 복구는 별개다. journal도 필드 존재만 확인하는 부분이 있어 깊은 형식 검증과 경계 중단 시험이 필요하다.
- 캐릭터와 바닥 전리품의 맵 세대별 명시 좌표변환은 inspected 저장/저널 모듈에서 찾지 못했다. 전체 저장소에 없다는 주장으로 확대하지 않는다. BND-027/RQ-138의 변환표·원본보존·멱등 시험은 미해결이다.
- README의 실제 Auth/RPC 배포 pending와 옛 CI 주장들은 현재 서비스 상태/실제왕복 증거가 아니다. 서비스·계정·키를 조회하거나 배포하지 않았다.

## J/SAVE 분야 통합용 남은 공백

|공백|확인 분모와 실제 범위|상태/영향|다음 정확한 작업|
|---|---|---|---|
|새 저장스키마/안정ID/계정·좌표 의미검증|기존5소스 재독;8참고계약. 새스키마0개선정|UNBOUND. P2-05/P3 저장계약|SAVE-P15-ENVELOPE와SOURCE5개해시를입력으로 신규ID/스키마를별도선정; synthetic foreign-owner/unknown-ID/outer-metadata 변조시험|
|원자교체·강제종료|필수OS2종;이세션실행0종|RUNTIME_OBSERVATION_NEEDED. P2-05|P2-SAVE-01에서 Windows/Android 각각 pending/backup/rename 경계중단·공간부족시험|
|맵세대/캐릭터·전리품이전|필수상태종류2종; inspected모듈변환루틴0개|UNBOUND. P2-05/P6|P2-SAVE-02에서 같은셀유지/명시변환/막힌셀/변환표누락/중단을 원본보존으로검사|
|계정순차왕복|PC→Android→PC 3hop 요구;실제HTTPS/Auth왕복0회|RUNTIME_OBSERVATION_NEEDED. P2-06/P3/P6|별도승인·기존무료환경/격리시험계정확보뒤 P2-SAVE-03; stale revision/ACK유실/lease/충돌사본 검사|
|실기기·서명·환경접근|현재Linux PATH읽기만실행;adb/wine/godot없음,java존재|도구없음/미관측. 권한거부·계정없음으로추정금지|실제Windows·Galaxy연결과 SDK/엔진/템플릿·서명 metadata를 P2 G0에서읽기전용확인. 기존서명키값은열지않음|

현재 환경의 Linux 관측은 실제 Windows/Galaxy 시험을 대체하지 않는다. 실기기·기존 서명·실인증은 NOT_RUN이며, 새 무료 프로젝트 생성이나 실제 계정 정보 입력을 요청하지 않았다.
