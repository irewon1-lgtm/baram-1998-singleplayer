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
