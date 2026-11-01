import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from inspection_adapter_v101 import adapt
from client_observer_compiler_v100 import generate,audit

def fixture():
 return {"objects":[
   {"path":"game.Workspace.Eggs.BasicEgg","id":"Egg","property":"Name"},
   {"path":["PlayerGui","HUD","Coins"],"id":"Coins","property":"Text","label":"Coins display"},
   {"path":"ServerStorage.Secret","id":"Secret","property":"Value"},
   {"path":"Workspace.World","id":"World"},
   {"path":"Workspace.World","id":"World"},
   {"path":"Workspace.Bad\nName","id":"Invalid"},
   {"path":"ReplicatedStorage.Modules.Data","id":"Module","property":"Source"}]}
class AdapterTests(unittest.TestCase):
 def test_accept(self):self.assertEqual(adapt(fixture(),123)[1]["accepted"],4)
 def test_reject(self):self.assertEqual(adapt(fixture(),123)[1]["rejected"],3)
 def test_normalize_game_prefix(self):self.assertEqual(adapt(fixture(),123)[0]["observations"][0]["path"][0],"Workspace")
 def test_infer_name(self):self.assertEqual(adapt(fixture(),123)[0]["observations"][2]["property"],"Name")
 def test_unique_names(self):
  ids=[o["id"] for o in adapt(fixture(),123)[0]["observations"]]
  self.assertEqual(len(ids),len(set(ids)))
 def test_place(self):self.assertEqual(adapt(fixture(),123)[0]["placeId"],123)
 def test_bad_place(self):
  with self.assertRaises(ValueError):adapt(fixture(),True)
 def test_bad_max(self):
  with self.assertRaises(ValueError):adapt(fixture(),123,151)
 def test_limit(self):self.assertEqual(adapt(fixture(),123,2)[1]["accepted"],2)
 def test_missing_collection(self):
  with self.assertRaises(ValueError):adapt({"foo":[]},123)
 def test_no_supported(self):
  with self.assertRaises(ValueError):adapt({"objects":[{"path":"ServerStorage.X"}]},123)
 def test_list_input(self):self.assertEqual(adapt([{"path":"Workspace.Spawn"}],123)[1]["accepted"],1)
 def test_entries(self):self.assertEqual(adapt({"entries":[{"path":"Players.Player"}]},123)[1]["accepted"],1)
 def test_instances(self):self.assertEqual(adapt({"instances":[{"path":"Workspace.Part"}]},123)[1]["accepted"],1)
 def test_generated_audit(self):
  with tempfile.TemporaryDirectory() as d:
   report,_=adapt(fixture(),123)
   generate(report,d)
   self.assertTrue(audit(d)["ok"])
 def test_no_verification(self):self.assertFalse(adapt(fixture(),123)[1]["verifiedInGame"])
 def test_deterministic(self):self.assertEqual(adapt(fixture(),123),adapt(fixture(),123))
if __name__=="__main__":unittest.main()
