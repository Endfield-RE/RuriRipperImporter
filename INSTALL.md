# Blender 5.3 installation (Windows x64)

1. Install Blender 5.3 or newer and Microsoft .NET 10 SDK x64 (includes the
   .NET and ASP.NET Core runtimes required by the backend). Our regression host
   is Blender 5.3 Alpha; other builds need their own compatibility checks.
2. Open this repository's **Actions > Package Blender Add-on**, choose a successful
   run and download **RuriRipperImporter-Blender53** from Artifacts. Sign in to
   GitHub to download artifacts. Extract that download once: it contains the
   installable `RuriRipperImporter-Blender53.zip` and `SHA256SUMS.txt`.
3. In Blender: **Edit > Preferences > Add-ons > dropdown > Install from Disk**.
   Select the inner add-on ZIP and enable **RuriRipperImporter**. Its package root
   is already named correctly; no manual rename or Git clone is needed.
4. On first enable the plugin attempts to install its Python dependencies into
   its own workspace. Keep internet access available and inspect the console for
   dependency errors. Initial offline installation requires pre-provisioned wheels.
5. Obtain a compatible backend separately and extract it outside the add-on.
   Set **Ruri-RipperHook Bin Dir** in the add-on preferences to the directory
   directly containing `Ruri.RipperHook.dll` and
   `Ruri.RipperHook.CLI.runtimeconfig.json`. Preserve all sibling dependencies.
   Save preferences and restart Blender after changing backend versions.
6. Open the 3D Viewport sidebar with **N**, select **RuriRipper**, then **Assets >
   Add Install**, choose Game Root and build/load the resource index. Import a
   character before applying animation with **Play On Rig**. Old RCM6 indices
   should be rebuilt for this Statement backend rather than reused as RCM7.

## Optional Endfield legacy character shading

In Blender 5.3, open **N > RuriRipper > Endfield Shader Compatibility**.
Choose **Legacy 5.2 Compatible**. Subsequent character imports use the pinned
legacy shader; for characters already in the scene, click **Apply Mode to Scene
Characters**. Choose **Native 5.3** and apply again to return to current shading.
The choice is saved per scene, not globally in Blender preferences.

This changes character materials and their generated outline/vertex modifiers,
not meshes, armatures, animation curves or backend decoding. Original geometry
and animation imports remain on the Statement architecture. The existing
character-material bindings are replaced, including other users of shared
materials; save a scene copy before applying. Native mode remains the default.
Scene shaders and post-processing remain native. This is not Blender 5.2 support.
Lighting/world settings are retained: matching the old look also requires
matching its lighting; this option does not delete user lamps or choose an HDRI.

## Which backend?

- The public backend repository's **Build Hooks** workflow emits
  **RipperHook-PureRelease** (and a separate FModel artifact). PureRelease excludes
  private game adapters. It is not the Endfield-enabled backend.
- Endfield support requires access to `KawakazeNotFound/Endfield-GameHook`, or a
  separately supplied compatible private runtime. Its **Package Verified Runtime**
  workflow emits **Endfield-Statement-Runtime-Windows-x64**, containing
  `Endfield-Statement-Runtime.zip`. Extract that inner ZIP and select its
  `statement-runtime` folder as Bin Dir. This packages the verified snapshot;
  it is not a fresh source rebuild. `runtime` is the legacy ABI, not this version.
- Public frontend packages never contain backend binaries, private sources or
  game test fixtures. Private artifacts stay in the private repository.

Actions checks packaging/build boundaries. It does not replace a full Blender
GUI/material/all-animation regression. The validated animation case is raw
Attack01, 556 bones, 301 frames at 60 fps with no missing reference paths.
