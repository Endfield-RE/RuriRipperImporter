"""Create a tracked-blob-only legacy addon, excluding every backend payload."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_RUNTIME = ROOT / 'dist/.python-runtime/cp313-win_amd64'
DIRS = {'Game', 'RuriRipperPyBridge', 'RuriYamlDumper', 'endfield_animation'}
SHADERS = 'Game/EndField/shader/'
FORBIDDEN = {'.dll', '.exe', '.pdb', '.tpk', '.cabmap', '.nupkg', '.pyc'}

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def build():
    entries = {}
    hashes = json.loads(git('show', ':provenance/blender52-shaders.sha256.json'))
    for record in git('ls-files', '--stage', '-z').split(b'\0'):
        if not record:
            continue
        meta, name = record.decode().split('\t', 1)
        mode, blob, stage = meta.split()
        p = PurePosixPath(name)
        include = p.parts[0] in DIRS or (len(p.parts) == 1 and p.suffix == '.py') or name in {'LICENSE', 'README.md', 'INSTALL.md'}
        if not include:
            continue
        assert mode in {'100644', '100755'} and stage == '0', name
        assert p.suffix.lower() not in FORBIDDEN, name
        if p.suffix == '.blend':
            assert name == SHADERS + p.name and p.name in hashes, name
        data = git('cat-file', 'blob', blob)
        if p.suffix == '.py':
            compile(data, name, 'exec')
        entries[name] = data
    for name, digest in hashes.items():
        assert hashlib.sha256(entries[SHADERS + name]).hexdigest() == digest, name
    required_runtime = {'clr.py', '_cffi_backend.cp313-win_amd64.pyd',
                        'pythonnet/__init__.py', 'pythonnet/runtime/Python.Runtime.dll'}
    runtime_files = {p.relative_to(PYTHON_RUNTIME).as_posix(): p for p in PYTHON_RUNTIME.rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert required_runtime <= runtime_files.keys(), required_runtime - runtime_files.keys()
    for name, path in runtime_files.items():
        assert not path.is_symlink() and path.resolve().is_relative_to(PYTHON_RUNTIME.resolve()), name
        entries['_bundled/cp313-win_amd64/' + name] = path.read_bytes()
    tree = ast.parse(entries[SHADERS + 'ruri_endfield.py'])
    manifests = next(json.loads(ast.literal_eval(n.value.args[0])) for n in tree.body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MANIFESTS' for t in n.targets))
    assert {m['blend'] for m in manifests} == set(hashes)
    assert {'__init__.py', 'LICENSE', 'INSTALL.md'} <= entries.keys()
    entries['BUILD-INFO.json'] = json.dumps({
        'addon_commit': git('rev-parse', 'HEAD').decode().strip(),
        'backend_commit': git('rev-parse', 'HEAD:Ruri.RipperHook').decode().strip(),
        'abi': 'legacy52', 'tested_blender': '5.2.2',
        'includes_backend': False, 'includes_private_module': False,
        'bundled_python': 'cp313-win_amd64: pythonnet 3.1.0, clr-loader 0.3.1, cffi 2.1.1, pycparser 3.0',
        'shader_sha256': hashes}, indent=2).encode()
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    archive = out / 'RuriRipperImporter-Blender-5.2.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo('RuriRipperImporter/' + name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any('Endfield-GameHook/' in n or 'Ruri.RipperHook/' in n for n in z.namelist())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n')
    print(f'PUBLIC_BLENDER52_PACKAGE_PASS files={len(entries)} sha256={digest}')

if __name__ == '__main__':
    build()
