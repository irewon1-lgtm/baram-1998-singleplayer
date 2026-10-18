# Project1998 S10 FE — P0/P1/P2 and P3

The latest user instruction authorizes **P3 only**. See [the P3 experiment](p3/README.md)
for the in-process C# integration and its separate APK/save namespace. The P2
Galaxy gate remains `NOT_RUN_DEVICE`; P4 has not been started. The material below
is the preserved P0–P2 technology baseline.

Plan: `P1998_S10FE_NATIVE_PORT_V1_20261018`.
Android baseline: `c1f3c5a075fe3ecb1cfb06a57f360e67b9b9798a`.
This isolated technology candidate displays the source city (0), tavern (2)
and rabbit field (4711), with touch/grid movement, original actor frames and
separate Korean local saves. P3 is a separate core probe; full gameplay and warp
traversal remain P4 work.

The public subtree contains adapters, build scripts and tests. It intentionally
requires privately materialized art; no original client archive or APK is stored
in Git. Upstream Project1998 has not granted a redistribution licence. See the
private P0 provenance/rights record; private access is not a redistribution grant.

## Build from the frozen private inputs

Use Godot 4.6 stable, Java 17, Android SDK platform 35/build tools 35.0.1,
and matching Android export templates. Paths below are caller-owned examples.

```bash
python ports/project1998/scripts/convert.py \
  --source /private/Project1998-master \
  --originals /private/originals \
  --ko-source /private/Project1998-KO-candidate \
  --output /private/converted
python ports/project1998/scripts/assemble.py \
  --converted /private/converted \
  --source /private/Project1998-master \
  --font-dir /private/fonts \
  --output /private/runtime
python ports/project1998/scripts/build_android.py \
  --godot /tools/Godot_v4.6-stable_linux.x86_64 \
  --templates /tools/templates --sdk /tools/android-sdk \
  --runtime /private/runtime --private /private/build \
  --output /private/p1998-s10fe-p2-tech.apk
```

The original archives match the official `project1998/dist` manifest. 4.95 map
words use the explicit `Tile533Map.csv` translation into 5.33 tile art. Actors
come directly from the original 4.x archive. Collision keeps 4.x directional
flags, including the source-authored ObjectFlagOverrides; it does not inherit
5.33's altered collision. Original map FILE-layer bytes and all warp rows are
retained; live C# door/quest rules have not been integrated in this P2 app.

`assemble.py` only adds clearly attributed test scene starting points: the source
CharacterFactory entry and existing warp arrivals. It never rewrites a map.

## Installation and status

Install `p1998-s10fe-p2-tech.apk` directly as a separate app. Package:
`com.irewon.baram.project1998.dev`, versionCode 1. Custom desktop data directory:
`project1998_s10fe_p2_20261018`. Android uses that package's private storage.
The APK contains both arm64-v8a and x86_64 and requests no INTERNET permission.

Tap free ground or drag to move; use the map buttons to inspect three original
scenes. Attack is the original basic attack animation only. Local position save,
cancelled touches and background input clearing are included. None of those
means that NPCs, C# combat rules, progression or working exits have been ported.

See `docs/STATE.json` and `docs/RESULTS.md` for exact executed scope, remaining
hardware requirements and the next resumption point.
