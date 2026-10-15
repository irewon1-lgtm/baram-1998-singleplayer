# Rebuild planning entrypoint

## Read before working
1. `docs/rebuild/MASTER_PLAN.md`
2. `docs/rebuild/STATE.json`
3. Actual remote branch/ref and accessible original files for the authorized task.

The user decided on 2026-10-15 to rebuild the game from scratch while preserving and reusing source material and verified components. The former instruction to repair only the existing runtime is superseded FOR THE NEW PROJECT. Existing code branches, original assets, installed builds and saves must remain intact.

Current authorization is PLANNING AND RECORDING ONLY. No game implementation, asset republishing, server execution, paid infrastructure, deployment or merging into main has been authorized by this planning turn. A later explicit user instruction may advance the task; record that instruction in STATE rather than claiming the current document already authorizes execution.

This branch is `planning/rebuild-20261015`. `main` and existing development/content branches are not the new runtime baseline and must not be reset or overwritten. Do not import old `main.gd` files wholesale. Reuse narrow, verified components only after the plan's compatibility checks.

Preserve these essentials: Korean 1998–2001 experience, user-provided UI references, Windows plus Android phone/tablet, shared rules/content/save format, offline play and same-account sequential continuation, free-only execution, original-versus-reconstructed provenance, no unexecuted PASS.

Progression: broad source inventory and reconciliation → risk prototypes on both platforms → login/creation-to-save playable slice → bulk content import → complete systems/content → full synchronization/update verification → integrated playtests. Source acquisition may proceed in parallel; one owner integrates runtime changes. Do not postpone all runtime validation until the end.

Keep the five user questions and old failure cases in MASTER_PLAN visible. Update STATE with real evidence and next actions at meaningful checkpoints. Reuse prior results only when their input hashes, versions and validation scope still match. Do not promise asynchronous/background progress.
