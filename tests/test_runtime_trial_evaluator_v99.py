import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from runtime_trial_evaluator_v99 import validate,observed,wilson_lower,evaluate,parse_logs,write_report

def trial(session,index,kind,change=True):
 return {"schemaVersion":"99.trial","placeId":123456,"userId":10001,
 "sessionId":session,"actionId":"Collect","stat":"Coins",
 "index":index,"kind":kind,"expected":"increase",
 "before":100,"after":101 if change else 100}
def fixture():
 return [trial(s,i,"action",True) for s in ("A","B") for i in range(10)]+[
 trial(s,100+i,"control",False) for s in ("A","B") for i in range(10)]
class EvaluatorTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(trial("A",1,"action"))["placeId"],123456)
 def test_observed_increase(self):self.assertEqual(observed(trial("A",1,"action")),"increase")
 def test_observed_equal(self):self.assertEqual(observed(trial("A",1,"control",False)),"equal")
 def test_wilson_empty(self):self.assertEqual(wilson_lower(0,0),0)
 def test_wilson_all(self):self.assertGreater(wilson_lower(20,20),.5)
 def test_wilson_none(self):self.assertEqual(wilson_lower(0,20),0)
 def test_eligible(self):self.assertEqual(evaluate(fixture())["groups"][0]["status"],"review_candidate")
 def test_no_verification_claim(self):self.assertFalse(evaluate(fixture())["verifiedInGame"])
 def test_no_causality_claim(self):self.assertFalse(evaluate(fixture())["groups"][0]["causalityProven"])
 def test_insufficient_sessions(self):
  f=[t for t in fixture() if t["sessionId"]=="A"]
  self.assertEqual(evaluate(f)["groups"][0]["status"],"insufficient_evidence")
 def test_contaminated_control(self):
  f=fixture();f[-1]["after"]=101
  self.assertIn("control_contamination",evaluate(f)["groups"][0]["issues"])
 def test_low_confidence(self):
  f=fixture()
  for t in f:
   if t["kind"]=="action":t["after"]=100
  self.assertIn("low_confidence",evaluate(f)["groups"][0]["issues"])
 def test_duplicate(self):
  f=fixture();f.append(f[0].copy())
  with self.assertRaises(ValueError):evaluate(f)
 def test_mixed_places(self):
  f=fixture();f[-1]["placeId"]=456
  with self.assertRaises(ValueError):evaluate(f)
 def test_bad_schema(self):
  t=trial("A",1,"action");t["schemaVersion"]="bad"
  with self.assertRaises(ValueError):validate(t)
 def test_bad_nan(self):
  t=trial("A",1,"action");t["after"]=float("nan")
  with self.assertRaises(ValueError):validate(t)
 def test_bad_bool(self):
  t=trial("A",1,"action");t["placeId"]=True
  with self.assertRaises(ValueError):validate(t)
 def test_bad_threshold(self):
  with self.assertRaises(ValueError):evaluate(fixture(),threshold=2)
 def test_missing_control(self):
  f=[t for t in fixture() if t["kind"]=="action"]
  self.assertEqual(evaluate(f)["groups"][0]["status"],"insufficient_evidence")
 def test_parse(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"trials.jsonl";p.write_text("\n".join(json.dumps(t) for t in fixture()))
   self.assertEqual(len(parse_logs([p])),40)
 def test_parse_bad(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"trials.jsonl";p.write_text("bad")
   with self.assertRaises(ValueError):parse_logs([p])
 def test_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"out.json";write_report(evaluate(fixture()),p)
   self.assertTrue(p.is_file())
 def test_deterministic(self):self.assertEqual(evaluate(fixture()),evaluate(fixture()))
if __name__=="__main__":unittest.main()
