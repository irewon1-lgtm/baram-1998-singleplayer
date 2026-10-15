# PC / Android continuity acceptance — 2026-10-15

Baseline: codex/game-core be0b454; existing Windows recovery / private runtime and all content retained. No main/content branch edits. Add only touch input, single-account save continuity and Android CI.

Required order:
1. Run existing source regression + parse changed Godot scripts. PASS requires actual exit 0 and no SCRIPT ERROR.
2. Run real PostgreSQL migration/RPC tests with auth.uid identities: exclusive device, CAS/replay, lost response, offline lease, previous backup, user isolation, invalid checksum and future version unchanged. Mock HTTP alone is not cloud deployment PASS.
3. Run local journal tests: original PC byte-for-byte copy, remote validation before write, pending/conflict preservation, restart/resume, update refusal. No secrets or user saves in artifacts.
4. Build original-content Windows and Android from the same commit/content manifest. Keep private originals exactly. Exclude development probes/tests from player packages; generate test packages separately.
5. On Windows native EXE perform existing game regression and create/save. On Android emulator install same-code APK, load, change progress using live game input, save. Fresh Windows process must load Android's changed save. Expected real cloud version increments, same character and no stale overwrite. Record actual sizes, cold startup and RSS; no estimate labelled measured.
6. Release only after required automated checks pass, to the existing private vault. Galaxy phone/S10 FE operator tests remain NOT_RUN unless observed. GUI automation/emulator is not Galaxy hardware.

Backend: one Supabase project (Auth + PostgreSQL RPC), one email/password login; first login creates account in same screen. Public config has URL/publishable key only. Player passwords never logged or saved. Session tokens only in private OS user/app data; no service-role/admin credentials in packages/Git.

One active device lease persists through offline/force-stop, recovered by same device. No automatic timeout takeover. Save only locally every 30 seconds and on suspend/focus loss; network upload only save-and-exit, plus opening version check. Previous cloud document is replaced by last validated document atomically with CAS. Conflicts preserve both local and cloud documents and block play/overwrite. No automatic merge. No new launcher, patcher, realtime, social, billing or content work.

Current actual Galaxy tests: BLOCKED_NO_ATTACHED_DEVICE.
