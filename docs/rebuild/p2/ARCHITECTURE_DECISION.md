# P2 architecture decision — candidate, not final platform freeze

Task `BARAM_REBUILD_CODEX_P2_001`. Keep MASTER_PLAN/STATE/P1.5 and existing game
unchanged. The current user request authorizes G0/P2; their earlier prohibitions
are preserved historical records. P3/P4/production/main merge remain excluded.

One new Godot project lives in `rebuild/p2`. `input/` receives unhandled events,
`state/` holds shared inspection state, `ui/` owns panels/focus,
`render/` shows missing-input diagnostics, and `storage/` owns the save contract.
There is no second game, web mockup, generated art or wholesale main.gd import.
Actual map/composition/effect/audio consumers must wait for scoped G0 and their
complete source/reference closure. Missing assets stay explicit errors.

The experiment uses exactly Godot 4.6.3 official `7d41c59c4`, GDScript and the
compatibility renderer, matching the preinstalled engine. Official export
templates were SHA512-checked. Windows x86_64 and Android arm64/x86_64 derive
from this same project. Android target package is
`org.baram.rebuild.p2.codex001`, with a new private synthetic debug key and an
independent user directory. No installed app, original key, font or real save is
included or changed. Native Windows and Galaxy remain separate acceptance gates;
Wine/emulator results cannot finalize those decisions.

The APK is an automatic technical-test app (`p2_smoke` export feature), not a
playable slice or existing-app update. Its four panels and bottom status verify
structure; the unavailable photos, original icons and equipment appearances have
not been reproduced. System fonts are used at runtime and never packaged.

Storage is a new implementation of the narrow pending/verify/backup/replace
pattern. `storage/PROVENANCE.json` records the actual fixed old save-source
fingerprint and source inspection. Schema `baram.p2.synthetic-save` version1 is a synthetic P2
contract, not adoption of the old schema or a real-save migration promise.
SHA256 detects corruption; it does not authenticate an account. Owner/content/ID
validation and map update deferral are independent of checksum verification.
Power-loss persistence and native filesystem rename behavior remain unverified.

Historical profile default stays null. `P2_INFRASTRUCTURE_ONLY` and
`synthetic-storage-fixture-v1` cannot supply Korean historical values. The
separately scoped reference-server test is NA, explicitly not Korean content.
No 2000/2001 field has been merged or selected as a default.

The Work receiver reads a pinned commit and explicit ZIP, without executing Work
code. It requires exact previous values, hashes, schema/profile and all declared
source-byte dependencies before adoption. B001 remains DEFERRED with zero adopted
or exercised fields. Its public metadata is not private selected content.

Cache fingerprints require input/parser/converter/config/profile/schema/mapping.
The converter-change regression proves the fingerprint function's behavior. No
actual original-asset rendering cache was rebuilt; that test is blocked with the
missing private inputs. New inputs must create a new manifest generation at a
test boundary, retaining prior results and rerunning affected tests.
