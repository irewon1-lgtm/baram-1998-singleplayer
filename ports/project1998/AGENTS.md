# Project1998 Android port

This subtree follows user plan `P1998_S10FE_NATIVE_PORT_V1_20261018`.
The latest user instruction on 2026-10-18 is “P4진행해” and authorizes the P4
vertical slice from the current P3 integration. This supersedes the older
P3-only restriction and sequencing gate; it does not turn unexecuted device
checks into PASS. Do not start P5 or import the full world.
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
