# Legacy shading regression

CI runs `test_legacy_resources.py`: checks the exact vendor payload, manifest
stamp and package allowlist. It does not certify Blender rendering.

For the actual integration test, run Blender 5.3 with `--background
--factory-startup --python-exit-code 1 --python tools/test_legacy_blender.py --
--fixture <absolute-native-Endfield-scene.blend> --output <scratch-directory>`.
Optionally pass `--deps <preprovisioned-Python-dependencies>`.
The fixture and resulting scenes stay local; never add game assets to Git.

The test registers the actual addon, rebuilds native records, switches all
character materials, checks idempotence and rig/action identity, saves and
reopens, checks that all group references reconstruct, exercises the actual
MaterialBuilder dispatch for new imports, switches back, and unregisters.

Visual scope: the adapter is a pinned old shader implementation, not a guarantee
that an already imported native scene is pixel-identical to an old scene. Lights,
world settings, source geometry, and previously discarded material properties
can differ. In the local Typhoea fixture, the native record omitted the unbound
`_StrokeMap` texture transform which the old record retained. Existing-record
conversion uses shader defaults for absent properties; it never copies settings
from a reference character. A fresh import passes all transforms supplied by
the Statement reader to the legacy shader. Full source-transform retention and
exact image parity require separate verification.
