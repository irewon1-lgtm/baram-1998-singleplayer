# V2 저장 이전 계약

상태: 구현 및 Linux 합성 저장 시험·실제 baseline/G1 콘텐츠 정의 통합 시험 완료. 개인용 P3 JSON 저장만 대상이며 원본 게임 저장이나 인증 동기화를 뜻하지 않는다.

## 실행 전 고정한 검증 단계

1. 실제 GameState로 만든 합성 구세대 저장을 새 콘텐츠에서 읽는다. 정확히 허용한 profile·4개 compatibility 필드·manifest 지문만 이전 가능하다. 원래 ID·좌표·진행값은 유지하고 추가 스폰만 보충한다.
2. 읽기는 파일을 변경하지 않는다. 명시적 저장에서는 원본 바이트를 `.pre-migration-<SHA256>`에 복사·확인한 다음 후보를 쓰고 검증·원자 교체한다. 원본/백업/충돌 파일을 삭제하지 않는다.
3. 소유자 불일치·잘못된 체크섬·미허용 ID 집합·새 지형의 막힌 좌표·동일 리비전 충돌·미지원 버전은 거절한다. 좌표를 시작점으로 덮어쓰지 않는다.
4. 원본 보존 후 및 후보/백업/교체 경계의 실패를 주입하여 이전/새 스냅샷 중 하나로만 복구되는지 확인한다. 손상된 주 파일은 유효한 백업을 읽고 원본 바이트를 보존한다.
5. 기존 저장 회귀시험과 새 이전 시험을 실제 Godot 4.6.3 Linux에서 실행한다. 이것을 Android/Windows 설치시험이나 실제 사용자 저장 이전 성공으로 쓰지 않는다.

검증 명령·실제 결과는 실행 후 아래에 기록한다.

## 허용 범위와 보존 방식

현재 저장 envelope `baram.gameplay-save/1` 및 payload `baram.p3.gameplay-payload/1`은 유지한다. 과거 P2 합성 저장기 `save_store.gd`와 원본 게임 저장 형식은 변경하지 않았다. `summons`·`bank_inventory`는 선택 필드이며 구세대 저장은 필드가 없어도 읽는다. 구세대의 `character.base_stats` 부재도 유지하며 현재 실행기의 기본 능력치 규칙을 사용한다. 창고/가방 전역 instance ID 중복과 창고/전리품 ID 충돌은 거절하고, 창고의 무기 사용자명·식별 여부를 저장한다. 직업·장비·성장·기술 등의 유효성은 현재 공통 GameState 검증기에 위임한다.

콘텐츠의 `accepted_compatibility`에는 다음 구조로 허용할 **정확한** 구세대를 넣는다. save가 제출한 ID 집합이나 manifest를 그대로 신뢰하지 않는다.

```json
{
  "accepted_compatibility": [
    {
      "profile": "기존 프로필",
      "compatibility": {
        "schema": "1",
        "rules": "구세대 규칙 지문",
        "idset": "구세대 ID 집합 지문",
        "map_geometry": "구세대 지형 지문"
      },
      "manifest_sha256": "구세대 manifest의 SHA256"
    }
  ]
}
```

현재 프로필과 구세대 프로필이 달라지면 계속 DEFERRED다. 기존의 좁은 geometry-only 정책도 유지한다. schema·rules·idset이 같고 지형 지문만 바뀐 경우 현재 지도에서 모든 기존 위치가 유효하면 위치를 그대로 읽는다. 규칙/ID 집합 변경은 위의 네 필드와 프로필·manifest 전부가 일치해야 한다. manifest만 바뀐 동일 규칙·ID 집합의 이미지 변경은 기존과 같이 읽힌다.

정상 이전은 기존 캐릭터·인벤토리·장비·기술·퀘스트·전리품·몬스터 상태를 보존한다. 새 콘텐츠의 스폰 중 기존 몬스터 dictionary에 없는 안정 ID만 기본 상태로 추가한다. 기존 몬스터의 사망·HP·위치·타이머를 새 기본값으로 덮어쓰지 않는다. 현재 정의에서 ID가 사라졌거나 위치가 막혔거나 수치가 범위를 벗어나면 이전을 거절한다.

좌표 변환은 허용 세대 행에 선택적으로 지정한 `map_transforms`만 사용한다. 형태는 `{"옛-map-ID":{"to_map_id":"새-map-ID","dx":정수,"dy":정수}}`이며 캐릭터·전리품·몬스터 현재/홈 위치·소환수·대기 행동/목적지에 적용한다. 변환 후에도 현재 위치 검증을 통과해야 한다. G1은 기존 지도의 크기·충돌·안정 ID를 유지하므로 변환을 사용하지 않는다. 출구 추가로 전체 지형 지문이 달라져도 임의 입구 이동은 하지 않는다.

`read_game`은 계속 OK/RECOVERED_BACKUP을 반환하며 `migration_required`를 추가로 제공한다. 읽기는 원본에 쓰지 않는다. 다음 `write_game`에서 원본 주 파일·구세대 백업을 각각 `.pre-migration-<원본 바이트 SHA256>`으로 복사하고 일치 검증한 뒤 `.pending`을 쓴다. 이미 같은 이름의 보존본이 있으면 바이트가 일치해야 한다. 검증한 후보와 백업의 원자 rename 절차는 기존과 같다. 보존본은 후속 백업 회전에서 삭제/덮어쓰지 않는다. 동일 revision·동일 후보의 이전 저장은 새 envelope로 승격하며, 동일 revision의 다른 진행값은 REVISION_CONFLICT다.

## 실제 검증 기록

2026-10-17 Asia/Seoul, Godot 4.6.3 stable official (`7d41c59c457bd5a245092b4e7eb2d833e3b3f8c3`), Linux에서 실행했다.

| 시험 | 실행 결과 | 근거 |
|---|---|---|
| 구세대→확장 세대 합성 저장 | PASS, 78개 검사·실패0 | `save-migration-G1-r3-4ea4-final.json`의 fixture 검사; 창고 사용자명·가방/창고/전리품 ID 충돌 포함 |
| 기존 저장 회귀시험 | PASS, 83개 검사·실패0 | `save-regression-G1-r3-4ea4-final.json` |
| 실제 보유 baseline→G1-r3 정의의 합성 진행 이전 | PASS, 전체 90개 검사·실패0 (위 이전 fixture78 + 실제 정의 통합12) | `save-migration-G1-r3-4ea4-final.json`; 구세대의 캐릭터·모든 몬스터 보존, 새 엔진 restore 후 즉시 저장 및 원본 보존/승격 확인 |
| 원본 보존 직후 2경계 + 후보/백업/rename 7경계 | PASS | 새 이전 시험이 실제 하위 Godot 프로세스를 종료한 뒤 재실행해 revision·보존 바이트 확인 |
| Android/Windows 실제 기존 앱 업데이트와 사용자 저장 | NOT_RUN | Linux 합성 파일 시험으로 승격하지 않음 |

재현 명령(저장 fixture는 매 실행 새 전용 하위 경로에만 생성):

```bash
Godot_v4.6.3-stable_linux.x86_64 --headless --path rebuild/p2 --script ../../tools/rebuild/v2/test_migration.gd -- --report /absolute/path/save-migration.json
Godot_v4.6.3-stable_linux.x86_64 --headless --path rebuild/p2 --script ../../tools/rebuild/p2/test_gameplay_save.gd -- --report /absolute/path/save-regression.json
```

실제 보유 baseline/G1 콘텐츠 정의에 합성 새 캐릭터를 적용하려면 새 이전 시험에 `--baseline /absolute/path/old/gameplay_content.json --current /absolute/path/new/gameplay_content.json`을 추가한다. 이는 실제 콘텐츠의 호환성을 시험하지만, 실제 사용자 진행 파일을 읽는 시험은 아니다.

통합 시험 대상은 `WORK-GAMEPLAY-GEN001`의 실제 `gameplay_content.json`과 최종 동결한 `baram-V2-G1-r3/gameplay_content.json`이다. 새 캐릭터를 실제 구세대 정의로 생성하고, 능력치·장비 HP/MP 보너스 캐시·소환수·창고 같은 새 선택 필드 없이 합성 legacy envelope를 만든 후 G1-r3에서 읽고 저장했다. 캐릭터의 기존 지도 `gp:map:domestic_city` 및 좌표를 그대로 유지했다. 후속 수정본은 해당 정의 경로를 바꿔 영향 시험을 다시 해야 한다.

창고 기능 추가 후 실제 `unequip`→`store_deposit` 명령은 정상인데 저장기가 `payload.unknown_field`로 거절하는 결함을 재현했다. `bank_inventory`를 선택 배열로 허용하고 가방·창고 전역 ID 검사를 적용하여 동일 명령 경로의 저장 성공을 확인했다. 장비 자원 캐시의 실제 정규화는 공통 실행기가 수행하며 값 변경 시 revision을 증가시킨다. 구세대 무보너스 장비에서는 없는 0 캐시를 임의로 추가하지 않으므로 복구 직후 동일 revision 저장도 충돌하지 않는다.

최종 실행 SHA256:

| 입력 | SHA256 |
|---|---|
| gameplay_store.gd | `57cd5eb6a86d606e33d57969cabf1eabf53be699db9b41815b1e3bbf7e2b7521` |
| gameplay_state.gd (최종 저장 시험) | `4ea4b760f4cdce69db6c8d12a4bfde79f798e0c7d5f3b8e9948725cc2cca3dd0` |
| test_migration.gd | `77c0f1345eb86a7f1bd45e77676fac1978baff4df90f2215550643c0a102477f` |
| 구세대 gameplay_content.json | `30e75ef2f490728c12c17faef3853aabcf132a96f1968e968e475dd94c1ef064` |
| G1-r3 gameplay_content.json | `2214d1050bca3d5490793901971000b6d00de7bcdb740e9895dee850360a598c` |

## 4직업 초반 자연 명령 경로와 재사용 판정

`tools/rebuild/v2/test_progression.gd`는 기존 journey의 탐색·이동·전투·획득 helper만 재사용한다. 부모 run이나 직접 지급/분기 fixture는 호출하지 않는다. 새 캐릭터 4명을 각각 생성한 뒤 실제 이동·공격·tick·획득·판매·구매·장착·전직·학습·귀환·디스크 저장 명령으로 진행했다. tick의 고정 시간 단계는 그대로이며 시간만 가속했다. GUI/수동/실기기 시험이나 1~99 자연 완주가 아니다.

실제 실행은 엔진 `02e675a897acb3cd2a8f365ab055e6f42160b546e5ddb4932fec5ca2c739f27d`와 최종 G1-r3 정의에서 94검사·실패0, 명령5,955회, 시뮬레이션1,420.75초/실제102.159초였다. XP·돈·아이템·기술을 직접 지급하거나 중간 상태를 restore하지 않았다. 모두 공통 기술 비영사천문을 실제 조건으로 학습했다. 전사·도적의 직업 전용 기술이 레벨5에 학습됐다는 주장은 하지 않는다.

| 직업 | 실제 전직 레벨 | 종료 레벨 | 사냥 처치 | 사망 |
|---|---:|---:|---:|---:|
| 전사 | 5 | 8 | 59 | 0 |
| 도적 | 5 | 9 | 84 | 0 |
| 주술사 | 5 | 9 | 91 | 0 |
| 도사 | 5 | 9 | 91 | 0 |

원 실행 보고서 `progression-G1-r3-final.json`과 명령 추적 `progression-G1-r3-final.json.commands.json`은 원래 실행 지문을 유지한다. 이후 마비/침묵 때문에 해제 기술 자체가 차단되는 결함을 수정하여 최종 엔진은 `4ea4b760...`이 됐다. 변경은 `_execute`의 상태 차단 1줄을 요청 기술이 해당 상태를 해제하는 cleanse인지 확인하는 5줄로 바꾼 한 구간뿐이다. 원 실행 엔진 사본의 SHA가 실제 보고서와 일치함을 확인했다.

최종 적용 판정은 **REUSED_AFTER_IMPACT_CHECK**이며 새 엔진에서 자연육성94검사를 다시 실행했다고 쓰지 않는다. `progression-G1-r3-impact-reuse.json`의 11개 비교 조건이 모두 참이다. 콘텐츠·저장기·실행 도구·상속 helper 지문이 같고 실제 추적의 시전은 비영사천문4회뿐이며 상태/버프 사건은0이다. 이 관측 경로에서는 새 지역 변수 `cleanse_statuses`가 빈 배열로 유지되어 기존 차단 조건과 동일하다. 변경된 후반 해제 기능은 B3의 별도 실제 회귀시험 대상으로 분리한다. 저장90/83검사는 최종 `4ea4b760...`에서 새로 실행했다.

재사용 비교 증거는 `natural-impact-old-engine-02e675a8.gd`와 `natural-impact-cleanse-final.diff`다. 재현하려면 아래 명령을 쓴다.

```bash
Godot_v4.6.3-stable_linux.x86_64 --headless --path rebuild/p2 --script ../../tools/rebuild/v2/test_progression.gd -- --content /absolute/path/baram-V2-G1-r3/gameplay_content.json --report /absolute/path/progression.json
```
