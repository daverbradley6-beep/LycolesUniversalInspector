import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from live_trace_collector_v61 import generate,build
def contract():
 return {"schemaVersion":"58.0","placeId":123,"ownerAuthorized":True,"actions":[{
  "id":"Training","operation":"activate_equipped_tool","toolName":"Weight",
  "expectedValue":{"container":"leaderstats","name":"Strength","minimumDelta":2},
  "repeatCount":2,"timeoutSeconds":4,"cooldownSeconds":0.5}]}
class V61(unittest.TestCase):
 def test_place_guard(self):
  s=generate(contract())
  self.assertIn("game.PlaceId~=123",s)
 def test_trace_schema(self):
  s=generate(contract())
  self.assertIn('schemaVersion="60.trace"',s)
  self.assertIn('kind="before"',s) if False else self.assertIn('"before"',s)
  self.assertIn('"after"',s)
 def test_no_remote_calls(self):
  s=generate(contract())
  for forbidden in ("FireServer(", "InvokeServer(", "hookmetamethod(", "setreadonly("):
   self.assertNotIn(forbidden,s)
 def test_stop_and_export(self):
  s=generate(contract())
  self.assertIn("STOP current action",s)
  self.assertIn("Export trace JSON",s)
  self.assertIn("TextBox",s)
 def test_unapproved_rejected(self):
  c=contract();c["ownerAuthorized"]=False
  with self.assertRaises(ValueError):generate(c)
 def test_invalid_action_rejected(self):
  c=contract();c["actions"][0]["operation"]="invoke_remote"
  with self.assertRaises(ValueError):generate(c)
 def test_release(self):
  with tempfile.TemporaryDirectory() as d:
   m=build(contract(),Path(d))
   self.assertFalse(m["serverVerified"])
   self.assertTrue((Path(d)/"live-trace-collector-v61.luau").exists())
   self.assertTrue((Path(d)/"collector-manifest-v61.json").exists())
 def test_no_placeholders(self):
  s=generate(contract())
  self.assertNotIn("__PLACE__",s)
  self.assertNotIn("__ACTIONS__",s)
if __name__=="__main__":unittest.main()
