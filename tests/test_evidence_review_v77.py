import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_review_v77 import analyze,contracts,diff,flatten,identity,read_events
P=85896571713843
def event(i,before=5,after=6,kind="keyboard",capture="s"):
 return {"schemaVersion":"76.event","placeId":P,"captureId":capture,"index":i,"kind":kind,"details":{"key":"E","gameProcessed":False} if kind=="keyboard" else {"uniquePath":[{"name":"Hatch","ordinal":1,"className":"ImageButton"}]},"before":{"🥚 Hatches":before},"after":{"🥚 Hatches":after}}
class Tests(unittest.TestCase):
 def test_unicode(self):self.assertIn("🥚 Hatches",diff({"🥚 Hatches":5},{"🥚 Hatches":6}))
 def test_increase(self):self.assertEqual(diff({"a":1},{"a":2})["a"]["operator"],"increased")
 def test_decrease(self):self.assertEqual(diff({"a":2},{"a":1})["a"]["operator"],"decreased")
 def test_toggle(self):self.assertEqual(diff({"a":True},{"a":False})["a"]["operator"],"toggled")
 def test_equal(self):self.assertEqual(diff({"a":1},{"a":1}),{})
 def test_nested(self):self.assertEqual(flatten({"gui":{"inventory":True}}),{"gui.inventory":True})
 def test_missing(self):self.assertEqual(diff({"a":1},{"b":2}),{})
 def test_no_int_bool(self):self.assertEqual(diff({"a":1},{"a":True}),{})
 def test_draft(self):
  r=analyze([event(1),event(2,6,7),event(3,7,8)])
  self.assertEqual(len(contracts(r,P)["contracts"]),1)
 def test_no_execution(self):self.assertFalse(contracts(analyze([event(1),event(2,6,7),event(3,7,8)]),P)["executionEnabled"])
 def test_one_insufficient(self):self.assertEqual(analyze([event(1)])["groups"][0]["status"],"insufficient_or_ambiguous")
 def test_conflict(self):self.assertEqual(analyze([event(1),event(2,7,6),event(3,7,8)])["groups"][0]["consistentSignals"],[])
 def test_gui_separate(self):self.assertEqual(len(analyze([event(1),event(2,kind="gui")])["groups"]),2)
 def test_identity(self):self.assertTrue(identity(event(1)).startswith("keyboard:E"))
 def test_multiple_signals(self):
  a=[event(i) for i in (1,2,3)]
  for e in a:e["before"]["Bubbles"]=1;e["after"]["Bubbles"]=2
  self.assertEqual(analyze(a)["groups"][0]["status"],"insufficient_or_ambiguous")
 def test_repeated_capture(self):self.assertEqual(analyze([event(1),event(2,6,7),event(3,7,8)])["groups"][0]["observations"],3)
 def test_bad_repeats(self):
  with self.assertRaises(ValueError):analyze([],1)
 def test_parser(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log.txt";p.write_text("LYCOLES_V76_EVENT "+json.dumps(event(1),ensure_ascii=False),encoding="utf-8")
   self.assertEqual(len(read_events([p],P)),1)
 def test_parser_dedup(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log.txt";line="LYCOLES_V76_EVENT "+json.dumps(event(1))
   p.write_text(line+"\n"+line,encoding="utf-8")
   self.assertEqual(len(read_events([p],P)),1)
 def test_parser_conflict(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"log.txt";p.write_text("\n".join("LYCOLES_V76_EVENT "+json.dumps(e) for e in [event(1),event(1,after=10)]))
   with self.assertRaises(ValueError):read_events([p],P)
if __name__=="__main__":unittest.main()
