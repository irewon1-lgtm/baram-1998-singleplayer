# 실제 게임 상태 저장 계약

`rebuild/p2/storage/gameplay_store.gd`는 기존 P2 `save_store.gd`의 정규화 JSON, checksum, native USERDATA 링크 검사, 임시 쓰기·검증·백업·원자 교체 알고리즘을 재사용한다. 기존 합성 저장 형식과 시험은 수정하지 않았다.

## 호출

```gdscript
var saves = preload("res://storage/gameplay_store.gd").new()
var saved = saves.write_game("user://gameplay-p3/<owner-hash>.json", engine.snapshot(), owner_id, definitions)
var loaded = saves.read_game("user://gameplay-p3/<owner-hash>.json", owner_id, definitions)
```

경로는 `user://gameplay-p3/` 내부만 허용한다. 소유자 ID는 표시 이름과 분리한 1~128자 ASCII 안정 ID(`local:default` 등)다. 실제 사용자 파일·P2 저장 경로를 읽거나 이전하지 않는다.

성공은 `SAVED`다. `COMMITTED_ACK_LOST`는 이미 교체됐을 수 있으므로 성공 표시·거래 재실행 대신 같은 파일을 다시 읽어 revision과 상태를 확인한다. `OK`/`RECOVERED_BACKUP` 읽기 결과만 활성 GameState로 복원한다. 저장기는 전달받은 상태를 변경하거나 revision을 증가시키지 않는다. 더 낮은 revision은 거부하고 같은 revision의 다른 상태도 거부한다. 같은 상태의 재요청은 `IDENTICAL_SNAPSHOT`으로 확인한다.

## 저장 내용과 검증

봉투 형식은 `baram.gameplay-save/1`, 실제 payload는 `GameState.snapshot()`의 `baram.p3.gameplay-payload/1`이다. 직업·누적 XP·HP/MP·금전·좌표·장착·보유 인스턴스·학습/단축키·퀘스트·전리품·몬스터 생사/세대/리스폰·버프·재사용·대기 행동·32비트 전투 난수·요청 중복 방지 ledger/watermark·revision을 함께 저장한다. 원본 그림·음향·연구 테이블은 저장하지 않는다.

권위 상태의 validator를 호출하기 전에 자료형·크기·깊이를 검사한다. 추가로 소유자, 인스턴스/전리품 충돌, 장착·단축키·기술·몬스터·상점 참조, 스폰/전리품/대기 이동 좌표와 유한한 타이머를 검증한다. 타이머·배율은 유한한 소수이며, 금전·경험치·개수·좌표·revision·RNG는 정수다. 외형은 현재 자산 계약의 `{variant: 0|1}` 또는 기본값 `{}`만 허용한다.

정규화 직렬화 결과의 상한은 **4,194,304바이트**, 깊이 24, 일반 컬렉션 4,096항목이다. GameState의 더 작은 가방/몬스터/요청 ledger 한도도 유지한다. 격리 fixture의 초기 봉투는 1,579바이트였고 실제 P3 정의·64몬스터·외형1·0.05초 진행 상태의 봉투는 18,128바이트였다. 이는 전체 미래 콘텐츠의 최대 상태 크기 측정이 아니다.

## 업데이트와 손상

`definitions.compatibility`는 `schema`, `rules`, `idset`, `map_geometry` 네 개의 짧은 버전/해시 값이다. 첫 세 값 또는 실행 프로필이 달라지면 `DEFERRED`다. manifest만 바뀐 아이콘/음향 업데이트는 허용한다. 지도 기하 버전이 달라도 모든 저장 좌표가 같은 안정 ID에서 유효하면 유지한다. 캐릭터·전리품·몬스터 스폰/위치·대기 목적지가 유효하지 않으면 원본을 유지하고 보류한다. 입구 이동·전리품 삭제·가방 지급은 하지 않는다. 호환성 보류를 오래된 백업으로 감추지 않는다.

손상 시 읽기는 원본을 바꾸지 않고 유효한 `.backup`을 반환할 수 있다. 이후 명시적 저장으로 복구할 때 손상 원본을 `.corrupt-<SHA256>`으로 보존한다. 다른 소유자·미지원 형식·호환성 보류·불안전 링크가 있는 파일/백업은 덮어쓰지 않는다. SHA는 손상 검출이며 계정 인증이나 악의적 편집 방지 수단이 아니다. Godot의 파일 API로 동시 외부 프로세스의 경로 교체 공격이나 전원 차단 내구성까지 보장하지 않는다.

## 실제 시험

`tools/rebuild/p2/test_gameplay_save.gd`는 실제 GameState를 생성한 격리 fixture 시험이다. Linux Godot 4.6.3에서 소수 tick 왕복, 소유권/참조/범위 거부, 이전/동일 revision, manifest/기하 변경, 전리품 보류, 손상·백업 보존, 쓰기 실패, 7개 실제 자식 프로세스 강제 종료 경계, 7개 오류 주입 경계, 부분 기록 검증, 4개 실제 심볼릭 링크를 실행했다. 이 결과를 자연 육성·Windows·Android·계정 동기화 성공으로 세지 않는다. 실기기 링크 fixture를 만들지 못한 경우에는 링크 보호 PASS를 만들지 않는다.

## GUI 통합에서 확인한 타이머 직렬화 수정

첫 자연명령 GUI 실행은 `cooldowns.move=21.310000000000166`을 JSON 재해석할 때 `21.31000000000017`로 바꾸는 Godot 파서 차이 때문에 VERIFY_FAILED였다. P3 전용 canonical은 소수 타이머를 마이크로초(소수 6자리)로 저장한다. 50ms 시뮬레이션보다 작은 정밀도이며 금전·XP·수량·좌표 정수는 그대로 보존한다. P2 저장 알고리즘은 바꾸지 않았다. 종단 재시작 비교는 이 명시된 저장 표현과 모든 실제 진행 필드의 일치를 검사한다. 변경된 타이머 체크섬 거부와 실제 중단 경계 회귀를 포함한다.
