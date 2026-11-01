import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from client_observer_compiler_v100 import validate,compile_gui,generate,audit

def report():
 return {"schemaVersion":"100.client-observations","placeId":85896571713843,
         "observations":[{"id":"Coins","path":["PlayerGui","HUD","Coins"],
         "property":"Text","label":"Coin display"},
         {"id":"Egg","path":["Workspace","Eggs","BasicEgg"],
         "property":"Name"}]}
class ObserverTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(report())["placeId"],85896571713843)
 def test_compiles(self):self.assertIn("LycolesObserverV100",compile_gui(report()))
 def test_place_guard(self):self.assertIn("game.PlaceId",compile_gui(report()))
 def test_close(self):self.assertIn("gui:Destroy()",compile_gui(report()))
 def test_read_only(self):
  script=compile_gui(report())
  for token in ("FireServer","InvokeServer","VirtualInputManager","loadstring","HttpGet","hookmetamethod"):
   self.assertNotIn(token,script)
 def test_no_arbitrary_path(self):
  x=report();x["observations"][0]["path"][0]="HttpService"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_duplicate(self):
  x=report();x["observations"][1]["id"]="Coins"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_property(self):
  x=report();x["observations"][0]["property"]="Parent"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_empty(self):
  x=report();x["observations"]=[]
  with self.assertRaises(ValueError):validate(x)
 def test_reject_place(self):
  x=report();x["placeId"]=True
  with self.assertRaises(ValueError):validate(x)
 def test_reject_invalid_component(self):
  x=report();x["observations"][0]["path"][1]="Bad\nName"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_duplicate_id(self):
  x=report();x["observations"][1]["id"]=x["observations"][0]["id"]
  with self.assertRaises(ValueError):validate(x)
 def test_reject_oversized(self):
  x=report();x["observations"]*=76
  with self.assertRaises(ValueError):validate(x)
 def test_generate_audit(self):
  with tempfile.TemporaryDirectory() as d:
   generate(report(),d)
   self.assertTrue(audit(d)["ok"])
 def test_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   generate(report(),d)
   with (Path(d)/"LycolesObserverV100.client.lua").open("a") as f:f.write("tamper")
   self.assertFalse(audit(d)["ok"])
 def test_missing(self):
  with tempfile.TemporaryDirectory() as d:
   generate(report(),d)
   (Path(d)/"observations-v100.json").unlink()
   self.assertFalse(audit(d)["ok"])
 def test_deterministic(self):self.assertEqual(compile_gui(report()),compile_gui(report()))
 def test_no_verification_claim(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(generate(report(),d)["verifiedInGame"])
if __name__=="__main__":unittest.main()
