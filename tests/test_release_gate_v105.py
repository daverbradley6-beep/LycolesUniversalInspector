import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_gate_v105 import verify
from release_pipeline_v104 import generate, canonical

DATA = {'placeId': 123, 'objects': [
    {'path': 'Workspace.Egg', 'className': 'Tool'},
    {'path': 'PlayerGui.HUD.Coins', 'className': 'TextLabel'},
]}

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        assert generate(DATA, 123, self.path)['ok']

    def test_valid(self): self.assertTrue(verify(self.path)['ok'])
    def test_verified_flag(self): self.assertFalse(verify(self.path)['verifiedInGame'])
    def test_minimum(self): self.assertIn('insufficient_observations', verify(self.path, minimum=3)['issues'])
    def test_bad_minimum(self):
        with self.assertRaises(ValueError): verify(self.path, minimum=-1)
    def test_bad_threshold(self):
        with self.assertRaises(ValueError): verify(self.path, maximum_rejection_rate=2)
    def test_missing(self):
        (self.path / 'report-v104.json').unlink()
        self.assertFalse(verify(self.path)['ok'])
    def test_tamper(self):
        with (self.path / 'LycolesObserverV104.client.lua').open('a') as f: f.write('bad')
        self.assertIn('hash_mismatch:LycolesObserverV104.client.lua', verify(self.path)['issues'])
    def test_manifest_claim(self):
        p = self.path / 'manifest-v104.json'
        data = json.loads(p.read_text()); data['verifiedInGame'] = True
        p.write_bytes(canonical(data))
        self.assertIn('manifest_claim', verify(self.path)['issues'])
    def test_report_claim(self):
        p = self.path / 'report-v104.json'
        data = json.loads(p.read_text()); data['verifiedInGame'] = True
        p.write_bytes(canonical(data))
        self.assertIn('unsupported_verification_claim', verify(self.path)['issues'])
    def test_accounting(self):
        p = self.path / 'report-v104.json'
        data = json.loads(p.read_text()); data['inputCount'] = 100
        p.write_bytes(canonical(data))
        self.assertIn('invalid_accounting', verify(self.path)['issues'])
    def test_symlink(self):
        p = self.path / 'report-v104.json'; p.unlink(); p.symlink_to(self.path / 'absent')
        self.assertFalse(verify(self.path)['ok'])
    def test_reproducible(self):
        self.assertEqual(verify(self.path), verify(self.path))

if __name__ == '__main__': unittest.main()
