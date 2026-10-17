# 바람의나라 B5 실사용 보수 — 앱 r14 / 자료 r12 후보

현재 판정: **PARTIAL_HOST_PERFORMANCE_TARGET_NOT_MET_NATIVE_ACCOUNT_GATES_REMAIN**. B6 정상 납품과 전체 완료는 미달성이다.

최종 앱 소스는639750f0, 자료는 r12/4791e101이다. 도시→동쪽 사냥터 도착 칸의 몬스터 때문에 영구 거부되던 실제 저장을 복구했다. 몬스터752개와 원본 저장을 보존하며 벽·NPC·출구로 뛰어넘지 않는다. 저장의 중복 파싱·복사를 줄이고 UI 행과 외형 미리보기를 필요한 때만 갱신했다.

| 실제 실행 범위 | 결과와 제한 |
|---|---|
| 연속 일반 플레이 | 1809.29초, 목검 판매·재구매·새 인스턴스 장착을 같은 구간 안에서 확인. 더 강한 종류의 무기 업그레이드 판정은 아님. Linux llvmpipe XTEST이며 사람/실기기 검증 아님 |
| 영상 | 원본 1824.80초 전체 decode/SHA 확인. 영상 FPS는 실제 표시 FPS가 아님 |
| 성능 | {"scope": "Every first-process active-play sample inside preregistered continuous1800s phase, no outliers removed. Marker-external active-play and new-process restart metrics are separate; menu/startup/trace-export gaps remain unmeasured and visible in raw video.", "engine_wall_p95_le33_4": true, "engine_wall_p99_le50": false, "engine_input_feedback_p95_le100": true, "OS_received_to_engine_draw_p95_le100": true, "saves_over100ms": 0, "long_wall_incidents": 155, "OS_matching": {"status": "OBSERVED", "all_received_events": 3245, "non_echo_presses": 1623, "echo_events": 0, "release_events": 1622, "press_feedback_missing": 0, "logged_commands": 1622, "matched_commands": 1622, "unmatched_commands": 0, "matched_render_feedback": 1622, "unmatched_engine_presses": 1, "signature_sequence_status": "EXACT_UNIQUE_ORDERED_SEQUENCE", "candidate_command_sequence_starts": [1], "global_logged_commands": 1631, "global_engine_presses": 1627, "global_signature_correlated_pairs": 1627, "ambiguous_commands": 0, "outside_receipt_phase_commands": 0, "key_presses_without_name_or_ascii_code": 0, "latency_outliers_removed": 0, "method": "Unique complete contiguous ordered signature alignment of non-echo presses by normalized physical key name or mouse button and viewport x/y within 2px. No timestamp lower bound or latency cutoff. Ambiguous or incomplete sequence alignments are not forced. Signed cross-clock residuals retain negatives without calibration and cannot validate command latency. Receipt-to-draw uses event_id within the same engine clock."}, "actual_physical_OS_presentation": "NOT_RUN", "human_fun_acceptance": "NOT_RUN", "OS_command_matching_acceptance": "EXCLUDED_UNVALIDATED_CROSS_CLOCK_ALIGNMENT; exact signature correspondence and signed residuals retained; never used to award or fail an absolute command-latency target", "scope_limit": "OS receive starts inside Godot and event-ID post_draw feedback is the bounded measured definition; not physical presentation/guaranteed changed pixels. Command→event latency has unvalidated cross-clock alignment; exact signature correspondence does not calibrate clock drift, so it is excluded from acceptance. Their tails remain in raw evidence; no latency cutoff.", "first_process_active_play_long_wall_incidents": 155, "restart_active_play_long_wall_incidents": 5, "cold_active_play_long_wall_incidents": 7, "all_recorded_active_play_long_wall_incidents": 167, "restart_save_duration": {"n": 2, "p50_ms": 58.541, "p95_ms": 84.181, "p99_ms": 86.46, "max_ms": 87.03, "over50ms": 1, "over100ms": 0}, "cold_sublegs": {"first-process": {"first_save_ms": 85.978, "save_duration": {"n": 8, "p50_ms": 34.736, "p95_ms": 82.506, "p99_ms": 85.284, "max_ms": 85.978, "over50ms": 2, "over100ms": 0}, "movement_seconds": 21.123055678999663, "OS_received_to_frame_post_draw": {"n": 7, "p50_ms": 19.686, "p95_ms": 22.429, "p99_ms": 22.795, "max_ms": 22.887, "over50ms": 0, "over100ms": 0}}, "restart-process": {"first_save_ms": 81.716, "save_duration": {"n": 8, "p50_ms": 34.195, "p95_ms": 66.087, "p99_ms": 78.59, "max_ms": 81.716, "over50ms": 1, "over100ms": 0}, "movement_seconds": 21.033642679001787, "OS_received_to_frame_post_draw": {"n": 7, "p50_ms": 17.715, "p95_ms": 25.068, "p99_ms": 25.543, "max_ms": 25.662, "over50ms": 0, "over100ms": 0}}}, "all_save_sets": {"full_first_process": {"n": 858, "p50_ms": 34.097, "p95_ms": 43.824, "p99_ms": 51.322, "max_ms": 90.797, "over50ms": 11, "over100ms": 0}, "full_restart_process": {"n": 2, "p50_ms": 58.541, "p95_ms": 84.181, "p99_ms": 86.46, "max_ms": 87.03, "over50ms": 1, "over100ms": 0}, "first-process": {"n": 8, "p50_ms": 34.736, "p95_ms": 82.506, "p99_ms": 85.284, "max_ms": 85.978, "over50ms": 2, "over100ms": 0}, "restart-process": {"n": 8, "p50_ms": 34.195, "p95_ms": 66.087, "p99_ms": 78.59, "max_ms": 81.716, "over50ms": 1, "over100ms": 0}}, "all_recorded_save_count": 876, "all_recorded_saves_under100ms": true, "host_numeric_targets_met": false} |
| 기능 | 도착67+행동1323, 현재 공통GUI24/변경없는UI재사용17. r14 저장83/90/368/31 및 cache/generation38(두 보고서를76회 실행으로 합산하지 않음) |
| 성장 | 앞선 가속 명령 초반3시드·4직업 첫기술, 중후반 유한예산 fixture. 자연1~99·새4직업 GUI·재미 합격 아님 |
| 플랫폼/계정 | 현재 r14 native Windows/APK 업데이트·Galaxy·IME·물리음향/표시지연 미실행. 승인된 게임 인증 endpoint 미확인으로 실제 계정 왕복 차단 |

첫 실행의 활성 플레이 전체·명시1800초 구간·재시작 구간을 나눠 긴 프레임과 저장 꼬리를 보존했다. 직전r13은1806초 기능 완주 후 첫 저장116ms로 성능 미달이었다. 그보다 앞선1311초 실제 진행불가/성능 FAIL,17분 도구 클릭 실패, 무결성이 실패한 초기15분은 역사 실패다. ac8a7307은 보정 전 native 입력이며 현재 실행 증거가 아니다.

Android는 기존 앱을 삭제하지 않고 같은 서명의 버전코드6 후보로 업데이트한다. Windows는 새 폴더에 ZIP 전체를 푼다. 실제 native 업데이트/실행은 미검증이다. 남은 수치/긴 정지는 해당 사건부터 보수하고 완료한 자료조사·SDK·G1을 다시 시작하지 않는다.

---

## 이전 후보의 역사 기록 — 현재 후보 PASS로 사용 금지

# V2 G1 implementation and candidate delivery — 2026-10-17

G1 source and content are implemented and verified in the host environment. Android APK and Windows ZIP candidates were built from the same final inputs. Overall status is **PARTIAL_NATIVE_PLATFORM_AND_SYNC_GATES_PENDING**.

App behavior source: `c9fe92886cb738708b189bd14f0c40299ddef301` on `work/rebuild-p3-remediation-20261016`. Later documentation/test-tool commits do not change these binaries. `DELIVERY.json` records exact artifacts and persistent file identities; `VERIFICATION.json` records hashes, test scope and limits.

## Resulting behavior

- G1 binds 76 maps and 152 transitions, 593 items, 190 skills, 346 stable monster IDs (333 exact semantic definitions), 24 NPCs, 52 quests, 9 recipes, 13 advancements and 7 training rules.
- Job learning tables and requirements differ for warrior, rogue, mage and poet. Normal command paths support shop, drops, pickup, crafting, learning, combat/status/projectile effects, equipment, training, warehouse instance storage, weapon naming and advancement.
- Nation-specific starts, gates and return points distinguish Goguryeo and Buyeo. The classic item/skill/equipment/stats panels remain; long NPC service/teacher tables paginate.
- Save migration accepts explicitly compatible manifests, preserves raw primary/backup archives before commit, keeps stable IDs/coordinates and restores equipment/storage instances. Actual final disk/save fixtures passed.
- Available Korean graphics and sound are reused. Unrecoverable geometry/navigation and missing rules are reconstructed with provenance. Exact historical city coordinates and every original formula are not claimed.

The 593 item entries include 484 selected source items, 3 retained helper items and 106 missing standalone dependencies reconstructed from named source drop/learning/crafting references. They are not 593 independently recovered original records. Source effect records are associated for 190/190 skills: 559 fields, 199 adopted, 137 adapted and 223 retained as references. Not all historical semantics are implemented exactly.

## Actual execution evidence

| Test | Result | Practical limit |
|---|---:|---|
| Content compilation | 3,296 checks PASS | Static only |
| Independent contract/acquisition/graph audit | STATIC_PASS | 76 maps reachable; execution separate |
| Engine action fixtures | 1,323 PASS | Explicit Linux Godot fixtures |
| G1 all-ID real command fixtures | 3,655 PASS | Levels/money/materials/RNG are supplied fixtures; no natural full-game claim |
| Engine regression | 131 PASS | Host engine |
| Final save migration / save regression | 90 / 83 PASS | Host disk; no different Android package auto migration claim |
| Four-job early progression | 94 PASS, reused after impact check | 5,955 commands; natural level5 job change, end8/9/9/9; accelerated engine time only |
| Exact Windows embedded PCK GUI | 89 logged PASS, scope limited | 74 GUI/fixture,12 logical bounds,3 nonempty framebuffer checks |
| Exact PCK touch/input-event edges | 13 PASS | Injected Godot InputEvent under Linux; not physical Android touch |
| Exact PCK ordinary create/save/restart/continue | 10 PASS | Actual Linux window, XTEST input; not native Windows |
| Actual APK/PCK compiled script/manifest parity | 11 PASS | Byte equality; not Android execution |

Early progression ran on engine SHA `02e675a8…` before the final cleanse-only guard change. The 11-condition impact review and recorded diff show that the trace contains no affected cleanse/status actions; this is **reused evidence, not a new execution on final engine**. Final combat/all-ID/save suites ran against final engine `4ea4b760…`.

GUI resolution limits are explicit: 1100×720 screenshot is complete. A 1600×900 request produced a1375×900 surface, and a600×960 request produced600×392. The harness forced logical app dimensions and only checked nonempty framebuffer data. Those counts do not prove three physical resolutions or portrait support. The Android candidate is configured for landscape. Actual mobile layout remains a native gate.

Prior failed fixture/UI cases and the XSendEvent-only ordinary restart input attempt are retained in the evidence archive. The identical final pack passed ordinary restart after switching to focused XTEST input. No app change was made for that input-method correction.

## Candidate provenance and installation

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Android APK | 65,168,379 | `54316901c31bef6e748bcd2935dbe6812f811f307e11f2d1f72fb2a3294fc970` |
| Windows ZIP | 38,533,242 | `256d51d9c9ca4bb819489d19483fabbfbe11cc87e3ccb8ff1d476c4df56adc67` |
| Windows EXE | 125,057,832 | `7a35dbf9581de9613ba5a79f0d2d838f3c51dea487a23f480dd5d8b4ad391af3` |

Android retains package `com.irewon.baram.p3repair20261016`, signer fingerprint `c0bc3989d93d7b9443bbfa59281797a48e2b020e5da4b1dc91858768b35ccd05`, user directory `baram_rebuild_p3repair_001`, and raises version code to3. If the same repair package is installed, preserve it and install as an update without uninstalling. Actual device update/save retention is untested. An older different package's saves are not guaranteed to transfer automatically. Windows ZIP should be fully extracted into a new directory before running the EXE.

Both exports preserve 49 source and3,411 runtime snapshot hashes with fingerprint `0f5a52596dc7352dfb3681e1c8d327acdee58ec1b3322a080989749b3dfdd25b`. Runtime manifest SHA-256 is `6ffdfc0cbad388635dd641579adfdb12ad0539726d13e8fdfb7c4f0b4227d1a9`; content SHA-256 is `2214d1050bca3d5490793901971000b6d00de7bcdb740e9895dee850360a598c`.

`git_head_at_export` truthfully records39c7e4a2 because the local ref had not yet advanced when export began. Actual per-file snapshots match published behavior commitc9fe9288; no app/runtime input changed after export. Nonfatal diagnostics include18 Unicode warnings per import and an unspecified Android project icon. Final export contains no script parse error.

## Remaining gates and exact resume point

Native Android/Galaxy and Windows execution, OS Korean IME, physical audio, physical multitouch/latency and device30FPS remain NOT_RUN. Prior Android render failure is not closed by a readiness log or Linux rendering. Authenticated same-account Windows→Android→Windows continuation is NOT_IMPLEMENTED; no approved accessible free authentication/sync endpoint exists in this environment. Local owner/checksum validation is not authentication.

Resume with the exact delivered APK and Windows ZIP on the required operating systems. Check visible first frame/menu, creation/IME, ordinary hunt/learn/return/save/restart, repair-package update and retained saves, touch and frame time. Implement/verify authenticated sequential continuation once the free endpoint is available. Reuse current source, private runtime and retained private signer; do not restart full inventory, SDK acquisition, decoder work or candidate export without changed inputs or a reproduced app defect. Source assets and signing keys remain excluded from GitHub.

