# P3 remediation affected verification

App behavior commit: `38c6e9ee536c251dc85fe8c5b76344ac9da1dbff`.
Use Godot **4.6.3** with the final Windows EXE as `--main-pack`; this reads the actual exported resources. Running that pack with Linux Godot is explicitly **not native Windows execution**. This task's clean ZIP extraction was tested that way.

For a headless contract run, set `BARAM_CONTRACT_REPORT` to a new report path, optionally set `BARAM_REPAIR_OLD_SAVE` to a **read-only** copied legacy save, and run:

```sh
Godot_v4.6.3-stable_linux.x86_64 --headless --main-pack /absolute/baram-p3-playable.exe --script /absolute/tools/rebuild/p3/test_contract.gd
```

GUI scripts `test_remediation.gd`, `test_bindings.gd`, and `test_layout.gd` use a real Godot viewport and `InputEvent` injection. They need a display, Korean font, and writable isolated user-data directory; set `BARAM_REPAIR_EVIDENCE` to an existing directory. Distinguish explicitly positioned combat/job fixtures from naturally earned progress. The export uses user directory `baram_rebuild_p3repair_001`; never point tests at an existing user's save directory.

`test_live_journey.gd` records the first 600-second automatic GUI attempt. Its original FAIL remains in the evidence: the operator requested a south-field route from inside the guild instead of first leaving to the city, and its final comparison sampled state before the save click's normal simulation frames. `test_live_resume.gd` is the corrected 420-second continuation of the actual earned character, with no progress grants. `test_final_continue.gd` verifies a separate process's ordinary menu load and records return/save/menu/selection/continue. These last two scripts name this task's synthetic character deliberately; they are evidence drivers, not general production auto-play or manual platform certification.

`export_repair.py` calls the preserved P3 exporter and changes only the new parallel package/version/user directory. Required arguments: `--target Android|Windows --project PATH --runtime GEN001_PATH --godot EXE --templates PATH --output NEW_FOLDER --source-commit SHA`. Android also needs `--android-sdk`, `--java-home`, and a **new private** `--signing-root`. Reuse this task's private synthetic signing identity for future updates to this candidate, never substitute the old app's key. Validate actual source/runtime hashes in the export receipt; `--source-commit` is a provenance label and does not replace hash comparison.

Private input: `WORK-GAMEPLAY-GEN001`, ZIP SHA256 `b97c533e5b979abc4d68470314b37e012898c97c450515c9b9364644c9543461`, Library file ID recorded in the source package and delivery records. Assets and signing material are excluded from git. APK package `com.irewon.baram.p3repair20261016`, version `0.1.1-p3-repair` / code2. The previous Android key was unavailable; automatic old-app save migration is not claimed.

Do not repeat the old identical 99 natural/83 storage/131 engine suites. The storage parsers, private inputs and converters have not changed. Re-run only dependent verification after new code changes, and always exercise the exact final delivery binaries. Actual Galaxy, OS Korean IME, physical listening, native Windows and original map geometry remain independent gates in `docs/rebuild/p3-remediation/`.

Final touch repair: native ScreenTouch action callbacks allow the second finger to attack while the first holds movement; their emulated mouse copies are suppressed. `test_input_edges.gd` covers 13 affected cases. `test_final_journey.gd` performs a new 420-second fresh-character journey on the final rebuilt PCK. `test_pack_parity.gd` compares actual compiled scripts and private input manifests in the APK ZIP against the Windows embedded PCK (11 byte equalities); this is not Android execution.
