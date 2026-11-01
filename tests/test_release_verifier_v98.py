import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from release_verifier_v98 import verify_release,verify_reproducibility
from universal_pipeline_v97 import write_stage

def review():
 return {"schemaVersion":"91.review","placeId":123456,"verifiedInGame":False,
         "candidates":[{"id":"c1","status":"review_candidate",
         "input":"keyboard:E:processed=False",
         "outcome":{"stat":"Coins","operator":"increase"}},
         {"id":"c2","status":"insufficient_evidence",
         "input":"keyboard:W:processed=False",
         "outcome":{"stat":"Coins","operator":"increase"}}],
         "temporalAttribution":{"total":20,"retained":20,"quarantined":0}}
class VerifierTests(unittest.TestCase):
 def test_valid(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);self.assertTrue(verify_release(d)["ok"])
 def test_missing_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(verify_release(d)["ok"])
 def test_missing_file(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);(Path(d)/"plan-v97.json").unlink()
   self.assertFalse(verify_release(d)["ok"])
 def test_tampered_file(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);(Path(d)/"proposal-v97.json").write_text("{}")
   self.assertFalse(verify_release(d)["ok"])
 def test_wrong_place(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);p=Path(d)/"manifest-v97.json"
   m=json.loads(p.read_text());m["placeId"]=999;p.write_text(json.dumps(m))
   self.assertFalse(verify_release(d)["ok"])
 def test_manifest_claim(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);p=Path(d)/"manifest-v97.json"
   m=json.loads(p.read_text());m["verifiedInGame"]=True;p.write_text(json.dumps(m))
   self.assertFalse(verify_release(d)["ok"])
 def test_empty_candidates(self):
  with tempfile.TemporaryDirectory() as d:
   r=review();r["candidates"]=[];write_stage(r,d)
   self.assertTrue(verify_release(d)["ok"])
 def test_reproducible(self):
  self.assertTrue(verify_reproducibility(review(),write_stage)["ok"])
 def test_bad_json(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d);(Path(d)/"manifest-v97.json").write_text("{")
   self.assertFalse(verify_release(d)["ok"])
 def test_unverified(self):
  with tempfile.TemporaryDirectory() as d:
   write_stage(review(),d)
   self.assertFalse(verify_release(d)["verifiedInGame"])
if __name__=="__main__":unittest.main()
