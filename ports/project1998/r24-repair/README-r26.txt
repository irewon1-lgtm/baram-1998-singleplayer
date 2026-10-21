Project1998 r26 — active handoff

Read verification/r26/STATE.json first. It is the one active resume state.
The user's replacement stage4 is accumulated-world performance, not BGM.
This is a partial verified repair with a final signed update APK, not a claim
that every entrance or physical-device behavior is now correct.

Final APK: Project1998-r26-final-update-arm64.apk, versionCode30.
SHA256: 0517350d72af71e852fcccd72fb94fe8c5ed6136855e28aba4c35f5c4a04add5
Existing package/certificate/save folder remain unchanged. Code29 was the first
candidate and is superseded. No uninstall/reset or new signing key was used.

Full source/assets are present. Tool archives and original signing material are
not bundled. Use the existing private signing directory. The original r25 tools
were restored under P1998_TOOLCHAIN; pinned setup/hashes are in
verification/r25/toolchain and the baseline build-r25-101 receipts.
See verification/r25/README.md for the existing test/build environment.

Final executed neutral products: evidence/r24/products/growth-final001.
The full regression driver is verification/r25/run_repair_suite.py.
Original xUnit:2065 executed,1999 pass,66 unchanged failures,0 new names/messages.
Final full suite and scoped source/receipt evidence are included; large generated
screenshots, compiled products and synthetic databases are excluded from this ZIP.
Use original sources and verification/r24/build_products.py to regenerate products.
All supplied test credentials belong to isolated synthetic fixtures only.

Replacement stage4:
1. verification/r26/run_growth.py builds/prepares isolated fixtures and performs
   normal host reopen/input/FULL SQLite save on same-map level/history cases.
2. Reuse --seeds for exact before/after states; do not compare different random
   spawn worlds. run_growth_pair.py records fresh-process ABBA comparisons.
3. OfflineSnapshotOptimizationProbe.cs independently mutates every scalar member
   and mutable graph and checks full original JSON equivalence.
4. OfflineContinuityProbe.cs checks stable owners/items/HP/known room correction;
   TotemMenuProbe.cs follows current named options and normal authenticated relog;
   WorldReaderCompatibilityProbe.cs runs with original r25 frozen DLLs.
5. Actual progressed user save and new APK physical install/thermal comparison
   are NOT_RUN; no connected adb device was available.

Navigation and maps:
NavigationProbe.cs compares A* first directions to independent weighted Dijkstra.
run_ui.py tests actual Godot viewport touch -> Main -> Session -> SQLite on a
newly prepared fixture. input008 is final. No test overlay is in the APK.
WorldAudit.cs and WarpSweep.cs are developer-only: all7948 map IDs/10533 effective
warp rows retain separate ledgers. Final host3333 complete roundtrips,7200 reviews
or exclusions; no whole-game/whole-visual/condition-matrix PASS is implied.
Unzip the separate world-ledger ZIP and open map-ledger.html to inspect each row.
The retained all-map contact previews are not human visual correctness review.

Rebuild final APK (source root; unique attempt/output):
P1998_TOOLCHAIN=/path/to/existing/toolchain \
P1998_BASELINE_APK=/path/to/retained-r25.apk \
python android/build/build_r26.py --attempt r26-004 --version-code 30 \
 --workspace /path/to/work --private-signing /path/to/original-signing \
 --staging /path/to/new-staging --output /path/to/new-final.apk \
 --keep-sdk-output-copies --recovered-host

To reproduce content ZIP into an explicit new directory:
python verification/r26/refresh_content.py --output-dir /path/to/new-content
Copy both resulting ZIP/manifest together only for a deliberately new build.
The supplied original frozen content inputs already match the delivered APK.

Stage commit history/patches and final reports are included. The canonical work
branch remains work/project1998-r24-repair-20261021 in the original GitHub repo,
under ports/project1998/r24-repair; main was not merged or deployed publicly.
