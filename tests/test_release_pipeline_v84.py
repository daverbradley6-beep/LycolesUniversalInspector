import hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from release_pipeline_v84 import build,compile_runner,luau_long_string,validate
P=85896571713843
T="if game.PlaceId~=__PLACE__ then return end\nlocal c=H:JSONDecode(__PAYLOAD__)"
def entry(name="hatch",approved=True):
 return {"id":name,"approved":approved,"executionEnabled":False,"input":["gui",[{"name":"🥚 \\ \" ]=]","className":"ImageButton","ordinal":1}]],"expectedSignals":[{"stat":"🥚 Hatches","operator":"increase"}]}
def doc(*items):return {"placeId":P,"contracts":list(items)}
class TestRelease(unittest.TestCase):
 def test_valid(self):self.assertEqual(len(validate(doc(entry()),P)),1)
 def test_unapproved(self):self.assertEqual(len(validate(doc(entry(approved=False)),P)),0)
 def test_wrong_place(self):
  with self.assertRaises(ValueError):validate(doc(entry()),1)
 def test_duplicate(self):
  with self.assertRaises(ValueError):validate(doc(entry(),entry()),P)
 def test_pre_enabled(self):
  x=entry();x["executionEnabled"]=True
  with self.assertRaises(ValueError):validate(doc(x),P)
 def test_invalid_path(self):
  x=entry();x["input"][1]=[]
  with self.assertRaises(ValueError):validate(doc(x),P)
 def test_non_button(self):
  x=entry();x["input"][1][-1]["className"]="Frame"
  with self.assertRaises(ValueError):validate(doc(x),P)
 def test_bad_ordinal(self):
  x=entry();x["input"][1][-1]["ordinal"]=True
  with self.assertRaises(ValueError):validate(doc(x),P)
 def test_bad_signal(self):
  x=entry();x["expectedSignals"][0]["operator"]="remote"
  with self.assertRaises(ValueError):validate(doc(x),P)
 def test_string_path(self):
  x=entry();x["input"][1]=json.dumps(x["input"][1])
  self.assertEqual(len(validate(doc(x),P)),1)
 def test_unicode_preserved(self):self.assertIn("🥚",compile_runner(validate(doc(entry()),P),P,T))
 def test_long_bracket(self):self.assertTrue(luau_long_string("a]]=]b").startswith("[==["))
 def test_payload_literal(self):self.assertIn("JSONDecode([[",compile_runner(validate(doc(entry()),P),P,T))
 def test_template_missing(self):
  with self.assertRaises(ValueError):compile_runner([],P,"bad")
 def test_manifest(self):
  script,m=build(doc(entry()),P,T)
  self.assertEqual(m["runnerSha256"],hashlib.sha256(script.encode()).hexdigest())
 def test_not_verified(self):self.assertFalse(build(doc(entry()),P,T)[1]["verifiedInGame"])
 def test_no_auto(self):self.assertEqual(build(doc(entry()),P,T)[1]["automaticallyExecuted"],0)
 def test_multiple(self):self.assertEqual(build(doc(entry(),entry("inventory")),P,T)[1]["approvedActions"],2)
 def test_max(self):
  with self.assertRaises(ValueError):validate(doc(*[entry("a"+str(i)) for i in range(101)]),P)
 def test_reproducible(self):self.assertEqual(build(doc(entry()),P,T),build(doc(entry()),P,T))
if __name__=="__main__":unittest.main()
