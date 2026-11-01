import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspection_quality_v103 import inspect, emit, normalize_path

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.data = {'observations': [
            {'path': 'game.Workspace.Egg', 'className': 'Tool'},
            {'path': ['PlayerGui', 'HUD', 'Coins'], 'className': 'TextLabel'},
            {'path': 'Workspace.Egg', 'className': 'Tool'},
            {'path': 'ServerStorage.Hidden', 'className': 'Tool'},
            {'path': 'Workspace.Remote', 'className': 'RemoteEvent'},
            {'path': 'Workspace.Bad\nName', 'className': 'TextLabel'},
        ]}
    def test_accept(self): self.assertEqual(inspect(self.data, 12)['acceptedCount'], 2)
    def test_reject(self): self.assertEqual(inspect(self.data, 12)['rejectedCount'], 4)
    def test_deduplicate(self): self.assertEqual(inspect(self.data, 12)['rejections']['duplicate_path'], 1)
    def test_read_only(self): self.assertTrue(all(not x['canAutomate'] for x in inspect(self.data, 12)['objects']))
    def test_unverified(self): self.assertFalse(inspect(self.data, 12)['verifiedInGame'])
    def test_no_actions(self): self.assertEqual(inspect(self.data, 12)['gameplayFunctionsGenerated'], 0)
    def test_game_prefix(self): self.assertEqual(normalize_path('game.Workspace.Egg'), ['Workspace','Egg'])
    def test_bad_path(self): self.assertIsNone(normalize_path('ServerStorage.Hidden'))
    def test_bad_place(self):
        with self.assertRaises(ValueError): inspect(self.data, True)
    def test_missing(self):
        with self.assertRaises(ValueError): inspect({}, 12)
    def test_empty(self): self.assertEqual(inspect([], 12)['acceptedCount'], 0)
    def test_deterministic(self): self.assertEqual(inspect(self.data, 12), inspect(self.data, 12))
    def test_emit(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'report.json'
            result = emit(self.data, 12, p)
            self.assertEqual(result['accepted'], 2)
            self.assertEqual(json.loads(p.read_text())['acceptedCount'], 2)

if __name__ == '__main__': unittest.main()
