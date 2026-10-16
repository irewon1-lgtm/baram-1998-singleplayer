# P2 synthetic storage validation

`save_store.gd` is a shared GDScript storage module for the single P2 inspection project. This is a new fixture schema, not a historical Baram save format or an existing-save migration. Source and requirement provenance is in `PROVENANCE.json`. Every test uses newly generated local identities, Korean text, inventory, equipment, skills, positions and loot; it has no original asset dependency.

API:

- `validate(state, expected_owner, catalog)` returns a status dictionary.
- `encode(state)` / `decode(text, expected_owner, catalog)` provide canonical JSON and integrity checking. Use `validate` before calling the encoder directly.
- `read_state(path, expected_owner, catalog)` returns `OK` or `RECOVERED_BACKUP` with `state` and `source`, or an explicit failure. A read never repairs files.
- `write_state(path, state, expected_owner, catalog, fault_phase = "")` returns `SAVED` or an explicit failure. All metadata plus payload are covered by SHA-256; the digest field excludes itself. Wrong owners, unknown content, deferred maps and future schemas cannot overwrite an existing primary.
- `plan_map_update(state, expected_owner, old_catalog, target_catalog)` returns `READY` with a new state only when each character/loot coordinate remains valid on its same stable map. Otherwise it returns `DEFERRED` with an untouched source copy. Nothing is teleported or discarded.

The catalog supplies the profile/manifest fingerprint, known stable item/skill IDs, equipment slots and map versions/dimensions/collision cells. It must itself be validated by its caller. A local owner ID check does not authenticate an online account. Coordinate migration tables, legacy formats and server synchronization remain separate contracts.

The writer checks an existing backup even when the primary is absent. A backup from another owner, a future schema or an unsupported content profile blocks writing and remains intact. Pre-existing symlinks in the primary, sidecars or ancestor directories are refused before reading, writing or replacement. Use an app-owned directory: Godot's API does not provide exclusive/no-follow file opens, so this guard does not establish protection against a concurrent process swapping filesystem entries or hardlinks.

On Android, the absolute-path filesystem provider lacks symlink operations. `native_directory(path)` opens `user://` first and retains its native USERDATA backend while changing to the absolute directory. The guard and link fixtures use this route so actual links remain detectable when the suite receives an absolute fixture root. Keep each suite run in a distinct directory to preserve earlier evidence and the absent-file preconditions.

`save_self_test.gd` exposes `run(output_directory, optional_child_runner) -> Dictionary`. The inspection app can run it in its separate `user://` fixture directory on each platform. Without a child process runner the process kill/restart checks are recorded as `NOT_RUN`, while the same file/schema/fault/recovery/map tests execute. The full Linux runner is:

```sh
godot --headless --path rebuild/p2 --script /workspace/baram-p2-codex/tools/rebuild/p2/test_save.gd -- --root /workspace/p2-private/save-tests
```

The tool runner starts actual child Godot processes, kills them at seven storage boundaries, and verifies recovery in fresh processes. It exits with the exact failed check count, or zero. Preserve previous evidence by selecting a new output directory for a new run. Tests with no process driver are available with `--local-only` after the output arguments.

Evidence write/flush/readback failures count as failed checks before the returned summary and exit code are finalized. A regression creates a directory at the `results.json` destination and verifies `FAIL` with a nonzero failure count. Symlink creation unavailable on a target platform is recorded as `NOT_RUN` for those cases.

File flush and same-directory rename are the tested mechanism. Passing these tests does not prove durability after physical power loss, controller cache loss or every filesystem. Each target OS/app build needs its own execution receipt; Linux results cannot establish Windows, Android or Galaxy results. Existing installed apps, signing keys and real saves are outside this module's test paths.
