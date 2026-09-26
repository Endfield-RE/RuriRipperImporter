"""CI: execute the actual adapter method against the 5.3 input ordering."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

source = Path(__file__).resolve().parents[1] / 'Game/Endfield/shader/Blender/compatibility.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StableGraph')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'vtrans')
namespace = {}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)


class Graph:
    vtrans = namespace['vtrans']

    def __init__(self):
        self._cse = {}
        self.created = []
        self.connections = []

    def _ck(self, value):
        return value

    def _nd(self, kind):
        self.node = SimpleNamespace(inputs={0: 'LightIndex', 'Vector': 'Vector'},
                                    outputs={'Vector': object()})
        self.created.append(kind)
        return self.node

    def _set(self, target, value):
        self.connections.append((target, value))


class SocketContract(unittest.TestCase):
    def test_named_vector_input_and_cache(self):
        graph = Graph()
        result = graph.vtrans('normal', 'OBJECT', 'WORLD')
        self.assertEqual(graph.connections, [('Vector', 'normal')])
        self.assertEqual((graph.node.convert_from, graph.node.convert_to), ('OBJECT', 'WORLD'))
        self.assertIs(graph.vtrans('normal', 'OBJECT', 'WORLD'), result)
        self.assertEqual(len(graph.created), 1)


if __name__ == '__main__':
    unittest.main()
