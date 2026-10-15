# Rebuild planning entrypoint

## Read before working
1. `docs/rebuild/MASTER_PLAN.md`
2. `docs/rebuild/STATE.json`
3. Actual remote branch/ref and accessible original files for the authorized task.

The user decided on 2026-10-15 to rebuild the game from scratch while preserving and reusing source material and verified components. The former instruction to repair only the existing runtime is superseded FOR THE NEW PROJECT. Existing code branches, original assets, installed builds and saves must remain intact.

Current authorization (user task BARAM_REBUILD_P0P1_001, 2026-10-15) is P0/P1 SOURCE PREPARATION: preserve and inventory originals; inspect source/documentation and archives statically; reconcile requirements, evidence, conflicts and unused materials; prepare the Codex P2 handoff. Small inventory/reference-validation scripts and safe existing static data tools are permitted. No game implementation or repair, original-asset republishing, reference server execution, APK/EXE builds, paid infrastructure, deployment or merging into main is authorized. P2 is a handoff target, not permission to execute it. See STATE authorization_history; the MASTER_PLAN planning-turn authorization is historical.

This branch is `planning/rebuild-20261015`. `main` and existing development/content branches are not the new runtime baseline and must not be reset or overwritten. Do not import old `main.gd` files wholesale. Reuse narrow, verified components only after the plan's compatibility checks.

Preserve these essentials: Korean 1998–2001 experience, user-provided UI references, Windows plus Android phone/tablet, shared rules/content/save format, offline play and same-account sequential continuation, free-only execution, original-versus-reconstructed provenance, no unexecuted PASS.

Progression: broad source inventory and reconciliation → risk prototypes on both platforms → login/creation-to-save playable slice → bulk content import → complete systems/content → full synchronization/update verification → integrated playtests. Source acquisition may proceed in parallel; one owner integrates runtime changes. Do not postpone all runtime validation until the end.

Keep the five user questions and old failure cases in MASTER_PLAN visible. Update STATE with real evidence and next actions at meaningful checkpoints. Reuse prior results only when their input hashes, versions and validation scope still match. Do not promise asynchronous/background progress.


## Current P1.5 execution (2026-10-16)
User task `BARAM_REBUILD_P1_5_001` explicitly authorizes `STEP015_WORK_INSTRUCTIONS.md` sections 0–12. Continue from `docs/rebuild/p1_5/` and STATE; P0/P1 historical records stay unchanged. Static source processing, evidence selection, validator fixes and handoff only. Runtime/reference server/build/deploy/P2 remain unauthorized in this task.
