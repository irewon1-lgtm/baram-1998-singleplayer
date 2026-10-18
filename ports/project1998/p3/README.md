# P3: offline C# core integration experiment

Only P3 is authorized by the user's latest instruction. P4 gameplay and full-world
content integration remain outside this change. P2 Galaxy hardware checks remain
`NOT_RUN_DEVICE`; the instruction to run P3 does not change that evidence.

The candidate architecture is a Godot 4.6 .NET application calling the pinned
original C# rules in the same process. The app targets **net9.0**, required by
Godot 4.6's prebuilt C# Android templates. The original Shared.Core, Shared,
Protocol.Tk495 and Server remain **net8.0**. LoginServer is omitted. The private
Server build is a class library with its host-only `Program.cs` excluded; its rule
source files are unchanged. Networking types still compile because Session is
monolithic, but no TCP transport, listener, server main or tick loop is started.

Fix 1 adds a separately audited **host-path-only** overlay in `Shared/RepoPaths.cs`.
`P1998_P3_ROOT` supplies the absolute Godot sandbox root before any original
configuration or collision lookup. This avoids the original desktop ancestor
walk when an embedded Android runtime has an empty `AppContext.BaseDirectory`.
`HOST_PATH_OVERLAY.json` records original/private hashes. Rule bodies remain
unchanged. The v1 capsule manifest remains byte-identical for save compatibility;
`SOURCE_LINK_MANIFEST.json` additionally records this build-only path overlay.

`OfflineApi.cs` adds state-monitor-protected calls to original `GivePlaced`,
`HandleUseItem`, `MapData.BlockedMove` and `World.TryMovePlayer`. This is a minimal
integration seam, not a claim that the whole server has become a clean mobile SDK.
It proves a bounded route without rewriting the rules into GDScript.

## Reproduce

Keep all private inputs and outputs outside the checkout. Supply the original
Project1998 source, Noto Sans KR font with OFL.txt, and the upstream
SQLitePCLRaw.lib.e_sqlite3.android **2.1.6** NuGet package. `prepare.py` refuses
drift from the pinned original source hashes in `source_pins.json`.

```bash
python3 ports/project1998/p3/prepare.py \
  --source /private/Project1998-master --output /private/p3-run \
  --font-dir /private/fonts --sqlite-android-nupkg /private/sqlite-android.nupkg \
  --converted /private/p2-runtime/assets

python3 ports/project1998/p3/build.py \
  --experiment /private/p3-run --dotnet /tools/dotnet/dotnet \
  --godot /tools/Godot_v4.6-stable_mono_linux.x86_64 \
  --sdk /tools/android-sdk --templates /tools/mono-templates \
  --signing /private/p1998-test-signing --output /private/p1998-s10fe-p3-map.apk \
  --version-code 3 --version-name 0.0.3-p3-map
```

Install the .NET 8 and 9 SDKs into the same task-owned toolchain. Use the .NET
Godot editor and .NET Android templates, Java 17 and Android SDK 35 build tools.
`build.py` runs the unchanged original Server reference in a terminating desktop
oracle, builds the app, runs the actual Godot process twice, then exports and
verifies the signed APK. It never starts either original server process.

Some restricted build hosts expose a parent PID namespace in `/proc`. The
optional `proc_self.c` shim resolves only the current numeric process path to
the kernel's actual `/proc/self`; it changes no process data. `dotnet_msbuild.py`
can also run the installed SDK's MSBuild entry point serially. These are build
host workarounds and are **not** included in the APK. The exact use and failures
are recorded in the private evidence. `--resume` continues after a resolved
failed stage; archive that failed stage's log before retrying.

## Exact experiment scope

The private capsule contains map 4711, four source item rows (3001, 10001, 10009,
10049), MobId 1, original SObj flags and original Lua definitions. Other content
tables are header-only. Automatic spawns, NPCs, warps and shops have zero entries.
The rabbit fixture uses the original fixed spawn's (6,6), but does not enable
full AI or combat. Content bytes and retained rows have source hashes.

`fixtures.json` supplies the same appearance, HP/MP, commands and seed to the
original oracle and the app. There are 39 actions and 40 state snapshots. These
are deterministic cases consuming **zero random draws**. Character creation
uses `FromCreate` and `StartFor`; starting HP/MP are controlled fixture values.
`PlaceNewCharacter`'s Random.Shared rolls, random combat/AI, network cadence,
warps, traps, equipment effects and the full walk packet handler are untested.
Movement here covers normalized cardinal geometry, original terrain and living
mob occupancy. Monster coverage is status expiry/clear and threat bookkeeping.

The oracle calls the unchanged server assembly (reflection is confined to the
desktop oracle). The app calls direct C# entry points; it compares every snapshot
with that separately produced oracle result before reporting success. A host
PASS or successful cross-build does not become an Android runtime PASS.

## Save and rollback decision

| Boundary | P3 choice |
| --- | --- |
| Android package | `com.irewon.baram.project1998.p3`, separate from P2 and Baram |
| Desktop user directory | `project1998_s10fe_p3_20261018` |
| Save namespace | `user://p3/v1/` |
| Outer identity | `project1998.p3.core-probe`, version 1 |
| Character blob | Original Character schema 1, original SQLite store |
| Content version | SHA256 of the exact bounded capsule manifest |
| Engine version | Original source commit `65cb3ef28f289ee35d19abfb6829d6120b9ec0cd` |
| Backup | SQLite online backup API; verified standalone previous snapshot |
| Rollback | Read the backup without replacing current state; migrate into a new version directory later |
| Unknown/future state | Refuse writes; no automatic reset, import or downgrade |

P3 verifies a character snapshot and a previous save's recovery data. It does not
promise durable monster/timer/world-state restoration. There is no P2 save
migration and no access to Baram saves or the original PC server database.

`verify_host.py` runs four real engine processes to verify future-envelope,
wrong-content, missing-identity and future-character refusals. SQLite fixtures
are made through SQLite's backup API, never by copying a live database file.
`android_probe.py` installs the exact candidate in an isolated Android emulator,
disables radios, reads app-generated verification, and checks a cold process.
Emulator and physical Galaxy outcomes must always be reported separately.

`verify_paths.py --godot … --experiment … --previous /private/prior-p3-run
--output /private/path-qa` runs five real Linux Godot processes: an empty managed
base directory with a prior-v1 SQLite backup, blank-output sandbox fallback,
and refusal of a relative output path with a persisted failure record. The first
two cases also run cold and compare all 40 original snapshots. This reproduces
and tests the failed path condition; it does not constitute Android execution.

The user observed versionCode 1 failing on Android with the empty-path exception.
Its exact failure was reproduced in the unchanged original scenario through
`RepoPaths.Root → ObjectFlags.Locate → MapData.BlockedMove`. Fix 1 is versionCode
2, with the same package, signing identity, save schema and capsule hash. Install
as an update. Android runtime after this repair remains `NOT_RUN_AFTER_FIX` until
actual device evidence is supplied. The failure UI now includes the stage and
records the exception without a second unhandled logging-path failure.

## Default entry: original map linked to the C# core (versionCode 3)

The user's next Android screenshot showed fix1's complete 40-state success and
saved-record confirmation. That is actual Android core-probe evidence, within
the displayed scope; it does not establish cold restart, touch or frame rate.
The remaining usability issue was a probe-only landing screen.

Normal startup now opens map4711 with the existing original player/rabbit art.
`InteractiveCore.cs` owns the Character, World, Session, inventory and SQLite
store. `play/core_model.gd` reads those values and interpolates drawing only.
Path planning asks the original `MapData.BlockedMove`; actual movement invokes
`Session.P3Move`, which enforces original world occupancy. Apple/wine controls
invoke `Session.P3Use` and the original Lua. The reused P2 renderer, touch adapter
and A* are copied into the private runtime; **P2's GDScript game-rule model and
JSON save store are not included**.

The initial actor uses the controlled P3 fixture (HP40, MP10), three original
apples and one original 50-charge wine, granted once through the source method.
The player is stored under `p3player`, separate from `p3probe`, in the same guarded
v1 database. Player backups use `p3-player-v1.backup.db`; existing probe rows and
`p3-v1.backup.db` remain untouched during normal entry. `--p3-quit` and
`--p3-probe-only` explicitly run the retained 40-state diagnostic path.

`verify_view.py` runs actual GUI ScreenTouch/Drag fixtures, a second cold engine
process, and future-player refusal. It preserves a prior-v2 SQLite snapshot and
probe backup, then verifies their contents. The 16 GUI checks cover entry, tap,
drag, release outside the pad, four facings, rabbit collision, two-finger wine,
apple, pause and save. These are Linux input fixtures, not native Android touch.
The versionCode3 map scene still requires actual Android retesting. No NPC,
warp, combat, progression or P4 route is implemented by this P3 integration.
