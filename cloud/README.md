# Single-service continuity (deployment pending)

The game uses one Supabase project for email/password Auth and PostgreSQL RPC.
No always-on game server, realtime subscription, object-storage SDK, launcher,
patcher, chat, friend list or dashboard is added. Passwords are never logged or
persisted; only the player's rotating runtime session is stored in OS-private
application data. Android user-data backup is disabled by the export default.

## Required deployment, to be done by the agent after connection

1. Confirm Supabase connection and a **Free** project. Do not enable paid
   compute, billing, SMTP or subscriptions. Do not reuse an unrelated app DB.
2. Apply `migrations/20261015020000_continuity.sql` once through the connected
   service. `baram_private.saves` is not directly exposed; all writes go through
   three authenticated, row-locked functions. RLS is enabled and direct grants
   are revoked. Do not edit this migration after actual deployment.
3. Enable only email/password login, same-screen first-login account creation,
   password minimum 10. Disable email-confirmation for this private game so the
   single login screen does not depend on sending emails/SMTP. The email is a
   login identifier here; this does **not** prove ownership of that mailbox.
4. Obtain **only** project URL + public publishable/anon key and write
   `game/data/cloud_public.json` with exactly `url` and `public_key`.
   `tools/android_ci.public_config()` rejects service-role/admin keys. Never put
   service keys, account passwords or test credentials in a player package.
5. Create an isolated CI test account (not the player's real account), keep its
   credentials only in the existing private vault, and test real Auth + RPC
   using the game client's HTTP methods. Do not mark PostgreSQL `auth.uid()`
   claim fixtures as deployed-auth validation.
6. Complete the **real HTTPS** PC save → Android load/play/save → fresh PC
   restore with matching character and changed progress. Use original assets
   privately, test lost connection/stale version/future-version refusal, and
   observe the actual save-and-exit path. The existing emulator file-transfer
   fixture test is a different, narrower test and is not sufficient.
7. Only then merge draft PR and integrate private Android/Windows publication
   gates. Keep previous Windows releases untouched; do not publish an
   unconfigured APK as a working cloud-continuity release.

No project, production schema or real player account has been provisioned yet.
Connection is the current external prerequisite. The Android signing identity
is already saved only in `baram-windows-private/android/android-signing.json`;
reuse it for later APK updates. Never print it or commit it to the public repo.

## Protocol

`POST /auth/v1/token?grant_type=password` (first login may use `/signup`), then
`/token?grant_type=refresh_token`. Password is cleared after login.

Authenticated `POST /rest/v1/rpc/baram_open` takes `p_device` UUID and
`p_compatibility` (`schema2:<content release hash>`). It returns current version,
document and last request, or BUSY / UPDATE_REQUIRED. Device leases have no
automatic expiry; an offline device resumes and syncs before another can play.

`baram_push` takes the same device/compatibility, base version, request UUID,
exact schema2 document and release flag. Under one row lock it validates the
checksum/state, compares the version/lease, moves current to previous backup,
writes the new document, increments version and releases the device. A replay
of the last exact request returns its previous acknowledgement. Stale writes
return CONFLICT and the current document; the client preserves both snapshots
and blocks further account writes. There is no automatic merge/overwrite UI.

`baram_release_empty` releases only a still-empty account's own device lease.
Compatibility changes require explicit reviewed migration; never advance the
server compatibility string merely to make an old save pass a test.

## Actual evidence so far

- PostgreSQL transaction tests exercise real PostgreSQL, including concurrent
  clients; their JWT claim context is local CI fixture data.
- Godot local journal tests run on Linux and Windows.
- Native Android CI tests are separately labeled file transport, not cloud.
- All Galaxy phone / Galaxy Tab S10 FE operator checks remain NOT_RUN.
- The source content branch has 13 packages, while the current private runtime
  snapshot records 6 imports. Both are preserved; no 13-import claim is made.
