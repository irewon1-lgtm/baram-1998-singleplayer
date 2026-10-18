# P5: Kugnae region increment

Continues `622b6d94abce7952183a2f27d0257c99a465c5b0` under the existing
`P1998_S10FE_NATIVE_PORT_V1_20261018` plan. The user's “5단계 진행해” follows P4;
the separate V2 independent-review proposal does not restart this port.

This increment contains 47 original maps, 36 NPC placements, 23 spawned creature
types, eight regional merchant keys and the four unaligned class trainers/guild
halls. `scope.py` is the finite map set. It includes the old tutorial, Kugnae
commerce, and maps 50–63 (Rat/Earth caves). The whole world is not imported.

The original C# handlers and four Lua files remain unchanged. `Adapter.cs` is a
transport/snapshot boundary, not a new combat or class system. Internal P4 type
names remain for the saved field contract. `GameCore` delegates the three cast
argument forms (self, typed answer, target entity) to the native learned spell
slot. The client adds a spellbook and a source-exit walking guide. Native entry
requirements remain active; a denied warp stops navigation. Only transient live
occupancy triggers replanning.

Source looks/dyes identify NPC placements separately even when they share a
script key. Regional armor dyes and sword/spear families come from the original
DAT tables. Original 4.95 has no bow raster. Missing item icons remain named,
interactable items; no substitute art is claimed. See `P5_RESULTS.json` for the
four deferred harvesting definitions and other asset gaps.

## Saves and death

The package, certificate and Godot user-data directory remain unchanged.
P3 data is untouched. P4 `user://p4/v1` is read only; an exact known P4 identity
and verified JSON/checksum/schema are required for copy-on-upgrade to
`user://p4/v2`. Spawn indices are mapped by original row/group identity. Old
living IDs and pending respawns survive; only newly introduced point rows are
materialized. A separate owned `cache-p5` is disposable, never the canonical DB.
Unknown/future/corrupt data is refused, not converted into a new character.

Character and world commit in one SQLite FULL/WAL transaction, retaining the
previous checkpoint. Pending NPC/shop conversations commit only on completion
or native close. Native currency is `GroundItem.ItemId == -1`, carrying its
original `Graphic`, amount, owner and looter lock. It is valid in render/export
and cold restore; it must not be looked up in the item-definition table.

The world runs native ticks from the host at 333 ms; no console server, login
server, external network or separate process runs on the device. Pause stops
new host ticks/inputs. Source monotonic/real-time deadlines keep their existing
policy; this increment does not claim a global frozen-time clock or RNG replay.

## Reproduce privately

Use the same frozen source `65cb3ef28f289ee35d19abfb6829d6120b9ec0cd`, official
4.x/5.33 DAT hashes from P1, the P3 Android SQLite archive, and the existing font
and signing identity. All private inputs and generated outputs stay outside Git.
Installed versions are those in P3/P4's locked toolchain (Godot .NET 4.6,
SDK 9.0.319 host / original libraries net8.0, Android build tools35.0.1, Java17).

1. Run `convert.py --source ... --ko-source ... --originals ... --output ...`.
2. Run `prepare.py --source ... --output ... --font-dir ... --sqlite-android-nupkg ... --converted ...`.
3. Use `tooling.environment` for local compilation/import (it carries the
   workspace's proc/SDK workaround). Do not run publication concurrently with
   host tests: Godot publication writes the host Debug assembly/PDB.
4. Run `audit.py`, `audit_source.py`, `parity.py`, `traversal.py`, GUI scenarios,
   storage/dialog/migration regressions with fresh output directories.
5. Run `build.py --workspace ... --experiment ... --output ...` for the same
   signed package, code5. Its receipt verifies signature, manifest, both SQLite
   ABIs and the absence of INTERNET permission. This is BUILD_PASS, not execution.

`gui_qa.gd` labels natural P4 continuation separately from explicitly prepared
Lv5 class/spell/death fixtures. `controls_qa.gd` injects a stale route and briefly
holds the next host tick to avoid an independently moving goal. Spell debit
sampling similarly defers two frames of host ticks so regeneration cannot
masquerade as a wrong mana cost. Combat/quests still use original handlers.
Failed attempts and test corrections remain in the private evidence.

## Current evidence and limits

See `../docs/P5_RESULTS.json` and `../docs/STATE.json`. Map raster parity is
against the pinned independent renderer, not an executed Windows client.
47 maps passed native exit/snapshot fixtures; a natural P4 character continued
through shops and correctly failed the level5 cave gate. Class, offensive-spell,
death and revival checks are explicitly labelled fixtures. Neither parsing a
row nor these host fixtures proves Galaxy playability.

Android P5 runtime, actual fingers/IME, airplane mode, installation-over-P4,
16KiB page support, device lifecycle, FPS, thermal behavior and full-world play
remain NOT_RUN. The signed update is the device-test candidate. Keep P4 installed
and install over it so the v1 save can be copied without deletion.
