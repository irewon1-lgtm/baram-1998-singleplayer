# Native mobile control verification result — 2026-10-15

Player source commit: f248613d6139fc5274bd383ac3ce292aa0a9d67d.
Workflow: https://github.com/irewon1-lgtm/baram-1998-singleplayer/actions/runs/38700525075
This document is a later documentation-only change; neither player binary was rebuilt after validation.

## Observed results

- Android 35 x86_64 emulator, exact signed universal release APK: PASS for native OS-input story, 605.88 seconds, town/NPC/hunting/combat/XP/real drop pickup/skill/return, stationary touch coordinate check, 24 destination replacements and last-goal arrival, no stale route restart, bag/status/menu, Android Back, background resume, replacement install preserving save bytes, and phone/tablet aspect ratios.
- Independent fresh Android emulator, identical APK SHA-256: PASS for OS MotionEvent multi-pointer injection, joystick held while right pointer attacks/uses a skill, releasing the right pointer without ending the left input, outside-button release, no stuck movement after all pointers release, four joystick directions, backgrounding while held then resuming.
- Windows native release EXE built from the same source: PASS for real window/message handling, startup, existing keyboard play, combat/loot/save, fresh-process restore. Four-direction walk/idle/attack screenshots visually inspected. Startup to ready in this runner: 7.64 seconds. Not a test on the user's Windows 11 PC.
- Artifact identity: APK 856300b12442cea015668a01a132ce099178d683bffc9d274313b56f7e8bab0a (203525948 bytes). Windows ZIP 5932ac92d3416705b93a34a160c79cdde2c3f73b5db11ed8e99a2f44b3002c7b (128490407 bytes). Delivered copies retain those hashes.
- Original private runtime assets/content: 943 files byte-preserved. Same package org.irewon.baram.singleplayer and same signing certificate f8cf43158c663e80b3e15aaa82681ea328be009ea900c7c5ea68e8a6ddec608a. App version 0.3.f248613d. No player saves or signing secrets shipped.
- Private artifacts, screenshots, original OS recordings, a 100-second selected-scene video at original speed, verification HTML and hashes were delivered to the user. Public workflow artifacts remain encrypted.

## Measured limits

After restart, 5280 Android emulator frames averaged 83.705753ms; p99 174.316ms; over 50ms 4769; over 100ms 744. Before restart, the mixed capture/travel/combat/menu sample averaged 195.885321ms with p99 1667.283ms. Last Android save measured 831.199ms. These include software rendering, saves and OS/testing overhead. **60FPS was not reached in this environment and physical-device smoothness is not established.**

Same real 4.4MB save, Linux optimization measurement from the prior run: 2487ms to 874ms with byte-identical payload. Previously executed fixed-delta 30/60 movement/attack comparison and source-render collision/input checks are reused supporting evidence, not new native/hardware tests.

## Fixed failures in this resume

57095f8 correctly disabled SceneTree automatic Back quit, but continuity.gd independently received GO_BACK and called save_and_exit after main.gd closed the bag. Native logs showed OnGodotTerminating. The minimal fix gives mobile Back exclusively to main.gd while retaining desktop close/save. The pointer job's sdkmanager PATH failure was fixed by using its explicit runner SDK path. Both failures were retried on f248613d; no failure was promoted to PASS.

## Still not established

- Physical Galaxy phone / Galaxy Tab S10 FE / user Windows 11: NOT_RUN.
- Account/cloud save roundtrip: BLOCKED_PREEXISTING (cloud config absent), preserved independently of UI work.
- Physical audio output: NOT_RUN.
- Original ARM64 APK's pre-fix hardware replay and official public gameplay video timestamps: NOT_RUN / playback unavailable; prior exact-code Linux replay and official gameplay screenshots are documented separately.

Conclusion: native automated functionality verification PASS in the stated environments; no blanket mobile-complete, 60FPS, cloud-continuity or physical Galaxy PASS.
