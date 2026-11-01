import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from temporal_attribution_v91 import valid_window,quarantine_overlaps,release
PLACE=85896571713843

def event(key,index,capture,start,match=True):
 return {"schemaVersion":"87.event","placeId":PLACE,"captureId":capture,
 "index":index,"kind":"keyboard","details":{"key":key,"gameProcessed":False},
 "startedAt":start,"observationDelay":1.5,
 "observedChanges":[{"stat":"Hatches","before":index,"after":index+1}] if match else []}

def fixture():
 x=[]
 for capture in ("a","b"):
  for i in range(5):
   x.append(event("E",i+1,capture,10+i*4))
   x.append(event("W",i+101,capture,12+i*4,False))
 return x

class AttributionTests(unittest.TestCase):
 def test_valid_window(self):self.assertEqual(valid_window(event("E",1,"a",10)),(10,11.5))
 def test_missing_timing(self):
  e=event("E",1,"a",10);del e["startedAt"]
  self.assertIsNone(valid_window(e))
 def test_overlap_same_transition(self):
  a=event("E",1,"a",10)
  b=event("W",2,"a",10.5)
  b["observedChanges"]=a["observedChanges"]
  clean,d=quarantine_overlaps([a,b])
  self.assertEqual(len(clean),0)
  self.assertEqual(d["quarantined"],2)
 def test_no_overlap(self):
  a=event("E",1,"a",10);b=event("W",2,"a",12)
  b["observedChanges"]=a["observedChanges"]
  self.assertEqual(len(quarantine_overlaps([a,b])[0]),2)
 def test_different_transition(self):
  self.assertEqual(len(quarantine_overlaps([event("E",1,"a",10),event("E",2,"a",10.5)])[0]),2)
 def test_capture_isolation(self):
  a=event("E",1,"a",10);b=event("E",1,"b",10)
  self.assertEqual(len(quarantine_overlaps([a,b])[0]),2)
 def test_unknown_timing_quarantine(self):
  a=event("E",1,"a",10);a.pop("startedAt")
  clean,d=quarantine_overlaps([a])
  self.assertEqual(len(clean),0)
  self.assertEqual(d["missingOrInvalidTiming"],1)
 def test_clean_candidate(self):
  r=release(fixture(),PLACE)
  self.assertEqual(r["candidates"][0]["status"],"review_candidate")
 def test_contaminated_control_recovered(self):
  x=fixture()
  target=next(e for e in x if e["captureId"]=="b" and e["details"]["key"]=="E")
  extra=event("W",999,"b",target["startedAt"]+.2)
  extra["observedChanges"]=target["observedChanges"]
  x.append(extra)
  r=release(x,PLACE)
  self.assertEqual(r["temporalAttribution"]["quarantined"],2)
  self.assertEqual(r["candidates"][0]["status"],"review_candidate")
 def test_no_execution(self):
  r=release(fixture(),PLACE)
  self.assertFalse(r["candidates"][0]["executionEnabled"])
 def test_no_causal_claim(self):
  self.assertFalse(release(fixture(),PLACE)["candidates"][0]["causalityProven"])
 def test_no_verification(self):
  self.assertFalse(release(fixture(),PLACE)["verifiedInGame"])
 def test_empty(self):
  self.assertEqual(release([],PLACE)["candidates"],[])
 def test_no_cross_capture_control(self):
  x=[e for e in fixture() if e["details"]["key"]=="E" or e["captureId"]=="a"]
  self.assertEqual(release(x,PLACE)["candidates"][0]["status"],"insufficient_evidence")
 def test_three_captures(self):
  x=fixture()+[event("E",i+1,"c",10+i*4) for i in range(5)]
  self.assertTrue(release(x,PLACE)["candidates"])
 def test_invalid_minimum(self):
  with self.assertRaises(ValueError):release(fixture(),PLACE,0)
 def test_independent_capture(self):
  self.assertEqual(release(fixture(),PLACE)["candidates"][0]["captureCount"],2)
 def test_conflict_diagnostics(self):
  a=event("E",1,"a",10);b=event("W",2,"a",10.1)
  b["observedChanges"]=a["observedChanges"]
  self.assertEqual(quarantine_overlaps([a,b])[1]["conflicts"][0]["reason"],"same_outcome_overlapping_windows")
if __name__=="__main__":unittest.main()
