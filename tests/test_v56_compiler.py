import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from universal_compiler_v56 import quality,compile_bundle,audit,build
from evidence_explorer_v55 import parse_path
from balanced_discovery_v54 import analyze
def fixture():
 p='ReplicatedStorage/"Strength"#1@IntValue'
 return {"schemaVersion":"54.0","placeId":123,"observations":[
  {"index":1,"entries":[{"path":p,"className":"IntValue","value":"10"}]},
  {"index":2,"entries":[{"path":p,"className":"IntValue","value":"20"}]}]}
class V56(unittest.TestCase):
 def test_quality(self):
  self.assertEqual(quality(analyze(fixture()))["changedPaths"],1)
 def test_bundle(self):
  bundle=compile_bundle(analyze(fixture()))
  self.assertEqual(bundle["schemaVersion"],"56.0")
  self.assertEqual(len(bundle["fingerprint"]),64)
  self.assertIn("Training",bundle["groups"])
 def test_compile_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   check=build(json.dumps(fixture()),123,Path(tmp))
   self.assertTrue(check["passed"])
   self.assertEqual(len(list(Path(tmp).iterdir())),4)
   self.assertIn("MouseButton1Click",(Path(tmp)/"universal-evidence-explorer-v56.luau").read_text())
 def test_wrong_place(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):build(json.dumps(fixture()),456,Path(tmp))
 def test_audit_rejects_placeholder(self):
  bundle=compile_bundle(analyze(fixture()))
  self.assertFalse(audit(bundle,"PLACE_ID")["passed"])
 def test_json_name_parser(self):
  self.assertEqual(parse_path('Workspace/"Meshes/JunglePortal"#1@MeshPart')[1]["name"],"Meshes/JunglePortal")
  self.assertEqual(parse_path('Workspace/"a\\\"b"#1@Model')[1]["name"],'a"b')
 def test_reject_unknown(self):
  self.assertIsNone(parse_path('DataStoreService/"X"#1@Folder'))
if __name__=="__main__":unittest.main()
