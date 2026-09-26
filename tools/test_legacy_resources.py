"""CI checks for the pinned shader-only compatibility payload (no bpy needed)."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'Game/Endfield/shader/Blender/legacy52'


class LegacyResources(unittest.TestCase):
    def test_pinned_runtime_and_template(self):
        expected = {
            'runtime.py': '13f242b03b03a2a9d3e5e68de1bd0b88137a4d23c68de4f7b16ae3a883037cc3',
            'ruri_character_uber_endfield.blend': 'f91e1b2e047c8585f334b439a70d12a0fdec68a0d2fea838326974ed0c6b1ef1',
        }
        for name, sha in expected.items():
            self.assertEqual(hashlib.sha256((FOLDER / name).read_bytes()).hexdigest(), sha)

    def test_character_manifest_present(self):
        module = ast.parse((FOLDER / 'runtime.py').read_text(encoding='utf-8'))
        node = next(n for n in module.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'MANIFESTS' for t in n.targets))
        manifests = json.loads(node.value.args[0].value)
        character = next(m for m in manifests if m['names']['panel_key'] == 'ruri_character_uber_endfield')
        self.assertEqual(character['stamp'], '941c8817ab4011a2')
        self.assertTrue((FOLDER / character['blend']).is_file())
        self.assertTrue({'Face', 'Hair', 'Standard', 'Eyes'}.issubset(character['parts']))

    def test_packager_explicitly_allows_only_shader_template(self):
        import package_addon
        allowed = [p for p in package_addon.PUBLIC_SHADER_LIBRARIES if '/legacy52/' in p]
        self.assertEqual(allowed, ['Game/Endfield/shader/Blender/legacy52/ruri_character_uber_endfield.blend'])


if __name__ == '__main__':
    unittest.main()
