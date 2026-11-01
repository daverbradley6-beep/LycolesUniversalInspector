import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from verification_replay_v60 import verify,release

def contract():
 return {"schemaVersion":"58.0","placeId":123,"ownerAuthorized":True,"actions":[{
  "id":"Training","operation":"activate_equipped_tool","toolName":"Weight",
  "expectedValue":{"container":"leaderstats","name":"Strength","minimumDelta":2},
  "repeatCount":2,"timeoutSeconds":4,"cooldownSeconds":0.5}]}
def trace(pairs=((0,10,1,12),(2,12,3,14))):
 events=[]
 for t1,v1,t2,v2 in pairs:
  events.extend([{"time":t1,"actionId":"Training","kind":"before","value":v1},
                 {"time":t2,"actionId":"Training","kind":"after","value":v2}])
 return {"schemaVersion":"60.trace","placeId":123,"events":events}
def receipt():
 p='StarterPack/"Weight"#1@Tool'
 return {"schemaVersion":"54.0","placeId":123,"observations":[
  {"index":1,"entries":[{"path":p,"className":"Tool"}]},
  {"index":2,"entries":[{"path":p,"className":"Tool"}]}]}
class V60(unittest.TestCase):
 def test_observed(self):
  r=verify(contract(),trace())
  self.assertTrue(r["allObserved"])
  self.assertFalse(r["serverOutcomeVerified"])
 def test_failed_delta(self):
  r=verify(contract(),trace(((0,10,1,11),(2,12,3,14))))
  self.assertFalse(r["allObserved"])
 def test_timeout(self):
  r=verify(contract(),trace(((0,10,5,20),(6,20,7,22))))
  self.assertEqual(r["results"][0]["attempts"][0]["status"],"timed_out")
 def test_incomplete(self):
  t=trace();t["events"].pop()
  self.assertFalse(verify(contract(),t)["allObserved"])
 def test_place_mismatch(self):
  t=trace();t["placeId"]=456
  with self.assertRaises(ValueError):verify(contract(),t)
 def test_out_of_order(self):
  t=trace();t["events"][1]["time"]=-1
  with self.assertRaises(ValueError):verify(contract(),t)
 def test_invalid_action(self):
  t=trace();t["events"][0]["actionId"]="Unknown"
  with self.assertRaises(ValueError):verify(contract(),t)
 def test_release_positive(self):
  with tempfile.TemporaryDirectory() as d:
   m=release(receipt(),contract(),trace(),Path(d))
   self.assertEqual(m["observationallyPassed"],["Training"])
   self.assertTrue((Path(d)/"combined-inspection-and-gameplay-v59.luau").exists())
 def test_release_negative(self):
  with tempfile.TemporaryDirectory() as d:
   m=release(receipt(),contract(),trace(((0,10,1,11),(2,12,3,14))),Path(d))
   self.assertEqual(m["observationallyPassed"],[])
   self.assertFalse((Path(d)/"gameplay-runner-v59.luau").exists())
 def test_release_no_discovery(self):
  with tempfile.TemporaryDirectory() as d:
   r=receipt()
   for sample in r["observations"]:sample["entries"]=[]
   m=release(r,contract(),trace(),Path(d))
   self.assertEqual(m["observationallyPassed"],[])
if __name__=="__main__":unittest.main()
