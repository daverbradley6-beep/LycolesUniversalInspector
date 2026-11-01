import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from universal_discovery_v89 import discover,compile_release

def ev(key,idx,session,match):
 return {"kind":"keyboard","details":{"key":key,"gameProcessed":False},
         "captureId":session,"index":idx,
         "observedChanges":[{"stat":"🥚 Hatches","before":1,"after":2}] if match else []}
def fixture():
 return [ev(key,i,session,key=="E") for session in ("s1","s2")
         for key in ("E","W") for i in range(1,6)]
class DiscoveryTests(unittest.TestCase):
 def test_positive(self):
  x=discover(fixture())
  self.assertEqual(len(x["actions"]),1)
  self.assertEqual(x["actions"][0]["status"],"review_candidate")
 def test_negative_control(self):
  self.assertIn("keyboard:W",discover(fixture())["actions"][0]["negativeControl"]["input"])
 def test_no_auto_execution(self):
  self.assertFalse(discover(fixture())["actions"][0]["executionEnabled"])
 def test_no_approval(self):
  self.assertFalse(discover(fixture())["actions"][0]["approved"])
 def test_no_causal_proof(self):
  self.assertFalse(discover(fixture())["actions"][0]["causalityProven"])
 def test_single_session(self):
  x=discover([e for e in fixture() if e["captureId"]=="s1"])
  self.assertEqual(x["actions"][0]["status"],"insufficient_evidence")
 def test_missing_control(self):
  x=discover([e for e in fixture() if e["details"]["key"]=="E"])
  self.assertIn("no_adequate_negative_control",x["actions"][0]["issues"])
 def test_contaminated_control(self):
  x=fixture()
  for e in x:
   if e["details"]["key"]=="W" and e["index"]==1:
    e["observedChanges"]=[{"stat":"🥚 Hatches","before":1,"after":2}]
  self.assertEqual(discover(x)["actions"][0]["status"],"insufficient_evidence")
 def test_candidate_inconsistent(self):
  x=fixture()
  for e in x:
   if e["details"]["key"]=="E" and e["captureId"]=="s2":
    e["observedChanges"]=[]
  self.assertFalse(any(a["status"]=="review_candidate" for a in discover(x)["actions"]))
 def test_no_data(self):self.assertEqual(discover([])["actions"],[])
 def test_invalid_minimum(self):
  with self.assertRaises(ValueError):discover([],0)
 def test_invalid_sessions(self):
  with self.assertRaises(ValueError):discover([],min_sessions=0)
 def test_invalid_rate(self):
  with self.assertRaises(ValueError):discover([],min_rate=1.5)
 def test_invalid_place(self):
  with self.assertRaises(ValueError):compile_release([],0)
 def test_catalog(self):
  x=compile_release(fixture(),85896571713843)
  self.assertEqual(x["catalog"]["placeId"],85896571713843)
  self.assertFalse(x["catalog"]["contracts"][0]["approved"])
 def test_stable_ids(self):
  self.assertEqual(discover(fixture())["actions"][0]["id"],discover(list(reversed(fixture())))["actions"][0]["id"])
 def test_generic_stats(self):
  x=fixture()
  for e in x:
   for c in e["observedChanges"]:c["stat"]="Coins"
  self.assertEqual(discover(x)["actions"][0]["outcome"]["stat"],"Coins")
 def test_two_outcomes(self):
  x=fixture()
  for e in x:
   if e["details"]["key"]=="E":
    e["observedChanges"].append({"stat":"Coins","before":10,"after":11})
  self.assertEqual(len(discover(x)["actions"]),2)
 def test_zero_matches(self):
  x=[ev("W",i,"s1",False) for i in range(5)]
  self.assertEqual(discover(x)["actions"],[])
 def test_manifest_flags(self):
  x=compile_release(fixture(),123)
  self.assertFalse(x["verifiedInGame"])
  self.assertEqual(x["automaticallyExecuted"],0)
if __name__=="__main__":unittest.main()
