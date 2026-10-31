import importlib.util
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('adapter', ROOT / 'tools' / 'scan_adapter_v36.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class AdapterTests(unittest.TestCase):
    def fake(self, parts, count):
        return SimpleNamespace(compile_scan=lambda _: {'integrity': {'scanId': 'scan-test', 'placeId': 123,
                    'parts': parts, 'objects': count, 'scanComplete': True}})
    def test_single_part(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'p1.json').write_text('{"partIndex":1,"objects":[{"path":"workspace.X","class":"Folder"}]}')
            result = mod.adapt_parts(d, self.fake(1, 1))
            self.assertEqual(result['objects'][0]['name'], 'X')
            self.assertEqual(result['objects'][0]['className'], 'Folder')
            self.assertFalse(result['runtimeVerified'])
    def test_multiple_parts_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'b.json').write_text('{"partIndex":2,"objects":[{"path":"workspace.B"}]}')
            pathlib.Path(d, 'a.json').write_text('{"partIndex":1,"objects":[{"path":"workspace.A"}]}')
            result = mod.adapt_parts(d, self.fake(2, 2))
            self.assertEqual([o['name'] for o in result['objects']], ['A', 'B'])
    def test_count_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'p.json').write_text('{"partIndex":1,"objects":[]}')
            with self.assertRaises(ValueError): mod.adapt_parts(d, self.fake(1, 1))
    def test_missing_path(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'p.json').write_text('{"partIndex":1,"objects":[{}]}')
            with self.assertRaises(ValueError): mod.adapt_parts(d, self.fake(1, 1))
    def test_metadata_only_file(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'meta.json').write_text('{"metadata":{}}')
            pathlib.Path(d, 'part.json').write_text('{"partIndex":1,"objects":[]}')
            self.assertEqual(mod.adapt_parts(d, self.fake(1, 0))['objects'], [])
    def test_preserve_ordinal(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d, 'p.json').write_text('{"partIndex":1,"objects":[{"path":"workspace.A","scanOrdinal":2}]}')
            self.assertEqual(mod.adapt_parts(d, self.fake(1, 1))['objects'][0]['scanOrdinal'], 2)
    def test_compiler_error_propagates(self):
        with self.assertRaises(ValueError):
            mod.adapt_parts('.', SimpleNamespace(compile_scan=lambda _: (_ for _ in ()).throw(ValueError('incomplete'))))

if __name__ == '__main__': unittest.main()
