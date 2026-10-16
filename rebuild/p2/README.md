# P2 inspection project

This is one isolated technical inspection app, not P3 or an installed-game update.
It contains no original map, sprite, sound, icon, font, account or user save.
Missing original inputs are visible; no substitute art or historical defaults are generated.

Candidate engine: Godot 4.6.3 official, GDScript, compatibility renderer. Final
Windows/Android engine and export decision remains provisional until both are run.

From this directory:

```sh
godot --headless --path . --editor --import --quit
BARAM_P2_REPORT=/workspace/p2-private/linux-ui.json godot --headless --path . -- --p2-smoke
```

UI, input adapter, shared state, rendering and storage are separate modules.
The four panels and bottom status are a structural inspection, not a reproduction
of the unavailable user photos. Direct Unicode injection and synthetic input are
reported separately from physical keyboard, touch and native IME.

The app's custom user directory is `baram_rebuild_p2_001`; Android uses a separate
package ID. All destructive tests use fresh synthetic save paths outside the checkout.
