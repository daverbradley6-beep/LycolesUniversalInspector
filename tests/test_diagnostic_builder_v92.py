import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from diagnostic_builder_v92 import build_dashboard,build_backlog,generate,luau_quote

PLACE=85896571713843
def event(key,index,capture,start,match):
 return {"schemaVersion":"87.event","placeId":PLACE,"captureId":capture,
 "index":index,"kind":"keyboard","details":{"key":key,"gameProcessed":False},
 "startedAt":start,"observationDelay":1.5,
 "observedChanges":[{"stat":"Hatches","before":index,"after":index+1}] if match else []}
def fixture():
 return [event(key,100*i+(0 if key=="E" else 50),capture,10+i*4,key=="E")
 for capture in ("a","b") for key in ("E","W") for i in range(1,6)]
def report():
 return {"placeId":PLACE,"candidates":[{"id":"x","input":"keyboard:E:processed=False",
 "outcome":{"stat":"Hatches","operator":"increase"},"status":"review_candidate"}]}
class BuilderTests(unittest.TestCase):
 def test_dashboard(self):self.assertIn("LycolesV92Diagnostics",build_dashboard(report()))
 def test_place_guard(self):self.assertIn(str(PLACE),build_dashboard(report()))
 def test_no_remote(self):self.assertNotIn("FireServer",build_dashboard(report()))
 def test_no_invoke(self):self.assertNotIn("InvokeServer",build_dashboard(report()))
 def test_no_key_injection(self):self.assertNotIn("VirtualInputManager",build_dashboard(report()))
 def test_no_activate_call(self):self.assertNotIn(":Activate()",build_dashboard(report()))
 def test_close(self):self.assertIn("screen:Destroy()",build_dashboard(report()))
 def test_empty(self):self.assertIn("ScreenGui",build_dashboard({"placeId":PLACE,"candidates":[]}))
 def test_invalid_place(self):
  with self.assertRaises(ValueError):build_dashboard({"placeId":0,"candidates":[]})
 def test_invalid_candidates(self):
  with self.assertRaises(ValueError):build_dashboard({"placeId":PLACE,"candidates":None})
 def test_invalid_candidate(self):
  with self.assertRaises(ValueError):build_dashboard({"placeId":PLACE,"candidates":[None]})
 def test_backlog(self):self.assertEqual(len(build_backlog(report())["items"]),1)
 def test_backlog_disabled(self):self.assertFalse(build_backlog(report())["items"][0]["executionEnabled"])
 def test_backlog_unverified(self):self.assertFalse(build_backlog(report())["items"][0]["verifiedInGame"])
 def test_backlog_filters(self):
  r=report();r["candidates"][0]["status"]="insufficient_evidence"
  self.assertEqual(build_backlog(r)["items"],[])
 def test_quote(self):self.assertIn("\\n",luau_quote("a\nb"))
 def test_unicode(self):self.assertIn("🥚",luau_quote("🥚"))
 def test_release(self):
  with tempfile.TemporaryDirectory() as d:
   result=generate(fixture(),PLACE,d)
   self.assertEqual(len(result["files"]),3)
   self.assertFalse(result["verifiedInGame"])
 def test_manifest_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   generate(fixture(),PLACE,d)
   m=json.loads((Path(d)/"manifest-v92.json").read_text())
   for name,digest in m["files"].items():
    self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),digest)
 def test_deterministic(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   generate(fixture(),PLACE,a);generate(list(reversed(fixture())),PLACE,b)
   self.assertEqual((Path(a)/"diagnostics-v92.luau").read_bytes(),
                    (Path(b)/"diagnostics-v92.luau").read_bytes())
if __name__=="__main__":unittest.main()
