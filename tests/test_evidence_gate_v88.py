import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_gate_v88 import evaluate,changed,identity,rate_interval
P="keyboard:E:processed=False"
N="keyboard:W:processed=False"
def event(key,index,capture,success=True):
 return {"kind":"keyboard","details":{"key":key,"gameProcessed":False},
 "captureId":capture,"index":index,
 "observedChanges":[{"stat":"🥚 Hatches","before":1,"after":2}] if success else []}
def good():
 return [event(key,i,capture,key=="E") for capture in ("session1","session2") for key in ("E","W") for i in range(1,6)]
class GateTests(unittest.TestCase):
 def test_good(self):self.assertTrue(evaluate(good(),P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_one_session(self):
  data=[e for e in good() if e["captureId"]=="session1"]
  self.assertFalse(evaluate(data,P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_missing_control(self):
  self.assertFalse(evaluate([e for e in good() if e["details"]["key"]=="E"],P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_bad_candidate(self):
  data=good()
  for e in data:
   if e["details"]["key"]=="E":e["observedChanges"]=[]
  self.assertFalse(evaluate(data,P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_control_false_positive(self):
  data=good()
  data[-1]["observedChanges"]=[{"stat":"🥚 Hatches","before":1,"after":2}]
  self.assertFalse(evaluate(data,P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_duplicate_inputs(self):
  with self.assertRaises(ValueError):evaluate(good(),P,P,"🥚 Hatches")
 def test_bad_operator(self):
  with self.assertRaises(ValueError):evaluate(good(),P,N,"🥚 Hatches","invalid")
 def test_bad_minimum(self):
  with self.assertRaises(ValueError):evaluate(good(),P,N,"🥚 Hatches",minimum=0)
 def test_bad_sessions(self):
  with self.assertRaises(ValueError):evaluate(good(),P,N,"🥚 Hatches",sessions=0)
 def test_empty(self):self.assertFalse(evaluate([],P,N,"🥚 Hatches")["eligibleForHumanReview"])
 def test_interval_empty(self):self.assertEqual(rate_interval(0,0),[0,1])
 def test_interval_bounds(self):
  low,high=rate_interval(5,5)
  self.assertLess(low,1)
  self.assertEqual(high,1)
 def test_no_execution(self):self.assertFalse(evaluate(good(),P,N,"🥚 Hatches")["executionEnabled"])
 def test_no_causal_claim(self):self.assertFalse(evaluate(good(),P,N,"🥚 Hatches")["causalityProven"])
 def test_manual_strategy(self):self.assertEqual(evaluate(good(),P,N,"🥚 Hatches")["actionSpecification"]["executionStrategy"],"manual_observation_only")
 def test_identity(self):self.assertEqual(identity(event("E",1,"a")),P)
 def test_changed(self):self.assertTrue(changed(event("E",1,"a"),"🥚 Hatches","increase"))
 def test_unchanged(self):self.assertFalse(changed(event("W",1,"a",False),"🥚 Hatches","increase"))
 def test_decrease(self):
  e=event("E",1,"a");e["observedChanges"][0]["after"]=0
  self.assertTrue(changed(e,"🥚 Hatches","decrease"))
 def test_gui(self):
  e=event("E",1,"a");e["kind"]="gui";e["details"]={"path":[{"name":"B","className":"TextButton","ordinal":1}]}
  self.assertTrue(identity(e).startswith("gui:"))
 def test_invalid_gui(self):
  e=event("E",1,"a");e["kind"]="gui";e["details"]={"path":[{"name":"B","className":"TextButton","ordinal":0}]}
  self.assertIsNone(identity(e))
if __name__=="__main__":unittest.main()
