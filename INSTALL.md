# Blender 5.2 legacy install

Use branch `codex/blender-5.2`, tested with Blender 5.2.2 LTS on Windows x64.
Do not mix this frontend with the Statement/Blender 5.3 backend.

1. Download the **RuriRipperImporter-Blender-5.2** Actions artifact from this branch.
2. Extract the outer Actions download; install the inner
   `RuriRipperImporter-Blender-5.2.zip` in Blender Preferences > Add-ons.
3. Endfield support is a separate **private** download from the
   `KawakazeNotFound/Endfield-GameHook` repository's same branch:
   **RuriHookBin-Blender-5.2-Windows-x64**.
4. Extract its inner `RuriHookBin-Blender-5.2-Windows-x64.zip` and set the addon's
   backend Bin Dir to its `RuriHookBin`
   directory, containing the accepted legacy `Ruri.RipperHook.dll`.
   SHA256: `9F9355D95C5FF7015399128DE1444345712E7799ADE4AD248B34D45B505C1F95`.
5. Install .NET 10 ASP.NET Core Runtime. The add-on ZIP includes its Windows x64
   CPython 3.13 Python bridge dependencies. Restart Blender before testing a clean scene.

Actions downloads require GitHub sign-in; private artifacts additionally require
repository read access. Public installation grants no private repository access.
No repository visibility or collaborators were changed for this branch.

Source dependency chain: frontend `Ruri.RipperHook` gitlink -> public backend
`Source/Endfield-GameHook` gitlink -> private source/runtime. Both refs are pinned,
not floating. Public CI never initializes private submodules.

The legacy shader libraries are included and hash checked during packaging.
The frontend and shader runtime are restored from the tested legacy baseline;
this is not the 5.3 legacy-compatibility switch. Existing 5.3 installations should
stay in their separate portable directory. User scenes are not part of any package.
