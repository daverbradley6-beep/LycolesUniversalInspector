import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from release_builder_v52 import build,synthetic_receipt
M={"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"f","features":[{"id":"inspect-ui","family":"interface","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Players.LocalPlayer.PlayerGui.HUD.Score","Workspace.A"]}]}
class V52(unittest.TestCase):
 def test_synthetic_identity(self):
  r=synthetic_receipt(M);self.assertEqual(r["scanId"],"s");self.assertEqual(len(r["observations"]),3)
 def test_offline_build(self):
  with tempfile.TemporaryDirectory() as td:
   files=build(M,td,synthetic_receipt(M))
   self.assertIn("feature-candidates-v49.json",files)
   self.assertIn("auto-actions-v51.luau",files)
   self.assertIn("auto-probe-v46.luau",files)
   self.assertEqual(json.loads((Path(td)/"auto-actions-v51.json").read_text())["actions"][0]["kind"],"read-value")
 def test_build_without_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   files=build(M,td)
   self.assertNotIn("auto-actions-v51.json",files)
   self.assertIn("feature-dashboard-v47.luau",files)
 def test_reproducible(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   fa=build(M,a,synthetic_receipt(M));fb=build(M,b,synthetic_receipt(M))
   self.assertEqual(set(fa),set(fb))
   for key in fa:self.assertEqual(fa[key].read_bytes(),fb[key].read_bytes())
 def test_wrong_game(self):
  with tempfile.TemporaryDirectory() as td:
   r=synthetic_receipt(M);r["placeId"]=9
   with self.assertRaises(ValueError):build(M,td,r)
 def test_no_server_remote(self):
  with tempfile.TemporaryDirectory() as td:
   files=build(M,td,synthetic_receipt(M))
   for name,path in files.items():
    if name.endswith(".luau"):self.assertNotIn("FireServer(",path.read_text())
if __name__=="__main__":unittest.main()
