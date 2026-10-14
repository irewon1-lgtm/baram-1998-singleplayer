# Work final handoff — BARAM_PARALLEL_V1

Branch: `work/content-import`.
Base game: `dev/codex-asset-runtime-20261014` at `dea6574c9a69ebb04432d10fc32951aacd8b66cb`.
Last verified remote data commit: `d318098bce3c2923516a8b83ad5e2d1fe53d055e`.
The following index commit registers that fixed data SHA; its own SHA is read from
GitHub refs and reported after publication, never inserted recursively here.

Packages: `HANDOFF_INDEX.json` (single source of batch commits/status/manifest paths).
Both packages are READY_FOR_CODEX data, not IMPORTED or PLAY_VERIFIED.

## Produced and validated

- Shared: 992 asset definitions, 74,079 original frame indices including reused
  v125 atlases; 250 PNGs and 163 WAV definitions in the pinned private bundle.
  66,049 KR491 frame rectangles validated; 327 model representative images
  directly reviewed across three contact sheets, not all animations.
- Content: 1,887 records; 1,503 existing IDs conditionally enriched, 384 additions.
  11,253 null fields proposed; squirrel raw mean XP7.5 has a guarded integer8 fix.
  Item535 / monster269 / NPC59 / skill199 / growth401 / advancement12 /
  map64 / shop38 / quest33 / class5 (4 playable+novice phase) / drop_group269 /
  economy1 / optional enhancement1 / recipe1.
- Map64 is 63 physical definitions plus one retained source-name alias. The
  layouts have 60 distinct source hashes, 88,488 tile placements, 269 spawn
  points, 45 NPC placements and 124 authored portals. Geometry is original
  NA495 replacement, not historically verified Korean1998 geography.
- Work validation: PASS for envelope/required fields, two-pass references,
  probabilities, field guards, quest graph, four1–99 tables, source layouts,
  bounds/solid collisions/entry-component reachability and manifests. Directional
  collision rendering still requires the Codex capability; Work has not played.
- Generation checks9 PASS: existing ID reuse, rounding including negative ties,
  rare ratio precision, duplicate-source exclusion, unit mismatch rejection,
  record-order independence, non-null preservation and authorized mean repair.
- Remote readback: 192 package files compared byte-for-byte, mismatches0.
  Source/game changes outside content-work:0.

## Errors and unused work

`catalog/asset-errors.json`, `unused-assets.json`, `source-map-index.json` and
`source-inventory.json` are the structured ledgers; no duplicate ledger here.
49 EPF inputs are unsupported/empty, and9 original effect sequences were
quarantined. Successful independent asset sheets are in the shared package.
937 asset definitions have no current content role;48 are directly referenced,
7 are supporting sheets. These are definitions, not distinct picture counts.
NA466 static extraction, v125 motion semantics and unselected source-map roles
remain unresolved. Source originals are preserved; do not repeat full extraction.

Observed source failures: strict wide EPF stencil parsing; empty bow/line001;
zero-delay/empty original effects. Repair only affected decoder branches or use
existing source alternatives with inference labels; do not change game code here.
Transient own failures: PNG9 checksum errors repaired from identical source RGBA;
one failed upload replaced from an atomic final ZIP; patch-context mistakes
corrected before publication. Evidence is kept privately under drafts; no FAIL is
relabelled gameplay PASS. Content bundle shares object tables once (219,203bytes).

## Recipient and next action

Codex receipts were only work-start and synthetic importer-tests at observed
`6a2fd1f…`; no receipt matches these fixed package commits. Thus actual private
bundle acquisition, import and gameplay are NOT_RUN. `CODEX_IMPORT_NOTES.json`
records the required JSONL, size_bytes, package-local schema, guarded absence,
kind and private acquisition adaptations. Codex must implement its importer and
handlers; Work never edits integration or game files to resolve that.

Next Work task is a new correction batch only after a matching data-error receipt,
or justified assignment of existing unused source models/regions. Keep package
IDs immutable and content IDs permanent. On interruption resume from the pinned
index and affected ledger row; do not rebuild good packages or start over.
Main, existing development/research branches, original inputs, game canon,
saves, common ID registry, CI and deployment configuration were preserved.
