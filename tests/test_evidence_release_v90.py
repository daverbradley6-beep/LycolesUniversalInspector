import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_release_v90 import analyse,canonical,changes,input_key,read_events,write_release
PLACE=85896571713843

def event(key,index,capture,success):
 return {"schemaVersion":"87.event","placeId":PLACE,"captureId":capture,"index":index,
         "kind":"keyboard","details":{"key":key,"gameProcessed":False},
         "observedChanges":[{"stat":"🥚 Hatches","before":1,"after":2}] if success else []}

def fixture():
 return [event(key,100*i+(0 if key=="E" else 50),session,key=="E")
         for session in ("session-a","session-b") for key in ("E","W") for i in range(1,6)]

class EvidenceTests(unittest.TestCase):
 def test_positive(self):
  report=analyse(fixture())
  self.assertEqual(len(report["candidates"]),1)
  self.assertEqual(report["candidates"][0]["status"],"review_candidate")
 def test_negative_control(self):
  self.assertIn("keyboard:W",analyse(fixture())["candidates"][0]["negativeControl"])
 def test_single_session(self):
  x=[e for e in fixture() if e["captureId"]=="session-a"]
  self.assertEqual(analyse(x)["candidates"][0]["status"],"insufficient_evidence")
 def test_contaminated_control(self):
  x=fixture()
  for e in x:
   if e["details"]["key"]=="W" and e["captureId"]=="session-a" and e["index"]==150:
    e["observedChanges"]=[{"stat":"🥚 Hatches","before":1,"after":2}]
  self.assertFalse(any(c["status"]=="review_candidate" for c in analyse(x)["candidates"]))
 def test_candidate_inconsistent(self):
  x=fixture()
  for e in x:
   if e["details"]["key"]=="E" and e["captureId"]=="session-b":
    e["observedChanges"]=[]
  self.assertFalse(any(c["status"]=="review_candidate" for c in analyse(x)["candidates"]))
 def test_no_control(self):
  x=[e for e in fixture() if e["details"]["key"]=="E"]
  self.assertEqual(analyse(x)["candidates"][0]["status"],"insufficient_evidence")
 def test_no_execution(self):
  self.assertFalse(analyse(fixture())["candidates"][0]["executionEnabled"])
 def test_not_verified(self):
  self.assertFalse(analyse(fixture())["verifiedInGame"])
 def test_empty(self):
  self.assertEqual(analyse([])["candidates"],[])
 def test_deterministic(self):
  self.assertEqual(canonical(analyse(fixture())),canonical(analyse(list(reversed(fixture())))))
 def test_invalid_minimum(self):
  with self.assertRaises(ValueError):analyse([],min_per_capture=0)
 def test_invalid_capture_count(self):
  with self.assertRaises(ValueError):analyse([],min_captures=1)
 def test_identity(self):
  self.assertEqual(input_key(event("E",1,"a",True)),"keyboard:E:processed=False")
 def test_change(self):
  self.assertIn(("🥚 Hatches","increase"),changes(event("E",1,"a",True)))
 def test_no_change(self):
  self.assertFalse(changes(event("W",1,"a",False)))
 def test_log_parsing(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.txt"
   path.write_text("LYCOLES_V87_EVENT "+json.dumps(event("E",1,"a",True))+"\n",encoding="utf-8")
   events,sources,warnings=read_events([path],PLACE)
   self.assertEqual(len(events),1)
   self.assertEqual(len(sources),1)
   self.assertEqual(warnings,[])
 def test_log_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.txt"
   line="LYCOLES_V87_EVENT "+json.dumps(event("E",1,"a",True))
   path.write_text(line+"\n"+line+"\n")
   self.assertEqual(len(read_events([path],PLACE)[0]),1)
 def test_log_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.txt"
   path.write_text("\n".join("LYCOLES_V87_EVENT "+json.dumps(e) for e in [event("E",1,"a",True),event("E",1,"a",False)]))
   with self.assertRaises(ValueError):read_events([path],PLACE)
 def test_wrong_place(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"events.txt"
   path.write_text("LYCOLES_V87_EVENT "+json.dumps(event("E",1,"a",True)))
   self.assertEqual(len(read_events([path],PLACE+1)[0]),0)
 def test_release_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   report=analyse(fixture());report["placeId"]=PLACE
   manifest=write_release(d,report,[],[])
   self.assertEqual(len(manifest["outputs"]),2)
   for name,digest in manifest["outputs"].items():
    import hashlib
    self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),digest)
 def test_release_contracts_disabled(self):
  with tempfile.TemporaryDirectory() as d:
   report=analyse(fixture());report["placeId"]=PLACE
   write_release(d,report,[],[])
   contracts=json.loads((Path(d)/"contracts-for-review-v90.json").read_text())["contracts"]
   self.assertFalse(contracts[0]["approved"])
   self.assertFalse(contracts[0]["executionEnabled"])
if __name__=="__main__":unittest.main()
