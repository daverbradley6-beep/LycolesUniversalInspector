import importlib.util
import pathlib
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('matcher', ROOT / 'tools' / 'match_scan_features_v36.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

def report(paths):
    return {'schemaVersion': '32.0', 'features': [{'id': 'f', 'name': 'Test', 'dependencies': {'paths': paths}}]}

def scan(paths):
    return {'schemaVersion': '36.0', 'placeId': 123, 'scanId': 'scan',
            'integrity': {'scanComplete': True},
            'objects': [{'path': p, 'name': p.rsplit('.', 1)[-1]} for p in paths]}

class MatcherTests(unittest.TestCase):
    def test_unique(self):
        self.assertEqual(m.match(report(['workspace.A']), scan(['workspace.A']))['features'][0]['status'], 'unique-paths-observed')
    def test_missing(self):
        self.assertEqual(m.match(report(['workspace.B']), scan(['workspace.A']))['features'][0]['status'], 'missing')
    def test_collision(self):
        r = m.match(report(['workspace.A']), scan(['workspace.A', 'workspace.A']))
        self.assertEqual(r['pathCollisions'], 1)
        self.assertEqual(r['features'][0]['status'], 'ambiguous-paths')
    def test_incomplete(self):
        x = scan([]); x['integrity']['scanComplete'] = False
        with self.assertRaises(ValueError): m.match(report([]), x)
    def test_no_approval(self):
        self.assertFalse(m.match(report(['workspace.A']), scan(['workspace.A']))['gameplayAutomationApproved'])
    def test_lexical_status(self):
        a = {'schemaVersion': '34.0', 'features': [{'featureId': 'f', 'status': 'lexically-corroborated'}]}
        self.assertEqual(m.match(report([]), scan([]), a)['features'][0]['lexicalStatus'], 'lexically-corroborated')

if __name__ == '__main__': unittest.main()
