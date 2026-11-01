import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from contract_pipeline_v73 import compile_contracts,generate
PLACE=85896571713843
SEG=[{"name":"ScreenGui","className":"ScreenGui","ordinal":1},{"name":"HUD","className":"Frame","ordinal":1},{"name":"Button","className":"TextButton","ordinal":2}]
def catalog():
 return {"schemaVersion":"72.candidates","placeId":PLACE,"sourceComplete":True,"candidates":[{"id":"ui_1","label":"Hatch","ambiguousPath":True,"action":{"type":"local_gui_activate","className":"TextButton","path":["ScreenGui","HUD","Button"],"uniquePath":copy.deepcopy(SEG)}}]}
def outcomes():
 return {"schemaVersion":"73.outcomes","placeId":PLACE,"outcomes":{"ui_1":{"type":"leaderstat","stat":"Hatches","operator":"increased","target":None,"timeoutSeconds":5}}}
class TestV73(unittest.TestCase):
 def test_compiles(self):self.assertEqual(len(compile_contracts(catalog(),outcomes(),PLACE)["contracts"]),1)
 def test_unverified(self):self.assertFalse(compile_contracts(catalog(),outcomes(),PLACE)["actionContractsVerified"])
 def test_luau(self):
  s=generate(compile_contracts(catalog(),outcomes(),PLACE))
  self.assertIn("target:Activate()",s)
  self.assertIn("seg.ordinal",s)
 def test_no_remote(self):
  s=generate(compile_contracts(catalog(),outcomes(),PLACE))
  self.assertNotIn(":FireServer(",s)
 def test_wrong_place(self):
  with self.assertRaisesRegex(ValueError,"place ID"):compile_contracts(catalog(),outcomes(),123)
 def test_missing_outcome(self):
  o=outcomes();o["outcomes"]={}
  self.assertEqual(compile_contracts(catalog(),o,PLACE)["contracts"],[])
 def test_unknown_candidate(self):
  o=outcomes();o["outcomes"]={"missing":o["outcomes"]["ui_1"]}
  self.assertEqual(compile_contracts(catalog(),o,PLACE)["rejected"][0]["reason"],"unknown candidate")
 def test_ambiguous_without_unique(self):
  c=catalog();c["candidates"][0]["action"]["uniquePath"]=None
  self.assertIn("ambiguous",compile_contracts(c,outcomes(),PLACE)["rejected"][0]["reason"])
 def test_bad_unique(self):
  c=catalog();c["candidates"][0]["action"]["uniquePath"][-1]["ordinal"]=0
  self.assertIn("uniquePath",compile_contracts(c,outcomes(),PLACE)["rejected"][0]["reason"])
 def test_invalid_outcome(self):
  o=outcomes();o["outcomes"]["ui_1"]["timeoutSeconds"]=999
  self.assertIn("timeout",compile_contracts(catalog(),o,PLACE)["rejected"][0]["reason"])
 def test_deterministic(self):
  d=compile_contracts(catalog(),outcomes(),PLACE)
  self.assertEqual(generate(d),generate(d))
 def test_partial_source_provenance(self):
  c=catalog();c["sourceComplete"]=False
  self.assertFalse(compile_contracts(c,outcomes(),PLACE)["sourceComplete"])
if __name__=="__main__":unittest.main()
