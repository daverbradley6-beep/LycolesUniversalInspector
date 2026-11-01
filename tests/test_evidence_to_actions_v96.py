import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_to_actions_v96 import bridge,generate

PLACE=123456
def review():
 return {"schemaVersion":"91.review","placeId":PLACE,"verifiedInGame":False,
         "candidates":[{"id":"candidate1","status":"review_candidate",
         "input":"keyboard:E:processed=False",
         "outcome":{"stat":"Coins","operator":"increase"}}]}
def mapping():
 return {"schemaVersion":"96.mapping","placeId":PLACE,"developerApproved":True,
         "authorizedUserIds":[10001],"bindings":[{
             "candidateId":"candidate1","observedInput":"keyboard:E:processed=False",
             "expectedOutcome":{"stat":"Coins","operator":"increase"},
             "reviewedByDeveloper":True,
             "action":{"id":"Collect","kind":"increment_stat","stat":"Coins","amount":1}}]}
class BridgeTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(len(bridge(review(),mapping())[0]["actions"]),1)
 def test_provenance(self):self.assertEqual(bridge(review(),mapping())[1][0]["candidateId"],"candidate1")
 def test_no_verification(self):self.assertFalse(bridge(review(),mapping())[1][0]["verifiedInGame"])
 def test_place_mismatch(self):
  m=mapping();m["placeId"]=2
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_review_not_verified(self):
  r=review();r["verifiedInGame"]=True
  with self.assertRaises(ValueError):bridge(r,mapping())
 def test_no_developer_approval(self):
  m=mapping();m["developerApproved"]=False
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_no_binding_approval(self):
  m=mapping();m["bindings"][0]["reviewedByDeveloper"]=False
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_insufficient_evidence(self):
  r=review();r["candidates"][0]["status"]="insufficient_evidence"
  with self.assertRaises(ValueError):bridge(r,mapping())
 def test_reject_input_mismatch(self):
  m=mapping();m["bindings"][0]["observedInput"]="keyboard:W:processed=False"
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_outcome_mismatch(self):
  m=mapping();m["bindings"][0]["expectedOutcome"]={"stat":"Coins","operator":"decrease"}
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_unknown_candidate(self):
  m=mapping();m["bindings"][0]["candidateId"]="missing"
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_duplicate_binding(self):
  m=mapping();m["bindings"].append(m["bindings"][0].copy())
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_invalid_action(self):
  m=mapping();m["bindings"][0]["action"]["kind"]="unknown"
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_invalid_user(self):
  m=mapping();m["authorizedUserIds"]=[]
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_no_bindings(self):
  m=mapping();m["bindings"]=[]
  with self.assertRaises(ValueError):bridge(review(),m)
 def test_reject_wrong_schema(self):
  r=review();r["schemaVersion"]="999.review"
  with self.assertRaises(ValueError):bridge(r,mapping())
 def test_generate(self):
  with tempfile.TemporaryDirectory() as d:
   result=generate(review(),mapping(),d)
   self.assertTrue(result["v95AuditPassed"])
   self.assertTrue((Path(d)/"LycolesActionsV95.server.lua").exists())
 def test_provenance_file(self):
  with tempfile.TemporaryDirectory() as d:
   generate(review(),mapping(),d)
   p=json.loads((Path(d)/"provenance-v96.json").read_text())
   self.assertFalse(p["verifiedInGame"])
   self.assertEqual(p["bindings"][0]["actionId"],"Collect")
 def test_deterministic(self):
  self.assertEqual(bridge(review(),mapping()),bridge(review(),mapping()))
if __name__=="__main__":unittest.main()
