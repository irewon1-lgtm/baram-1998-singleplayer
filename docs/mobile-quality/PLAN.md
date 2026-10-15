# Mobile control quality verification contract

Baseline: work/mobile-continuity-20261015, 2bb4ec55fa8ccb347b11d2bf2532ae4d4806b76a. Origin heads queried 2026-10-15. Delivered APK SHA256 8189f0b85a67a67732eaf09cbbbc4449fc884cf5c62a872ef29d39b7fa76beee. Signing certificate SHA256 f8cf43158c663e80b3e15aaa82681ea328be009ea900c7c5ea68e8a6ddec608a. Original worktree and files preserved; isolated worktree used.

1. Baseline: inspect exact package/signature/source; replay five defects and capture actual frames. Exact ARM64 APK replay is NOT_RUN without an ARM64 Android device; same-source replay must be labeled separately.
2. Implement shared render direction mapping, continuous visual position/camera, bounded four-way path commands and mobile overlay controls. Preserve rules, schema, assets and continuity implementation.
3. Execute source checks, actual rendered direction/contact/input regressions, 20 retargets, blocked paths, two-finger cancellation, menu/back/focus, 30/60 speed comparison and >=600 s continuous activity. Collect frame times, long frames, screenshots/video. Emulator != Galaxy. Desktop Linux != Windows.
4. Build signed same-package Android update and Windows package from identified commit, verify delivered hashes and signature. Reproduce test artifact identity. Never mark export-only or synthetic-only as full acceptance.

Required outcomes: full field mobile layout; tap-to-route and contextual interaction with real range checks; correct visible layers/directions; continuous movement; usable combat/menu controls. Any unmet mandatory criterion remains FAIL/BLOCKED/NOT_RUN.

Existing cloud account/HTTPS roundtrip was BLOCKED before this change and is independent of UI acceptance. No new paid services or remote-control prerequisites.

Implementation finding: raw EPF U/R/D/L frames contrasted with stored/input U/L/D/R; all render layers now use one mapping. Original camera advanced immediately to the logical tile, while actor interpolation lagged; both now share visual position. Rapid tap retargeting must preserve touch-down camera coordinates until release (movement continues during a tap). Existing gameplay numeric definitions and assets are unchanged.

Native CI uses public repository standard hosted runners and existing private vault. Private runtime, screenshots and packages are encrypted with AES-GCM before any public Actions artifact upload. No signing key, account token, or original plaintext assets are uploaded publicly. The exact universal ARM64+x86_64 release APK is installed and hashed by Android OS-input tests; Galaxy ARM64 hardware remains separate.
