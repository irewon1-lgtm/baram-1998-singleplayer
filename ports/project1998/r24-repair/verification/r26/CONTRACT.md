# P1998 9-issue repair execution contract
0. Baseline: verify exact r25 input hashes, existing certificate, compile and reproduce signed APK.
1. Reproduce entrance330 and rat/bat candidates with original movement; fix proven coordinates and stale input generation. Preserve unknown current user location.
2. Compile candidate navigation with independent shortest-cost tests; test actual Godot floor tap, retarget, cancellation, transition; build first update.
3. Every registered map and effective warp gets a separate ledger row; directional collision, doors, arrival/return, conditions; do not promote unrendered/unwalked rows.
4. REPLACED BY USER: compare level1 and progressed characters on the same map; measure visited terrain cache/materialized maps/active and retained monsters, world and save sizes, RAM/CPU/GC/input latency. Identify repeated all-world capture/serialization/SQLite work per move/attack and eager unchanged-map restore. Optimize without disabling or weakening any character/world/item/quest commit. Verify cold reopen and ongoing play on physical device only if a device is available; otherwise NOT_RUN. Original step4/BGM work is not the substitute for this investigation.
5. Freeze inputs, full regression and unchanged66 comparison, save/crash/backup; signed arm64 package verifies embedded code/data, retained identity and increased code.
Completion requires final signed update APK plus source/tests, map/warp ledger, nine-issue report. Any required NOT_RUN/BLOCKED/FAIL prevents whole-task PASS.
