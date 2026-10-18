# P6: Korean display, mobile UI and six-defect repair

The latest user report supplies physical Android P6 evidence of six defects.
See `../docs/P6_REPAIR_CONTRACT.json` and `P6_REPAIR_RESULTS.json` for the
repair boundary and actual execution. The new update is code7 /
`0.0.6-p6-fix1`, not P7 hardware acceptance. The world now fills the canvas
behind translucent controls without a D-pad. Original action4 drives original
pickup poses 76..79. Actors interpolate over 0.2 seconds and source walk
frames follow movement. Region guide displays preserved local map art and
Inter.dat FIELD10; four separate parchment windows expose inventory, spells,
equipment/paperdoll and effective source stats.

The explicit user-requested offline tutorial bypass sets the newbie stage to
at least10 and enters Kugnae map0 at (87,147), the original tutor-home
Warp589 destination. It retains earned character data and awards nothing.
The existing canonical checkpoint commits stage/location and world together.
This is a declared exception to the earlier presentation-only P6 scope.
Normal source gate and quest handlers remain unchanged.

`repair_art.py` requires frozen Inter.dat and NexusTK.dat, emits only private
assets and audits palette raster hashes. `RepairSession.cs` adds a bounded
outgoing pose observer, read-only effective stats and the explicit bypass.
`RepairCore.cs` exposes that operation through the existing checkpoint.
`repair_fixtures.py` copies prior actual saves and labels only the prepared
pickup/spell changes. `repair_qa.gd` executes the finite six-defect checks,
portrait/landscape windows, cold restore, fresh main entry and P6 update.
`repair_package.py` creates separately named delivery/evidence; retain code6.

The following describes the original code6 P6 baseline; its device UI
acceptance is superseded by the user screenshot and this repair contract.


Continues P5 commit `cda6fe275dd2e41635a5fd20def137d3bd57c115` under
`P1998_S10FE_NATIVE_PORT_V1_20261018`. The user's “6단계 진행해” authorizes this
increment, not a restart under a separate review plan. The 47-map region and
all original rules remain the P5 scope.

`catalog.py` joins text from the supplied Korean candidate by numeric ID AND
immutable identifier. It never replaces rule CSVs. Manual/composed translations,
proper names and equivalence to historical Korean names remain REVIEW.
Application coverage counts source rows: 47 map names, 255 stock/buyback/drop/
starter item names, 180 common/base-path neutral spell names, 36 NPC placements
and 23 spawned creature names. These are finite presentation denominators,
not a claim that every item/spell or the whole world has been played. Selected
tutorial, merchant and trainer dialogue is translated; later quest dialogue
can retain English. `LOCALIZATION_AUDIT.json` records the full-source and
regional rates separately from actual execution evidence.

The core snapshot retains original names and values. A shop button displays
Korean but submits the original name/slot, and an NPC menu submits its unchanged
index. Korean “완료” and direction answers map to the native ASCII commands.
Unsupported Korean answers are refused visibly before the wire can replace
them with question marks.

Korean character names are **display aliases**, held in optional atomic
`profile-p6.json`; original `Character.Name`/keys/protocol are unchanged. New
Korean or long display names derive a stable letter-only internal name that
still passes original `NameRules` (3–11 letters). Existing P5 names remain
unchanged. Alias schema errors preserve the file and refuse profile writes.
The saved game stays in `user://p4/v2`, with exact P5 schema and capsule hash
`a354ffd0e90a3d1ca447ad51f63e33f634e6a99d95e00890c866609f710507f6`.
P4 v1 remains a protected read-only import and P3 is untouched.

The UI uses separate landscape/portrait canvases, wrapped text, scrollable
dialogs/inventory/spells, a modal input shield, keyboard avoidance, original
HP/MP values, and clearer font weights/actor labels. A source-exit guide still
walks to original gates. Pause/back cancels held input and saves; pause also
stops audio. Synthetic resize/pause/key commits are host fixtures, not Android
IME, rotation or lifecycle evidence.

`Media.cs` observes the original outgoing `SendSound` after its native validity
gate. It changes no sound selection or rule. The 184 actual 4.95 WAV members
are extracted from frozen NexusTK.snd. Legacy text metadata is removed and
odd RIFF chunks padded; every decoded PCM byte is checked unchanged. The client
deduplicates the bounded native event sequence and supports volume/mute.
Original MIDI music has no supplied synthesizer/bank and remains unimplemented.
Implicit Windows action sounds, full spell graphics/cast poses and complete
equipment/client-window parity are not claimed.

## Reproduce

Use P5's frozen original source/toolchain/assets and the same signing identity.
Keep all original assets, compiled output and signing material outside Git.

1. `prepare.py --source ... --ko-source ... --originals ... --converted <P5-converted-4> --output ... --font-dir ... --sqlite-android-nupkg ...`.
2. Use `tooling.environment` for .NET build and Godot import. This retains the
   proc/SDK workaround needed in this workspace. Do not publish Android while
   host tests run: publication rewrites the host Debug assembly/PDB.
3. `audit_source.py` restores only declared seams and compares 145 original C#
   files. P5 content/raster/parity evidence remains valid because the capsule,
   raw maps, Adapter.cs, Checkpoint.cs and rule bodies are unchanged.
4. `make_fixtures.py` labels prepared class/spell/death cases explicitly.
   `run_qa.py` runs real Godot/Xvfb in one namespace. GUI scripts exercise native
   menus, Korean input/commands, source shop transactions and four class flows.
   `verify_storage.py` performs actual SIGKILL, cold restore and six refusal
   cases. `performance_qa.gd` measures Linux frames; RUNNER.json records peak RSS.
5. `build.py` exports code6 `0.0.6-p6`, same package/certificate, both SQLite
   ABIs and no INTERNET permission. BUILD_PASS is not Android execution.

## Verification boundary

See `../docs/P6_RESULTS.json`. Keep failed runs and their actual causes.
Korean glyph availability/application is not meaning/era approval or a claim
that all rows were visually inspected. Host Unicode key commits are not a
Samsung keyboard composition test. Galaxy touch, speaker, installation over
P5, airplane mode, Android lifecycle/rotation/IME, 16KiB support, heat, battery
and minimum device FPS remain NOT_RUN_DEVICE. Install the update over P5/P4
without uninstalling; actual-device acceptance belongs to P7.
