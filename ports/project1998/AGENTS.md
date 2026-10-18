# Project1998 Android port

This subtree follows user plan `P1998_S10FE_NATIVE_PORT_V1_20261018`.
The latest user instruction on 2026-10-18 is “5단계 진행해”, following
“P4진행해” in this conversation. It authorizes the existing plan's P5 incremental
content integration from the completed P4 branch. The independently requested
V2 G0–G8 review document is not an instruction to reset/restart this work.
P5 first expands the original starting region; record its finite denominator,
source boundaries and untested areas. Do not claim a full-world port.
Prior Android/Galaxy checks remain unexecuted unless new device evidence exists.
Keep this separate from the existing Baram r16 game, package, saves and state.
The port's checkpoint is `docs/STATE.json`; do not replace the Baram plan/state.

Original DATs, client binaries, converted art, fonts, APKs and signing keys stay
outside the public checkout. The compiler accepts private source paths and pins
the official inputs. Preserve raw map words, IDs, flags, coordinates and warps.
Do not erase buildings or create substitute art to conceal conversion failures.

Use explicit statuses. A signed APK is BUILD_PASS; Linux or Android emulator
execution is not Galaxy hardware verification. The P2 device gate requires an
actual Galaxy Tab S10 FE, offline touch movement and measured minimum 30 FPS.
Until that evidence exists, retain `NOT_RUN_DEVICE`. Report P3 host, Android
build, Android runtime and physical-device evidence separately.
