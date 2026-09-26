"""Build a Blender-installable public ZIP from an explicit tracked-file allowlist."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "RuriRipperImporter"
ROOT_FILES = {"__init__.py", "LICENSE", "README.md", "INSTALL.md"}
SOURCE_DIRS = {"Game", "Host", "Kernel", "RuriYamlDumper"}
FORBIDDEN = {".dll", ".exe", ".pdb", ".tpk", ".blend", ".cabmap", ".nupkg", ".pyc"}
# Upstream public node libraries are plugin resources, not game/test scenes.
PUBLIC_SHADER_LIBRARIES = {
    "Game/Endfield/shader/Blender/legacy52/ruri_character_uber_endfield.blend",
    "Game/AzurPromilia/shader/Blender/ruri_character_uber_azurpromilia.blend",
    "Game/AzurPromilia/shader/Blender/ruri_post_azurpromilia.blend",
    "Game/EXILIUM/shader/Blender/ruri_character_uber_girlsfrontline.blend",
    "Game/EXILIUM/shader/Blender/ruri_post_girlsfrontline.blend",
    "Game/Endfield/shader/Blender/ruri_character_uber_endfield.blend",
    "Game/Endfield/shader/Blender/ruri_effect_uber_endfield.blend",
    "Game/Endfield/shader/Blender/ruri_post_endfield.blend",
    "Game/Endfield/shader/Blender/ruri_scene_uber_endfield.blend",
    "Game/Endfield/shader/Blender/ruri_shadowreceiver_endfield.blend",
    "Game/Endfield/shader/Blender/ruri_water_endfield.blend",
    "Game/WutheringWaves/shader/Blender/ruri_character_uber_wutheringwaves.blend",
    "Game/WutheringWaves/shader/Blender/ruri_post_wutheringwaves.blend",
}


def included(path):
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or "\\" in path:
        raise ValueError(f"Invalid repository path: {path}")
    return path in ROOT_FILES or p.parts[0] in SOURCE_DIRS


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def build():
    entries = []
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, name = record.decode("utf-8").split("\t", 1)
        mode, blob, stage = metadata.split()
        if not included(name):
            continue
        if mode not in {"100644", "100755"} or stage != "0":
            raise ValueError(f"Non-regular or conflicted package input: {name}")
        if PurePosixPath(name).suffix.lower() in FORBIDDEN and name not in PUBLIC_SHADER_LIBRARIES:
            raise ValueError(f"Binary/runtime payload in public package: {name}")
        data = git("cat-file", "blob", blob)
        if name.endswith(".py"):
            compile(data, name, "exec")
        entries.append((name, data))
    if not ROOT_FILES.issubset({name for name, _ in entries}):
        raise ValueError("Missing package entrypoint, license or installation instructions")
    info = {
        "addon_commit": git("rev-parse", "HEAD").decode().strip(),
        "backend_commit": git("rev-parse", "HEAD:Ruri.RipperHook").decode().strip(),
        "blender_minimum": "5.3.0", "includes_backend": False,
        "includes_private_module": False,
    }
    entries.append(("BUILD-INFO.json", json.dumps(info, indent=2).encode()))
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    archive = out / "RuriRipperImporter-Blender53.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries):
            item = zipfile.ZipInfo(f"{PACKAGE}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert f"{PACKAGE}/__init__.py" in z.namelist()
        assert all(n.startswith(f"{PACKAGE}/") for n in z.namelist())
        assert not any("Endfield-GameHook/" in n or "Ruri.RipperHook/" in n for n in z.namelist())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(f"PUBLIC_ADDON_PACKAGE_PASS files={len(entries)} sha256={digest}")


if __name__ == "__main__":
    build()
