# Windows startup repair — 2026-10-15 KST

Overall status: **PARTIAL — native Windows 11 execution is NOT_RUN.**
The repaired executable and private player ZIP are prepared for the user's
Windows PC. Linux execution of the same embedded PCK is evidence only for
game initialization, rendering and gameplay on Linux.

## Frozen inputs and source

- Original development branch: `codex/game-core`.
- Latest remote head checked at intake: `c483df8aba6fda0ae2c55340258cde44df18c572`.
- Isolated repair branch: `work/windows-startup-repair-20261015`.
- Exported local source commit: `f0d7408c977bfdce729ad40d2bf51c7901da3bfc`.
- Source ZIP SHA256: `7fe9b59e90410ec6af915797ccbb8e7630855574274c419d00fea0a32895baf2`.
- Existing Godot 4.6.3 Windows engine is reused. No engine upgrade or new Work
  content was mixed in. The pinned exported PE prefix retains the original
  engine code; Godot updates the embedded PCK's PE section offset/size on export.

## Diagnosis and minimal changes

The original embedded Windows PCK, executed by Linux Godot, blocked the main
thread for **66.494 seconds** while preparing the game. The independent phase
probe measured 25.999 seconds constructing tile resources and 34.649 seconds
merging all maps. This reproduces an unresponsive initialization path. It does
not establish whether the user's Windows driver also contributes to the hang.

- Retain all 50,104 tile IDs; create tile regions and TileSet entries only when
  drawn. Verify source hashes, frame order, counts, dimensions and actor bounds.
- Verify files, prepare rules/maps and decode images on owned worker threads.
  Only main-thread code creates GPU textures. Yield between atlas batches.
- Read each immutable shared map/object table once; share equal tile-name
  string storage across cells. No maps, cells, decorations or content are removed.
- Show a Korean loading screen before loading/instantiating the game scene.
- Flush phase/timing/memory logs during startup. Capture process and engine
  logs from a Unicode Windows launcher before Godot initializes.
- Start with ANGLE/Direct3D 11, retaining Godot's native fallback. If startup
  makes no progress for 60 seconds, stop only the owned child process and retry
  native OpenGL once. This launcher behavior is implemented and compiled;
  its actual Windows execution remains NOT_RUN.
- Preserve `%LOCALAPPDATA%\BaramSinglePlayer\saves\v2\character.json`,
  schema 2, content version and original protected-save behavior.

## Executed verification

| Verification | Platform / conditions | Result |
| --- | --- | --- |
| Original embedded-pack startup | Linux Godot 4.6.3, original ZIP bytes | 66.494 s main-thread block reproduced |
| Final first rendered game frame | Linux X11, software OpenGL, final embedded PCK | PASS: 15.808 s; 555 UI frames; max gap 379 ms |
| Full world equality | Every map cell, collision, decoration, spawn, NPC, portal and world field versus merger before string sharing | PASS; 423 maps |
| Normal creation, movement, NPC, real attack/kill/reward, skills, save | Actual Linux X11 window; final embedded PCK, normal input events | PASS; 20 checks |
| Fresh-process restart | Same final PCK; full saved player/world/loot compared | PASS; 5 checks |
| Private input bytes | All private assets/content checked against original manifest | PASS; 943 files / 145,473,744 bytes |
| Existing packaging unit tests | Actual Python execution | PASS; 11 tests |
| Content importer unit tests | Actual Python execution with required jsonschema installed | PASS; 31 tests |
| Launcher compilation / imported libraries | AMD64 GUI PE, strict compiler warnings treated as errors; Windows system DLLs only | PASS for compilation/PE inspection only |
| Windows 11 EXE double click and gameplay | No native Windows environment available | NOT_RUN |

Final X11 static engine memory after the first game frame was 589,909,383
bytes. The immediately preceding repaired build before tile-string sharing
measured 726,952,578 bytes with the same display/runtime probe. This is static
Godot memory, not total process RSS or GPU memory. Timing runs used the same
host but file cache and concurrent host workload differed; they are indicative
Linux observations, not promised Windows timings.

Early environment-only failures were retained in scratch: missing jsonschema,
blocked Unix-domain sockets, and Xvfb's fixed xkbcomp path. The dependency was
installed locally; X11 verification used TCP and a private test-server compiler
path. These changes are outside the delivered game. The final relevant tests
passed; no native Windows PASS is inferred from them.

## User action and remaining condition

Download the new ZIP, choose Extract All, then double-click `바람의나라.exe`.
No code edits, Godot/Python installation or internet connection are required.
Existing saves remain outside the ZIP. If startup fails, the launcher opens the
log folder; the user can return that folder as a ZIP. Native Windows entry,
combat, save and restart must be observed before declaring the Windows repair
complete. Four-job 1–99 playthrough and complete historical restoration were
not part of this startup-repair verification.

## Launcher hardening and source publication

The final launcher source also probes log-file creation and falls back to
LocalAppData when the player folder is not writable. Progress/READY can be
read from captured child stdout if marker writes are restricted, so a played
session is not stopped merely because a marker could not be created. This
last change affects the launcher only; the final embedded game PCK tested
above is unchanged. Native execution of these paths remains NOT_RUN.

CLI Git push had no credential helper in this environment. The connected
repository API published the isolated branch with exact blob readback for
all 20 changed files. API-created commit identifiers differ from local build
commit identifiers; exported local game and launcher commits are retained in
the artifact manifest and FINAL_DELIVERY.json. The public branch contains the
corresponding exact source bytes. Original `codex/game-core` and `main` were
not modified. The ZIP contains 943 unchanged private asset/content files and
no character saves. Final archive CRC plus all manifest member hashes passed.
