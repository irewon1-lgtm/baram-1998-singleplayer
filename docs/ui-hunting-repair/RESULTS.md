# UI / beginner route repair checkpoint

Player source: `05bde481055ad1af3fc26ef56fecfecdd656425c`

Branch: `work/ui-hunting-repair-20261015`. Player code is frozen at the SHA above. Later commits contain CI tools and this report only. Existing main, other work branches, original assets, immutable content releases and save IDs were preserved.

## Result

Overall: **BLOCKED**. Android APK and Windows ZIP candidates were produced; native execution was not established. Candidate filenames deliberately say `candidate`. No native PASS is claimed.

Executed the final Windows EXE embedded game PCK using Godot 4.6.3 on Linux X11/llvmpipe with real input paths:

- PASS: fresh level 1, four persistent tabs, actual owned icon references, Korean map and exit names, normal touch exit from town to field and back, ordinary rabbit/squirrel combat, 47 kills, real drops, natural level 2, save. Existing earned quests subsequently reached level 5.
- PASS: earned-gold purchases and sidebar equip, replace, remove, shared combat stats; body/head slot state. Unidentified head overlays are not an appearance PASS.
- FAIL then PASS: initial compass learning failed with 8 acorns where 10 are required. Three more ordinary kills earned the missing materials. Real trainer learning then consumed the required materials and 100 gold; four directions used 2 MP each without stale input. Failure evidence retained.
- PASS: fresh-process restore retains real equipment, items and learned compass. A separate earlier verified build save copy retained character/progress/skills/position while migrating 45 misplaced novice variants.
- PASS: rendered phone/tablet landscape aspect ratios and folding in Linux. This is not Galaxy testing.

Windows native: BLOCKED. Local Wine could not create its socket. Android emulator: BLOCKED; no KVM, package service was unavailable, APK install did not run. Free native CI failed before any job steps; exact cause UNKNOWN. Physical Galaxy phone, Tab S10 FE and user Windows 11: NOT_RUN.

## Preserved data and remaining scope

The two packages share player source tree, active release, repaired world and save format 2. WK-ASSETS-001..003 and WK-CONTENT-001..010 remain imported and active, distinct from whole-content play verification. Ordinary beginner spawn sets were checked on four maps; only the town/field route was played end to end. Relocated variants retain IDs and stats.

678 icon references are renderable, but many identity mappings remain inferred/replacements. 78 head/accessory overlays remain unidentified and are listed in the delivered evidence report. Do not claim all item pictures or worn appearances exact. Learned attack skill end-to-end, all walk portals, simultaneous native touch, keyboard regression and controlled performance comparison remain NOT_RUN.

Android package and original signing certificate are retained and versionCode increased to 1792064591. Static update compatibility PASS; actual old-APK update/save test NOT_RUN. Never recommend uninstall/data-clear to update. Windows uses the existing LOCALAPPDATA BaramSinglePlayer save folder. No user saves or signing material are included. Cloud account sync remains unconfigured.

## Build identifiers

- active_content_sha256: `cd0c680ab5fc8fb223ef2d14ff0b991b18e3e100fecba693bd608040f8a66e57`
- world_repairs_sha256: `2f0314a96e08e842432aa15764626644f47b811ecb84d4cab0d2d52332634844`
- shared_world_cache_sha256: `9bbe116b0927acb383f309cf1f459d1fd3eeb37b4c773e6625fb6956d7c2d75c`
- windows_exe_sha256: `ec4a8c1e7c3117002dc15df3c914b06536d6f274a4a6ca396125f9ce684b1bbc`

| Candidate / evidence | Bytes | SHA256 |
|---|---:|---|
| baram-Android-05bde481-candidate.apk | 283684954 | `cce2c4d1c2ed349c05bf25ac99e4b00801e906364e86cd3ca4b5d833668875e1` |
| baram-Windows64-05bde481-candidate.zip | 175942336 | `b40b1c4c9d27ae9264d987d595a7070fd8336f5f5c5fd69d42f478a178cb7f43` |
| baram-verification-05bde481.html | 3051580 | `7473cbaf9e8bc7a547ea29ed1fa3048cd37c6074d025b3b5644b94d812c7fd50` |
| baram-evidence-05bde481.zip | 10584410 | `c95648025c435a36636f1d4666021a2e35a8d992c81bb1348fe51aebc2ed623d` |

## Resume

Keep the player SHA and content/cache hashes above. First resolve native CI job-start failure or use an available free native execution environment. Execute these exact APK/EXE candidates, old-app update/save preservation, learned attack skills and native multi-touch/keyboard checks with device-specific screenshots/logs. Identify missing original item/equipment frames before extending mappings. Do not repeat completed Linux flows as a substitute for missing native evidence. Do not use paid resources.
