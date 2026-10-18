# Project1998 Android port

This subtree follows user plan `P1998_S10FE_NATIVE_PORT_V1_20261018`.
The P6 stage instruction on 2026-10-18 was “6단계 진행해”, following
the completed P5 increment in this conversation. It authorizes P6 Korean
display/mobile UI/quality from P5 HEAD cda6fe275dd2e41635a5fd20def137d3bd57c115.
The independently requested
V2 G0–G8 review document is not an instruction to reset/restart this work.
Keep P5's finite 47-map starting region and exact capsule/save identity.
Translate display text only; retain native keys, menu indices and shop reply
values. Korean names are aliases, not changes to original Character.Name.
Separate application/glyph checks from semantic/era review and real execution.
The latest user instruction reports six actual P6 Android defects: full-screen
translucent controls without D-pad, pickup crouch, smooth mobs, a real map,
optional tutorial bypass to main play, and four original parchment windows.
Follow docs/P6_REPAIR_CONTRACT.json on branch
work/project1998-s10fe-p6-repair-20261018. The explicit tutorial-bypass request
authorizes its narrow offline stage/location transition while retaining earned
character data. It does not authorize general rule changes or free rewards.
Do not claim a full-world port.
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
