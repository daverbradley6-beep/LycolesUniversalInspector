import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gameplay_planner_v59 import plan,build
def receipt():
 p='StarterPack/"Weight"#1@Tool'
 return {"schemaVersion":"54.0","placeId":123,"observations":[
  {"index":1,"entries":[{"path":p,"className":"Tool"}]},
  {"index":2,"entries":[{"path":p,"className":"Tool"}]}]}
def contract(name="Weight"):
 return {"schemaVersion":"58.0","placeId":123,"ownerAuthorized":True,"actions":[
  {"id":"Train","operation":"activate_equipped_tool","toolName":name,
   "expectedValue":{"container":"leaderstats","name":"Strength","minimumDelta":1},
   "repeatCount":2,"cooldownSeconds":0.5}]}
class V59(unittest.TestCase):
 def test_candidates_not_actions(self):
  p=plan(receipt())
  self.assertEqual(p["summary"]["candidates"],1)
  self.assertEqual(p["summary"]["readyForLiveVerification"],0)
  self.assertFalse(p["liveGameplayVerified"])
 def test_authorized_matching(self):
  p=plan(receipt(),contract())
  self.assertEqual(p["summary"]["readyForLiveVerification"],1)
  self.assertEqual(p["summary"]["unsupported"],0)
 def test_missing_tool_not_generated(self):
  p=plan(receipt(),contract("Unknown"))
  self.assertEqual(p["summary"]["readyForLiveVerification"],0)
  self.assertEqual(p["summary"]["unsupported"],1)
 def test_place_mismatch(self):
  c=contract();c["placeId"]=456
  with self.assertRaises(ValueError):plan(receipt(),c)
 def test_reject_unauthorized(self):
  c=contract();c["ownerAuthorized"]=False
  with self.assertRaises(ValueError):plan(receipt(),c)
 def test_generate_matching(self):
  with tempfile.TemporaryDirectory() as d:
   p=build(receipt(),contract(),Path(d))
   self.assertEqual(p["summary"]["readyForLiveVerification"],1)
   s=(Path(d)/"gameplay-runner-v59.luau").read_text()
   self.assertIn("Tool",s)
   self.assertIn("Activate()",s)
 def test_disabled_no_contract(self):
  with tempfile.TemporaryDirectory() as d:
   build(receipt(),None,Path(d))
   self.assertFalse((Path(d)/"gameplay-runner-v59.luau").exists())
 def test_unsupported_no_script(self):
  with tempfile.TemporaryDirectory() as d:
   build(receipt(),contract("Unknown"),Path(d))
   self.assertFalse((Path(d)/"gameplay-runner-v59.luau").exists())
if __name__=="__main__":unittest.main()
