# Mobile control quality verification contract

Baseline: work/mobile-continuity-20261015, 2bb4ec55fa8ccb347b11d2bf2532ae4d4806b76a. Origin heads queried 2026-10-15. Delivered APK SHA256 8189f0b85a67a67732eaf09cbbbc4449fc884cf5c62a872ef29d39b7fa76beee. Signing certificate SHA256 f8cf43158c663e80b3e15aaa82681ea328be009ea900c7c5ea68e8a6ddec608a. Original worktree and files preserved; isolated worktree used.

1. Baseline: inspect exact package/signature/source; replay five defects and capture actual frames. Exact ARM64 APK replay is NOT_RUN without an ARM64 Android device; same-source replay must be labeled separately.
2. Implement shared render direction mapping, continuous visual position/camera, bounded four-way path commands and mobile overlay controls. Preserve rules, schema, assets and continuity implementation.
3. Execute source checks, actual rendered direction/contact/input regressions, 20 retargets, blocked paths, two-finger cancellation, menu/back/focus, 30/60 speed comparison and >=600 s continuous activity. Collect frame times, long frames, screenshots/video. Emulator != Galaxy. Desktop Linux != Windows.
4. Build signed same-package Android update and Windows package from identified commit, verify delivered hashes and signature. Reproduce test artifact identity. Never mark export-only or synthetic-only as full acceptance.

Required outcomes: full field mobile layout; tap-to-route and contextual interaction with real range checks; correct visible layers/directions; continuous movement; usable combat/menu controls. Any unmet mandatory criterion remains FAIL/BLOCKED/NOT_RUN.

Existing cloud account/HTTPS roundtrip was BLOCKED before this change and is independent of UI acceptance. No new paid services or remote-control prerequisites.

Implementation finding: raw EPF U/R/D/L frames contrasted with stored/input U/L/D/R; all render layers now use one mapping. Original camera advanced immediately to the logical tile, while actor interpolation lagged; both now share visual position. Rapid tap retargeting must preserve touch-down camera coordinates until release (movement continues during a tap). Existing gameplay numeric definitions and assets are unchanged.

Native CI resumed after the explicitly authorized exact work/mobile-controls-20261015 environment branch rule was added; the original codex/game-core rule and all other protections remain. All native artifacts remain AES-GCM encrypted on public Actions. Windows actual EXE core/restart and 12 rendered direction frames PASS on a73a504. Android exact APK run 38697066012 reproduced an Android Back exit despite the existing modal notification handler: SceneTree.quit_on_go_back was still true independently of auto_accept_quit. This is corrected without changing the engine. Android NPC approach, field travel, actual combat XP, real loot acquisition, skill use, return to town, 24 command dispatches, bag opening, and modal input consumption ran successfully; overall run FAIL until Back and final destination are retested. Galaxy ARM64 hardware remains NOT_RUN.

Native retarget observer correction: the previous test converted a world goal with an F8 camera snapshot, then adb latency allowed the camera to move before touch-down. Its expected [64,165] versus observed [62,165] was not sufficient evidence of a game path regression. The revised test separately requires exact coordinates from a stationary camera, then logs every touch-accepted navigation command and requires arrival at the last actual goal, an empty path, and no later movement. No collision/navigation implementation is relaxed.

Additional native two-pointer job downloads the identical encrypted APK artifact from the story job, checks its hash, and injects Android MotionEvent pointer IDs through a CI-only shell driver. It uses a fresh disposable emulator, never clears a user's app data, never ships the driver, and records movement/attack/skill/outside-release/lifecycle plus four-direction frames. Its checks are NOT_RUN until CI completes.

Log classification correction: prior no-runtime-errors check matched Android emulator eglCodecCommon teardown warnings as game errors. The revised report preserves all OS logs and lists those renderer messages separately, while failing on Godot script/errors or Java fatal exceptions.
