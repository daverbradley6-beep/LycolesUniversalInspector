import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from feature_dashboard_v47 import generate,validate
M={"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"f","features":[{"id":"inspect-training","label":"Inspect Training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A","Players.LocalPlayer.PlayerGui.Hud"]}]}
class V47(unittest.TestCase):
 def test_generate(self):
  s=generate(M)
  for token in ("LycolesV47","Inspect all systems","FindFirstChild","game.PlaceId","Activated:Connect","PlayerGui"):self.assertIn(token,s)
 def test_count(self):self.assertEqual(len(validate(M)),1)
 def test_deterministic(self):self.assertEqual(generate(M),generate(M))
 def test_wrong_schema(self):
  with self.assertRaises(ValueError):generate({**M,"schemaVersion":"wrong"})
 def test_read_only(self):
  with self.assertRaises(ValueError):generate({**M,"readOnly":False})
 def test_supported_roots(self):
  from feature_dashboard_v47 import supported_path
  for root in ("Workspace","Players","ReplicatedStorage","ReplicatedFirst","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams"):
   self.assertTrue(supported_path(root+".Example"),root)
 def test_unsupported_roots(self):
  from feature_dashboard_v47 import supported_path
  for path in ("NoRoot.A","ServerStorage.Secret","Workspace","Workspace..A","",None):
   self.assertFalse(supported_path(path),path)
 def test_no_features(self):
  with self.assertRaises(ValueError):generate({**M,"features":[]})
 def test_duplicate_ids(self):
  with self.assertRaises(ValueError):generate({**M,"features":M["features"]*2})
 def test_invalid_id(self):
  with self.assertRaises(ValueError):generate({**M,"features":[{**M["features"][0],"id":"unsafe"}]})
 def test_invalid_kind(self):
  with self.assertRaises(ValueError):generate({**M,"features":[{**M["features"][0],"kind":"gameplay"}]})
 def test_invalid_path(self):
  with self.assertRaises(ValueError):generate({**M,"features":[{**M["features"][0],"evidencePaths":["NoRoot.A"]}]})
 def test_duplicate_paths(self):
  with self.assertRaises(ValueError):generate({**M,"features":[{**M["features"][0],"evidencePaths":["Workspace.A","Workspace.A"]}]})
 def test_unverified(self):self.assertNotIn("FireServer(",generate(M))
if __name__=="__main__":unittest.main()
