import sys,unittest,tempfile,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gameplay_workflows_v58 import validate,generate,build
def spec():
 return {"schemaVersion":"58.0","placeId":123,"ownerAuthorized":True,"actions":[
 {"id":"WeightTest","operation":"activate_equipped_tool","toolName":"Weight",
  "expectedValue":{"container":"leaderstats","name":"Strength","minimumDelta":1},
  "timeoutSeconds":3,"repeatCount":3,"cooldownSeconds":0.5}]}
class V58(unittest.TestCase):
 def test_valid(self):
  s=spec();self.assertIs(validate(s),s)
  self.assertEqual(s["actions"][0]["repeatCount"],3)
 def test_reject_unapproved(self):
  s=spec();s["ownerAuthorized"]=False
  with self.assertRaises(ValueError):validate(s)
 def test_reject_unsupported_operation(self):
  s=spec();s["actions"][0]["operation"]="remote_call"
  with self.assertRaises(ValueError):validate(s)
 def test_reject_repeat_overflow(self):
  s=spec();s["actions"][0]["repeatCount"]=21
  with self.assertRaises(ValueError):validate(s)
 def test_reject_delay(self):
  s=spec();s["actions"][0]["cooldownSeconds"]=0
  with self.assertRaises(ValueError):validate(s)
 def test_reject_extra_field(self):
  s=spec();s["actions"][0]["unknown"]=1
  with self.assertRaises(ValueError):validate(s)
 def test_generation(self):
  src=generate(spec())
  for token in ("tool:Activate()","MouseButton1Click","Stop current action","metric replaced","UNVERIFIED","game.PlaceId~=123"):
   self.assertIn(token,src)
  self.assertNotIn("FireServer(",src)
 def test_build(self):
  with tempfile.TemporaryDirectory() as d:
   m=build(spec(),Path(d))
   self.assertEqual(m["actionCount"],1)
   self.assertFalse(m["outcomesVerified"])
   self.assertEqual(len(list(Path(d).iterdir())),2)
 def test_no_mutation(self):
  s=spec();original=copy.deepcopy(s);generate(s)
  self.assertEqual(s,original)
if __name__=="__main__":unittest.main()
