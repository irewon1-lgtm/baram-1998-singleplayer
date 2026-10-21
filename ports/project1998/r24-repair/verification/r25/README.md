# Resume r24 repair

Read `STATE.json` first. The active repair is a dedicated port overlay on branch
`work/project1998-r24-repair-20261021`; do not replace the outer BARAM project.
The base is the delivered r24 ZIP SHA256
`07a0129381b484ec8c34743716efc8ce7f9473d47e2c786845c00c829f9e43e4`.
The retained r24 APK SHA256 is
`5cef47098ca9c3ad6d3cde7e1a720c8d3a5220e0a797270a1fa27e945ce2d5e0`.

Use the source root as the working directory. Set `P1998_TOOLCHAIN` explicitly.
The tested Linux layout has `dotnet/dotnet` SDK9.0.319, shared runtime8.0.32,
Godot4.6 mono in `godot-mono`, local packages in `nuget/feed` and `nuget/packages`,
Android35/build-tools35.0.1 in `android-sdk`, and Android mono templates under
`templates-mono/templates`. Exact official archive URLs/hashes and executed
dependency hashes are in `toolchain/`. Java17 and Python/Pillow are required.
Godot SDK/Sharp4.6.0, BCrypt4.0.3, Sqlite8.0.10, SQLitePCLRaw2.1.6 and MoonSharp2.0.0
remain pinned by the project lock files. Original tests use TestSDK17.11.1,
xUnit2.9.2 and runner2.8.2.

The display wrapper uses Xvfb and its XKB/fonts under the chosen toolchain's
`sysroot`. The executed Ubuntu24.04 setup extracted xvfb, x11-xkb-utils,
libxfont2, libxkbfile1, xfonts-base and xkb-data; its Xvfb expects
`/usr/bin/xkbcomp`. A stale r13 symlink was repaired to the restored executable.
Missing tools produce BLOCKED/NOT_RUN, never a fallback PASS. No device run is implied.

Generate the derived lossless original-pixel pack if applying only the Git overlay:

```bash
python3 verification/r25/pack_character_pixels.py
```

The full source deliverable already includes that pack and `skin-families.json`.
No new images or items are created by extraction. The six skin mappings borrow
five retained native sword animations; they are authored aliases, not recovered
late-version skin originals. Other weapon families keep their previous substitute.

Build and preserve a uniquely named desktop product snapshot, then generate a new fixture:

```bash
python3 verification/r24/build_products.py ATTEMPT
python3 verification/r25/prepare_fixtures.py FIXTURE_ATTEMPT --products evidence/r24/products/ATTEMPT
```

Set `P1998_PROBE_PRODUCT_ROOT` when a different product output root is desired.
The fixture uses normal account creation/authentication and save/reopen for three
ASCII identities. Credentials are synthetic and never imported from user data.
Its semantic inputs are fixed; BCrypt salts, SQLite physical layout and timestamps
are not claimed byte-deterministic. Each generated baseline records its own hashes.
It is explicitly not the missing historical r20 fixture.

One final regression batch:

```bash
python3 verification/r25/run_repair_suite.py FINAL_ATTEMPT --products ABSOLUTE_PRODUCTS --baseline-apk ABSOLUTE_R24_APK
```

The batch records independent categories and continues after a failed category.
Read every result; a completed driver is not a blanket acceptance. Original xUnit
failures remain FAIL and are compared against the unchanged r24 control. Assertions,
source-pixel integrity rows, content IDs and actual play scenarios have separate units.

The final accepted product snapshot is `ordinary-fix001`; final batch `final002`
completed with the 66 inherited unit failures and a backup-fixture rejection.
The latter was traced to the existing isolated death test's deliberately profile-less
account. The test-only item UI harness now uses the original public backup API after
normal stop, before injecting the death fixture. Corrected UI `final002-backup003`
and backup `final002-backup-corrected003` passed on the same frozen product.
No accounts were deleted or product validators weakened. The original FAIL remains
in the batch result; read `REPAIR-QUALIFICATION.json` and `BACKUP-FIXTURE-REVIEW.json`.

Create the APK only after transaction/save safety is verified. Run
`python3 android/build/build_r25.py --help` for explicit paths. Supply the existing
private signing directory separately and `P1998_BASELINE_APK`; never regenerate or
package the key. Use `--keep-sdk-output-copies`. The driver checks frozen sources,
real packaged settings, all data/assets, native SQLite, package/version, alignment
and the retained certificate. Android installation and physical runtime remain
NOT_RUN until actually executed. Do not merge main or publicly deploy.
