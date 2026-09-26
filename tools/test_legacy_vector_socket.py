"""Exercise the real adapter on Blender versions with the changed socket layout.

Run in factory-startup Blender with --background --python-exit-code 1 --python.
"""
import importlib.util
from pathlib import Path
import sys
import types
import bpy

root = Path(__file__).resolve().parents[1]
# Import the adapter without enabling backend-dependent addon bootstrapping.
parts = ['RuriRipperImporter', 'Game', 'Endfield', 'shader', 'Blender']
for i in range(1, len(parts) + 1):
    name = '.'.join(parts[:i])
    package = types.ModuleType(name)
    package.__path__ = [str(root.joinpath(*parts[1:i]))]
    sys.modules[name] = package
host_name = 'RuriRipperImporter.Host.Blender'
for name in ['RuriRipperImporter.Host', host_name]:
    mod = types.ModuleType(name)
    mod.__path__ = []
    sys.modules[name] = mod
sys.modules[host_name].material_builder = types.ModuleType(host_name + '.material_builder')
from RuriRipperImporter.Game.Endfield.shader.Blender import compatibility as c
if '--original' in sys.argv:
    # Deliberate pre-fix reproduction: this must fail on 5.3.
    c.StableGraph.vtrans = c.StableGraph.__mro__[1].vtrans

mat = bpy.data.materials.new('Vector socket regression')
mat.use_nodes = True
mat['ruri_uber_stack'] = c.LEGACY_KEY
graph = c.StableGraph(mat.node_tree, is_group=False)
geo = mat.node_tree.nodes.new('ShaderNodeNewGeometry')
out = graph.vtrans(geo.outputs['Normal'], 'OBJECT', 'WORLD')
assert out.node.inputs['Vector'].links[0].from_socket == geo.outputs['Normal']
index = next((s for s in out.node.inputs if s.identifier == 'LightIndex'), None)
assert index is None or not index.is_linked
assert graph.vtrans(geo.outputs['Normal'], 'OBJECT', 'WORLD') == out
if index is not None:
    mat.node_tree.links.remove(out.node.inputs['Vector'].links[0])
    mat.node_tree.links.new(geo.outputs['Normal'], index)
    assert c.repair_vector_inputs() == 1
    assert c.repair_vector_inputs() == 0
    assert out.node.inputs['Vector'].is_linked and not index.is_linked
print('LEGACY_VECTOR_SOCKET_PASS', bpy.app.version_string)
