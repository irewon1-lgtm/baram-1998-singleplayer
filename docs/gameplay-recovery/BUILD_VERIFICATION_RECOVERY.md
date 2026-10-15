# Recovered build and native verification tools

The previous scratch checkout was lost. `windows_ci.py`, `android_ci.py`,
`quality_android_input.py`, `quality_recovery_android.py`, and the Android
pointer checks were reconstructed from the retained baseline and preserved
build requirements. They are a new source revision, not byte-identical copies
of the unavailable previous Python helpers.

## Build inputs and compatibility

- Copy game inputs once into a separate build project; hash that exact snapshot.
  Record both the original copied inputs and the project after platform settings.
  Cache building and verification packs read the frozen copy, not the mutable
  source checkout.
- Validate all private assets/content/licenses against the pinned manifest.
  Check world-cache compiler revision, content release, original world hash and
  binary hash. A cache from another compiler or release must fail.
- Player APK retains `org.irewon.baram.singleplayer` and the existing private key.
  Compare the actual APK signer digest with the certificate derived from that
  key; inspect package identity and the embedded runtime-pack digest.
- Version code is at least `1792054708`, exceeding preserved candidate code
  `1792054707` and delivered f248 code `1792050193`.
- Player packages exclude probe/runner scripts and test canvas helpers. The
  Android verification APK has a separate `.verification` package and uses
  the official debug template, allowing only its isolated test data to be reset.

## Evidence gates

| Surface | Required execution | Result scope |
| --- | --- | --- |
| Windows | Visible EXE smoke, headless EXE smoke, normal-input recovery core, new-process restart | Windows-native only on Windows; Linux embedded-PCK runs remain explicitly non-native |
| Android player APK | Android OS input, novice skill restriction, monster attack/drop, map access, lifecycle and replace-install preservation | Exact signed player APK on emulator; physical Galaxy remains NOT_RUN |
| Android verification APK | Normal gameplay input core, replace install without clearing earned save, second-process restart | Same frozen production game/runtime with separate test-only input pack |
| Android pointers | Actual OS two-pointer injection | Exact player APK; novice empty skill slots must not cast |

Core/restart runs are bounded at 1200 seconds each. All required report checks
must be PASS. FAIL, NOT_RUN and BLOCKED do not satisfy the native archive gate.
Passing these representative paths does not mark the entire game complete.

## Checks executed before native CI

| Check | Status | Evidence |
| --- | --- | --- |
| Python syntax for the five reconstructed files | PASS | `py_compile` |
| Existing Python unit suite | PASS | 70 passed, 1 skipped (71 discovered) |
| Preserved real runtime manifest and file hashes | PASS | 1828 private asset/content/license entries |
| Stale compiler cache rejected | PASS | Isolated temporary cache with wrong compiler revision |
| Matching compiler cache accepted | PASS | Same test cache with matching world/release/hash/revision |
| Game input changed after copy rejected | PASS | Isolated copied source mutation |
| Native Windows/Android execution | NOT_RUN | Requires new native CI result; build success does not satisfy it |
