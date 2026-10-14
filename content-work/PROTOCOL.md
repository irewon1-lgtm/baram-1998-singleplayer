# BARAM_PARALLEL_V1 · schema 1

Producer Work, base `dev/codex-asset-runtime-20261014` at
`dea6574c9a69ebb04432d10fc32951aacd8b66cb`. Only `content-work/**` is writable.
Packages are immutable; `HANDOFF_INDEX.json` pins the package commit and manifest.
Importers read all IDs first, then resolve references. A dependency pins both its
commit and manifest SHA-256. `READY_FOR_CODEX` means data readiness only.

Each JSONL line follows `schemas/content-v1.json`. New definitions use persisted
`wk.<kind>.*` IDs. Existing definitions use a Work proposal ID, `target_id`, and
field guards. The effective reference ID of a proposal is **target_id**. An
importer must reject a changed guard and report a conflict; it must not silently
overwrite Codex changes. A proposal's `data` is a complete declarative definition
for the importer; it does not replace an existing file. `changes` are the exact
conditional changes to existing fields. `runtime_definition` is a new optional
field proposed on an existing numeric record. Existing `values` are preserved
unless an explicit guarded change appears.

Kinds: asset, item, monster, map, npc, shop, skill, quest, growth, class,
advancement, drop_group, enhancement, recipe, economy. References carry role,
target ID, and an optional selector (e.g. a frame index in an asset sheet).
Frame IDs are indices within a pinned asset definition, not invented item IDs.
Map/NPC/spawn placement IDs identify definitions; runtime instances are Codex's.

Coordinates: zero-based x right, y down; origin top-left; tile 24px. Body/weapon
frames use original EPF foot offsets and directions N,W,S,E. Motion inferred from
existing bindings remains marked inferred. Original effect front/back order,
palette, per-frame delay and repetition limits are kept separately.

Numerics: gold integer; HP/MP/XP integer; durations milliseconds; distances tiles.
Decimal arithmetic, ROUND_HALF_UP (ties away from zero) for averaged integers.
Only distinct same-unit same-condition observations enter means. Alpha/stencil
and transparent palette entries are never averaged. Ratios use `{numerator,
denominator}`; weights are a separate field. Independent rolls need not sum to
one. Exclusive outcomes including no-drop must sum to the declared denominator.

ORIGINAL is source data, AVERAGED is a source mean, DERIVED is deterministic
conversion, INFERRED is authored completion. Field rules override the record
mode where provenance is mixed. Historical identity is not implied by an asset's
successful decoding. Authored quests and enhancement rules are extensions.

Original pixels/layouts remain private. An asset can refer to a hash-pinned
private bundle or source with a deterministic converter. SHA-256, size, member
paths, Library identity and access requirements are acquisition data; Library
access in Work does not prove acquisition in Codex. Recipient acquisition and
game execution stay NOT_RUN until a receipt for the exact batch/commit exists.

Run commands and observed results live in package `validation.json`. Frozen
package files, schema/tool copies and private-bundle receipts are hashed by the
manifest. A manifest omits itself to avoid recursive hashes. Its commit is
registered only in the following index commit. Full originals are not copied
into each package. All failures are recorded with field, value and rule.
