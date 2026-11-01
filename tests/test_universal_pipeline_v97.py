import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from universal_pipeline_v97 import proposal,plan,write_stage,audit_stage,run

PLACE=123456
def event(key,index,capture,start,match):
 return {"schemaVersion":"87.event","placeId":PLACE,"captureId":capture,
 "index":index,"kind":"keyboard","details":{"key":key,"gameProcessed":False},
 "startedAt":start,"observationDelay":1.5,
 "observedChanges":[{"stat":"Coins","before":index,"after":index+1}] if match else []}
def events():
 return [event(key,100*i+(0 if key=="E" else 50),capture,10+i*4,key=="E")
 for capture in ("a","b") for key in ("E","W") for i in range(1,6)]
def review():
 return {"schemaVersion":"91.review","placeId":PLACE,"verifiedInGame":False,
         "candidates":[{"id":"c1","status":"review_candidate",
         "input":"keyboard:E:processed=False","outcome":{"stat":"Coins","operator":"increase"}},
         {"id":"c2","status":"insufficient_evidence",
         "input":"keyboard:W:processed=False","outcome":{"stat":"Coins","operator":"increase"}}],
         "temporalAttribution":{"total":20,"retained":20,"quarantined":0}}
def mapping():
 return {"schemaVersion":"96.mapping","placeId":PLACE,"developerApproved":True,
         "authorizedUserIds":[10001],"bindings":[{
             "candidateId":"c1","observedInput":"keyboard:E:processed=False",
             "expectedOutcome":{"stat":"Coins","operator":"increase"},
             "reviewedByDeveloper":True,
             "action":{"id":"Collect","kind":"increment_stat","stat":"Coins","amount":1}}]}
class PipelineTests(unittest.TestCase):
 def test_proposal(self):self.assertEqual(len(proposal(review())["bindings"]),1)
 def test_no_auto_approval(self):self.assertFalse(proposal(review())["developerApproved"])
 def test_no_auto_action(self):self.assertIsNone(proposal(review())["bindings"][0]["action"])
 def test_no_execution(self):self.assertFalse(proposal(review())["executionEnabled"])
 def test_plan(self):self.assertEqual(plan(review())["eligibleCandidateCount"],1)
 def test_plan_quarantine(self):self.assertEqual(plan(review())["quarantined"],0)
 def test_empty(self):
  r=review();r["candidates"]=[]
  self.assertEqual(proposal(r)["bindings"],[])
 def test_bad_review(self):
  with self.assertRaises(ValueError):proposal({"candidates":None})
 def test_stage(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d)
   self.assertTrue(audit_stage(d)["ok"])
 def test_stage_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d)
   (Path(d)/"proposal-v97.json").write_text("{}")
   self.assertFalse(audit_stage(d)["ok"])
 def test_stage_missing(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d)
   (Path(d)/"plan-v97.json").unlink()
   self.assertFalse(audit_stage(d)["ok"])
 def test_stage_manifest_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d)
   m=Path(d)/"manifest-v97.json"
   obj=json.loads(m.read_text());obj["verifiedInGame"]=True;m.write_text(json.dumps(obj))
   self.assertFalse(audit_stage(d)["ok"])
 def test_stage_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   m=write_stage(review(),d)
   for name,digest in m["files"].items():
    self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),digest)
 def test_deterministic(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   write_stage(review(),a);write_stage(review(),b)
   self.assertEqual((Path(a)/"manifest-v97.json").read_bytes(),(Path(b)/"manifest-v97.json").read_bytes())
 def test_run_no_mapping(self):
  with tempfile.TemporaryDirectory() as d:
   result=run(events(),PLACE,d)
   self.assertTrue(result["stagingAuditPassed"])
   self.assertFalse(result["approvedStudioCompilation"])
 def test_run_approved(self):
  with tempfile.TemporaryDirectory() as d:
   result=run(events(),PLACE,d,mapping())
   self.assertTrue(result["approvedStudioCompilation"])
   self.assertTrue((Path(d)/"approved-studio"/"LycolesActionsV95.server.lua").is_file())
 def test_run_bad_mapping(self):
  with tempfile.TemporaryDirectory() as d:
   m=mapping();m["developerApproved"]=False
   with self.assertRaises(ValueError):run(events(),PLACE,d,m)
 def test_run_unverified(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(run(events(),PLACE,d)["verifiedInGame"])
if __name__=="__main__":
 unittest.main()
