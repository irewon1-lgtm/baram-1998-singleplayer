# P3 original-map client/core integration

The user installed the fix1 APK and supplied a screen showing Android, all 40
original states matching and a saved-record confirmation. The path crash is no
longer shown. The APK still provided only diagnostic text, leaving no map or
character controls. VersionCode3 changes the default entry to the existing
map4711 view and connects it to the original in-process C# rules.

This is P3's one-map client/core integration. P4's NPCs, inter-map travel, shops,
combat, progression and full gameplay route have not been started.

| Boundary | Implementation |
| --- | --- |
| Initial view | Original P1/P2 converted map4711, player and rabbit; no invented art |
| Input | Tap A*, drag stick and four direction buttons |
| Authority | Original `Session.P3Move` and `World.TryMovePlayer`; path queries use original `MapData.BlockedMove` |
| Items | Original apple/wine IDs and Lua through `Session.P3Use`; no GDScript effect formulas |
| Initial state | Explicit P3 fixture, HP40/MP10; three apples and one 50-charge wine granted once |
| Player storage | `p3player` in the same guarded v1 SQLite database; default entry preserves `p3probe` |
| Backups | Player-specific online SQLite backup; existing probe backup preserved |
| Default entry | Map; diagnostic path requires `--p3-quit` or `--p3-probe-only` |
| Android update | Same package and certificate; versionCode3 / 0.0.3-p3-map |

| Execution | Result | Evidence scope |
| --- | --- | --- |
| User's fix1 Android screenshot | PASS observed core scope | 40 states and save confirmation only; device model, cold restart and touch not verified |
| Default map GUI | PASS, 16 checks | Actual Linux Godot with synthetic ScreenTouch/Drag; same in-process original C# |
| Tap / drag / four facings | PASS | Position changes committed by C# and read back by renderer |
| Living rabbit / release / pause | PASS | Occupancy refusal, no stuck movement or cancellation drift |
| Two-finger wine | PASS | Exactly one use, HP40→35, MP10→34, charges50→49, held movement continues |
| Apple | PASS | HP35→40; apples3→2 |
| Separate cold process | PASS | Position, HP/MP and inventory match the previous SQLite save |
| Existing data | PASS | Prior-v2 probe JSON and standalone backup unchanged; player backup integrity `ok` |
| Future player | PASS refusal | Real default startup rejects SchemaVersion999 and preserves its JSON |
| Four existing guards | PASS | Future envelope, wrong content, DB without identity, future probe character |
| Retained independent oracle | PASS | 40 snapshots, SQLite and cold save; unchanged capsule |
| VersionCode3 Android map runtime | NOT_RUN_DEVICE_MAP_LINK | Signed build and host tests do not establish native device touch/rendering |

The first GUI attempt failed before app execution because the new test script
used an untyped dynamic `instantiate` expression. Explicit Control annotations
fixed that harness parse error; the app and test expectations were unchanged.
The corrected run completed all checks. No failed attempt is counted as PASS.

Exact private logs, the APK hash, signed output correspondence, source/asset
freezes and actual Linux map captures accompany the downloadable results.
