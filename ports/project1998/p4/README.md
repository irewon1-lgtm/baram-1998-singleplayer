# P4: original-code playable route

User authorization: “P4진행해”, 2026-10-18. Based on P3 `deb2af36925d69aec729faf4095c2362c58f62f9`.
This is a private Android update candidate. P5 is not started. Device evidence
is separate from Linux execution and signed-build evidence.

## Play

Create an ASCII-letter name (the original name gate), walk through Welcome's
south exit, and follow the Korean objective line. Tap an NPC to talk; tap a mob
to chase and attack; tap floor loot to walk over and pick it up. The attack
button stops a selected hunt. The bag provides use/eat/equip and unequip.

The original chain gives a wooden saber, asks for ten rabbits, gives spring
garb, asks for ten squirrels, and directs the player through the coordinate
lesson to Mignok. Keep five rabbit meat and five acorns for his Soothe lesson.
The guard's original quiz leads to the Angel; speaking `Finish` nearby reaches
Ironheart's home. Talk to Ironheart twice to receive the original 20-gold
training allowance. The original Inn entrance is Kugnae `(56,149)`; its exit
is `(3,13)`. An apple costs 10 gold and sells back for 5. The Inn's original
accept list excludes hunting loot; no shop prices or accept lists are changed.

## Runtime boundary

- Eleven source maps: 4711–4718, 36, 0 and 2; only rabbit/squirrel definitions
  and their original spawn rows on those maps; nine original NPC placements.
  Kugnae's original population is retained, including its area-spawn counts.
- Original `HandleWalk`, `HandleAttack`, `HandleUseItem`, `HandleUnequip`,
  `HandleCast`, NPC Lua and shop handlers run in the Godot C# process.
  The world receives its original 333 ms heartbeat from the app loop.
  No listener, LoginServer, external game process or network transport starts.
- GDScript owns presentation, input and A* planning. Planning asks original
  `MapData.BlockedMove`; the real walk handler rechecks gates and occupancy.
- Private source overlays: existing absolute-root seam, Server library build,
  a partial modifier for snapshot access, and observations at outgoing dialog
  transport methods. Existing rule bodies and Lua files remain unchanged.
- NPC closing sends original text acknowledgements and native menu/input/shop
  cancellation. It does not abandon an item grant before its quest stage.
- Art comes from the pinned DATs: unchanged raw maps, original object columns,
  actors, item icons, spring-garb body and saber/sword frames. The source map
  renderer is the independent raster reference. Equipment layer composition
  is the port renderer, not a claim of complete original-client visual parity.

## Saves and updates

Package `com.irewon.baram.project1998.p3`, versionCode 4, versionName `0.0.4-p4`,
same signing identity as P3. Both arm64-v8a and x86_64 include native SQLite.
No INTERNET permission. Keep the app installed and apply this APK as an update.

P3 data stays under `user://p3/`. P4 creates a fresh character under
`user://p4/v1/`, schema `project1998.p4.vertical-slice` v1. Its guarded content
identity is independent of build-only host code. No automatic P3 demo import.

One SQLite FULL/WAL transaction stores the original character and the world
snapshot, including living mob IDs/HP/positions, ground items, spawn roster,
heartbeat and source batch timers. Slot 2 retains the previous committed
checkpoint; it is recovery history in the same SQLite database, not an
independent device backup. Runtime CharacterStore data is an explicitly owned
disposable cache, rebuilt only after the canonical checkpoint validates.
Unknown/future identity, character/world schema, checksum and foreign cache
refuse startup without overwriting the canonical database. RNG is the original
`Random.Shared`; random draws are not persisted/replayed as a fixed seed.

NPC conversations and shop visits commit when the last window finishes or is
closed. The pre-talk checkpoint remains authoritative while a window is open;
the UI says that saving follows completion. Force-killing a pending visit
returns to that checkpoint, avoiding an item grant saved before its quest
stage. `verify_dialog.py` reproduces the original partial-grant boundary,
kills the process and verifies a clean restart followed by exactly one reward.

## Reproduce and evidence

All supplied source, DATs, fonts, converted art, keys, APKs and prepared builds
remain private outside this checkout. `prepare.py` reuses P3's pinned input
audit and the Android SQLite 2.1.6 setup. `convert.py` compares every selected
map against the pinned original renderer, then includes NPC/mob/item/gear art
and both original gate states.

Run `convert.py` with the original P1 compiler arguments, then `prepare.py`
with `--source --output --font-dir --sqlite-android-nupkg --converted`.
`tooling.py` defines this workspace's already installed Godot/.NET/Android
toolchain and isolated build environment. `build.py --workspace …
--experiment … --output …` exports and verifies the update APK.

`parity.py` compiles `Parity.cs` against both the unmodified original Server
and the adapter: 15 deterministic states compare names, source exit/return,
item Lua, equip/unequip and known Soothe. Random spawn state is excluded from
that comparison. Natural attacks, drops, quests and level rolls are exercised
by `journey_qa.gd` in a real Godot window, without grants, stage edits or warps.
Its off-screen goals use the same client A* API; buttons and targets receive
synthetic ScreenTouch events. This is host GUI evidence, not physical touch.

`verify_storage.py` executes 29 input/UI checks, kills the actual engine during
a full-save loop with SIGKILL, reads the last committed checkpoint, starts a
new engine and compares character, mobs and natural floor loot. It checks both
snapshot checksums, SQLite integrity, six refusal cases and prior P3 hashes.
Failed attempts and their concrete fixes remain in the private evidence.

Android P4 runtime, Galaxy touch/IME, airplane mode, lifecycle, 16 KiB page
compatibility and measured 30 FPS remain `NOT_RUN_DEVICE_P4`. The user's P3
v2 core-success screenshot remains prior P3 evidence only. The older emulator
environment failures are retained; they are not converted to a P4 runtime PASS.
