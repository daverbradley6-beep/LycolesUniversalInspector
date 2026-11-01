import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from capability_catalog_v102 import classify,build

def fixture():
 return {"objects":[
  {"path":"PlayerGui.HUD.Coins","className":"TextLabel","name":"Coins"},
  {"path":["PlayerGui","HUD","Play"],"className":"TextButton","name":"Play"},
  {"path":"Workspace.World.Door","className":"ProximityPrompt","name":"Door"},
  {"path":"Workspace.Items.Sword","className":"Tool","name":"Sword"},
  {"path":"Workspace.World.Unknown","className":"RemoteEvent","name":"Remote"},
  {"path":"ServerStorage.Secret","className":"TextLabel","name":"Secret"}]}
class CatalogTests(unittest.TestCase):
 def test_classify(self):self.assertEqual(len(classify(fixture(),123)[1]["capabilities"]),4)
 def test_counts(self):self.assertEqual(classify(fixture(),123)[1]["counts"]["visible_button"],1)
 def test_rejections(self):self.assertEqual(classify(fixture(),123)[1]["rejections"]["unsupported_class"],1)
 def test_invalid_path(self):self.assertEqual(classify(fixture(),123)[1]["rejections"]["invalid_path"],1)
 def test_read_only(self):self.assertFalse(classify(fixture(),123)[1]["actionGeneration"])
 def test_no_verification(self):self.assertFalse(classify(fixture(),123)[1]["verifiedInGame"])
 def test_property(self):self.assertEqual(classify(fixture(),123)[0]["observations"][0]["property"],"Text")
 def test_prompt(self):self.assertEqual(classify(fixture(),123)[0]["observations"][2]["property"],"Enabled")
 def test_max_items(self):self.assertEqual(len(classify(fixture(),123,2)[1]["capabilities"]),2)
 def test_bad_max(self):
  with self.assertRaises(ValueError):classify(fixture(),123,0)
 def test_bad_place(self):
  with self.assertRaises(ValueError):classify(fixture(),True)
 def test_empty(self):
  with self.assertRaises(ValueError):classify({"objects":[]},123)
 def test_missing_collection(self):
  with self.assertRaises(ValueError):classify({},123)
 def test_non_string_class(self):
  with self.assertRaises(ValueError):classify({"objects":[{"className":[],"path":"Workspace.X"}]},123)
 def test_deterministic(self):self.assertEqual(classify(fixture(),123),classify(fixture(),123))
 def test_build(self):
  with tempfile.TemporaryDirectory() as d:
   result=build(fixture(),123,d)
   self.assertTrue(result["v100AuditPassed"])
   self.assertTrue((Path(d)/"capabilities-v102.json").exists())
 def test_catalog_read_only(self):
  with tempfile.TemporaryDirectory() as d:
   build(fixture(),123,d)
   c=json.loads((Path(d)/"capabilities-v102.json").read_text())
   self.assertTrue(all(x["actionGenerated"] is False for x in c["capabilities"]))
if __name__=="__main__":unittest.main()
