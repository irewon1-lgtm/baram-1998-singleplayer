# P3 compatibility audit and architecture decision

Plan: `P1998_S10FE_NATIVE_PORT_V1_20261018`. Latest authorization: **P3 only**.
This changes sequencing, not the previous P2 hardware evidence. P4 is not part
of this change. The attached master plan and original Baram state are preserved.

## Dependencies and execution boundary

| Component | Pinned dependency | P3 treatment and observation |
| --- | --- | --- |
| Shared.Core | net8.0; no NuGet packages | CSV and logging utilities; it is not the gameplay rule core |
| Shared | net8.0; Shared.Core; BCrypt.Net-Next 4.0.3; Microsoft.Data.Sqlite 8.0.10 | Original Character, CharacterFactory, Mob and CharacterStore used directly; authentication code is unused |
| Protocol.Tk495 | net8.0; Shared | Retained because monolithic Session emits frames; frames go to an in-process sink |
| Server | net8.0; Shared; Protocol.Tk495; MoonSharp 2.0.0 (resolved 2.0.0.0) | Private class-library build, host Program.cs excluded; original rules unchanged; no listener or tick started |
| LoginServer | net8.0; Shared; Protocol.Tk495 | Not built into the app and not required at runtime |
| MoonSharp | managed Lua interpreter | Original Lua heal/drink effects execute against original ItemContext and Session methods; hot reload and all verbs are not claimed |
| SQLite | SQLitePCLRaw 2.1.6 transitive bundle | Desktop package has no Android native RID payload; explicitly add the same-version upstream Android .so per ABI |
| Godot | 4.6 stable .NET, 89cea1439 | GDScript P2 stays separate. P3 app entry targets net9.0; original libraries stay net8.0 |
| .NET | SDKs 8.0.426 and 9.0.319; Android Mono runtime pack 9.0.21 | Host reference and mobile entry have separate target frameworks; SDK downloads are hash-verified |

The source is pinned to upstream commit
`65cb3ef28f289ee35d19abfb6829d6120b9ec0cd`. All **151 C#/project/build inputs**
and **77 content inputs** match that commit's Git blob identities. Preparation
rejects source drift. Original code/content are supplied privately and are not
vendored into this public subtree. No upstream redistribution licence was found;
the binary remains a private compatibility experiment, with no public deployment.
Upstream dependency licences are included in the evidence distribution materials.

## Selected route

Status: **PARTIAL_ANDROID_RUNTIME_NOT_VERIFIED**. The C# implementation, host
parity and signed Android build pass. The Android guest booted, but its package
service restarted during installation; fresh AVD creation then hit a disk-space
limit. The app itself was not executed on Android. Keep this as a candidate
architecture until its Android runtime parity is observed; no GDScript fallback
is justified by a host environment failure alone.

The implemented candidate uses **direct C# calls in the Godot app process**, with a small adapter protected
by the original session state monitor. Avoid a wholesale GDScript rule rewrite.
The unchanged desktop Server assembly supplies the independent reference; its
private methods are reached by reflection only in that desktop test program.
The app uses compiled direct calls through a private-build partial Session.

This is a minimal integration decision, not a completed separation of every
server concern. Server networking types and the protocol assembly still compile,
but the server Program is excluded, LoginServer.dll is absent, no TCP transport
is constructed, World.IsStarted is false, and the APK has no INTERNET permission.
No development-server process is required. Future extraction can narrow this
facade incrementally without changing the rule implementations.

The first prebuilt-template export established that Godot 4.6 requires net9.0
for this route. This is checked in the pinned engine's
`platform/android/export/export_plugin.cpp` (`_validate_dotnet_tfm`), rather than
assuming that the original net8.0 application can be exported unchanged. Android
native SQLite is an explicit separate dependency; successful desktop SQLite use
alone was not treated as Android proof.

## Bounded parity contract

One map (4711), four item rows (3001, 10001, 10009, 10049), one rabbit definition
(MobId 1), original SObj flags and Lua definitions. The fixture's (6,6) rabbit
coordinate comes from SpnId 5. Automatic spawns/NPCs/warps/shops have zero rows.

The same initial appearance, HP/MP, input sequence and seed 1998 produce **40
state snapshots for 39 actions**. The selected operations have no probabilistic
outcomes; random starting HP/MP, combat rolls and random AI are outside the test.
`FromCreate` and `StartFor` construct the state, with controlled pre-existing
HP/MP rather than falsely claiming seeded Random.Shared character rolls.

| Rule example | Original observed result |
| --- | --- |
| Cardinal step onto living rabbit | Refused, player position preserved |
| Acorns 200 then grant 5 | Only 1 accepted; carry total 201 |
| Full four-slot fixture pack | Apple grant accepts 0 |
| Wooden sword grant | Source durability 4000 |
| Eat apple through original Lua | HP 40 to 45; one apple consumed |
| Drink wine through original Lua | HP 45 to 40; MP 10 to 34; one charge spent |
| Mounted character tries food | HP and inventory preserved |
| Rabbit status until 1000 | Active at 999, inactive at 1000 |
| Rabbit threat 7 + 9 | Total 16; zero-id and negative inputs ignored; clear gives 0 |

Movement covers normalized cardinal geometry, terrain and living-mob occupancy,
not the full walk packet/cadence, warp, quest-door or trap pipeline. Monster
coverage is state expiry/clear and threat bookkeeping; full AI/combat is not
silently promoted to PASS. The actual engine runs on the host, and native APK
runtime outcomes are recorded independently in STATE/results.

## Storage decision and execution evidence

New package `com.irewon.baram.project1998.p3`, desktop directory
`project1998_s10fe_p3_20261018`, save root `user://p3/v1/`. Outer schema
`project1998.p3.core-probe` version 1 fences original Character schema 1 and the
exact capsule hash. There is no automatic P2/Baram import or downgrade.

The original SQLite store writes and re-reads HP 39. SQLite's online backup API
produces a standalone previous snapshot with HP 40; integrity_check is `ok`.
Rollback is verified by reading the previous snapshot without replacing the
current state. A future migration must use a new version directory. Durable
monster/timer/world-state restoration is not claimed by this character probe.

Four separate real engine processes test future-envelope, wrong-content,
database-without-identity and future-character protection. The first three leave
the version directory byte-identical. The future-character test preserves the
unknown character JSON; the original store may mark its unreadable timestamp.
No failed load is treated as a fresh character to overwrite.

## Build and remaining platform boundaries

The signed two-ABI APK is `p1998-s10fe-p3-core.apk` (217,461,901 bytes), SHA256
`afb804ddee5da1badbbd072576b835a83c98bd20b36d9938c03f803ce61c7975`.
All 14 selected managed assembly entries match actual export build outputs.
The APK contains both Android SQLite libraries, no LoginServer.dll and no
host-only proc compatibility shim. Signature verification and INTERNET-permission
absence pass. The exporter emits a shutdown-only EditorSettings diagnostic after
successful signing; that is preserved, not hidden as a clean log.

The SDK CLI and embedded build tools initially failed on this host's mismatched
PID/proc namespaces. The optional proc-self build shim points current-process
queries at the real kernel `/proc/self`, and serial MSBuild avoids unsupported
IPC. No game rule, SDK assembly or Android template is patched by this workaround.
Godot CSV auto-import was avoided by packing raw content in a verified ZIP capsule.

Galaxy S10 FE installation, native touch, lifecycle, memory and frame rate remain
`NOT_RUN_DEVICE`. The SQLite Android ELF has observed LOAD alignment 0x1000;
16 KiB-page runtime compatibility has not been tested. Host/emulator execution
must not be read as a Galaxy performance result. See STATE.json and the P3 result
report for the final Android emulator outcome and all failed attempts.
