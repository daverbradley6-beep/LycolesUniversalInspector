import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from state_capture_v78 import generate,flatten,changes,parse_logs,analyze
P=85896571713843
def event(i,before=5,after=6):
 return {"schemaVersion":"78.event","placeId":P,"captureId":"s","index":i,"kind":"keyboard","details":{"key":"E","gameProcessed":False},"before":{"leaderstats":{"🥚 Hatches":before}},"after":{"leaderstats":{"🥚 Hatches":after}}}
class Tests(unittest.TestCase):
 def test_generate(self):self.assertIn(str(P),generate(P))
 def test_keyboard(self):self.assertIn("UIS.InputBegan:Connect",generate(P))
 def test_gui(self):self.assertIn("v.Activated:Connect",generate(P))
 def test_tools(self):self.assertIn("backpackCount",generate(P))
 def test_character(self):self.assertIn("HumanoidRootPart",generate(P))
 def test_gui_state(self):self.assertIn("v.Visible",generate(P))
 def test_no_remote(self):self.assertNotIn(":FireServer(",generate(P))
 def test_bad_place(self):
  with self.assertRaises(ValueError):generate(0)
 def test_flatten(self):self.assertEqual(flatten({"a":{"b":2}}),{"a.b":2})
 def test_unicode(self):self.assertIn("leaderstats.🥚 Hatches",changes(event(1)["before"],event(1)["after"]))
 def test_increase(self):self.assertEqual(changes({"a":1},{"a":2})["a"],"increase")
 def test_decrease(self):self.assertEqual(changes({"a":2},{"a":1})["a"],"decrease")
 def test_toggle(self):self.assertEqual(changes({"a":True},{"a":False})["a"],"toggle")
 def test_equal(self):self.assertEqual(changes({"a":1},{"a":1}),{})
 def test_mismatch(self):self.assertEqual(changes({"a":1},{"a":True}),{})
 def test_missing(self):self.assertEqual(changes({"a":1},{"b":2}),{})
 def test_candidate(self):self.assertEqual(analyze([event(1),event(2,6,7),event(3,7,8)])["groups"][0]["status"],"review_candidate")
 def test_conflict(self):self.assertEqual(analyze([event(1),event(2,7,6),event(3)])["groups"][0]["consistentSignals"],[])
 def test_insufficient(self):self.assertEqual(analyze([event(1)])["groups"][0]["consistentSignals"],[])
 def test_not_verified(self):self.assertFalse(analyze([event(1)])["verified"])
 def test_no_execution(self):self.assertFalse(analyze([event(1)])["executionEnabled"])
 def test_bad_minimum(self):
  with self.assertRaises(ValueError):analyze([],1)
 def test_parser(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log";p.write_text("LYCOLES_V78_EVENT "+json.dumps(event(1),ensure_ascii=False),encoding="utf-8")
   self.assertEqual(len(parse_logs([p],P)),1)
 def test_dedup(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log";line="LYCOLES_V78_EVENT "+json.dumps(event(1));p.write_text(line+"\n"+line)
   self.assertEqual(len(parse_logs([p],P)),1)
 def test_collision(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log";p.write_text("\n".join("LYCOLES_V78_EVENT "+json.dumps(e) for e in [event(1),event(1,after=9)]))
   with self.assertRaises(ValueError):parse_logs([p],P)
if __name__=="__main__":unittest.main()
