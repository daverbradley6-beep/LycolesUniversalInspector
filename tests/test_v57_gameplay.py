import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gameplay_contracts_v57 import validate,generate,compile_release
def fixture():
 return {"schemaVersion":"57.0","placeId":123,"ownerAuthorized":True,"actions":[
  {"id":"TestWeight","operation":"activate_equipped_tool","toolName":"Weight",
   "expectedValue":{"container":"leaderstats","name":"Strength","minimumDelta":1},"timeoutSeconds":3}]}
class V57(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(fixture())["placeId"],123)
 def test_no_authorization(self):
  s=fixture();s["ownerAuthorized"]=False
  with self.assertRaises(ValueError):validate(s)
 def test_reject_unknown_operation(self):
  s=fixture();s["actions"][0]["operation"]="invoke_remote"
  with self.assertRaises(ValueError):validate(s)
 def test_reject_missing_outcome(self):
  s=fixture();del s["actions"][0]["expectedValue"]
  with self.assertRaises(ValueError):validate(s)
 def test_reject_duplicate(self):
  s=fixture();s["actions"].append(dict(s["actions"][0]))
  with self.assertRaises(ValueError):validate(s)
 def test_reject_invalid_delta(self):
  s=fixture();s["actions"][0]["expectedValue"]["minimumDelta"]=0
  with self.assertRaises(ValueError):validate(s)
 def test_generate(self):
  script=generate(fixture())
  for term in ("tool:Activate()","metric.Value","UNVERIFIED","UNSUPPORTED","game.PlaceId~=123","MouseButton1Click"):self.assertIn(term,script)
  for term in ("FireServer(", "InvokeServer(", "hookmetamethod("):self.assertNotIn(term,script)
 def test_output(self):
  with tempfile.TemporaryDirectory() as d:
   summary=compile_release(fixture(),Path(d))
   self.assertFalse(summary["serverOutcomeVerified"])
   self.assertEqual(len(list(Path(d).iterdir())),2)
 def test_reject_unknown_fields(self):
  s=fixture();s["actions"][0]["script"]="print('hello')"
  with self.assertRaises(ValueError):validate(s)
if __name__=="__main__":unittest.main()
