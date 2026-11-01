import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from passive_recorder_v87 import generate,parse,summarize

P=85896571713843
def event(index=1,kind="keyboard",before=1,after=2,capture="abc"):
 return {"schemaVersion":"87.event","placeId":P,"captureId":capture,"index":index,
         "kind":kind,"details":{"key":"E","gameProcessed":False} if kind=="keyboard" else {"path":[{"name":"Button","className":"ImageButton","ordinal":1}]},
         "observedChanges":[{"stat":"🥚 Hatches","before":before,"after":after}],"verified":False}
class Tests(unittest.TestCase):
 def test_generate(self):self.assertIn("85896571713843",generate(P))
 def test_no_activate_method(self):self.assertNotIn(":Activate()",generate(P))
 def test_real_activation_signal(self):self.assertIn("node.Activated:Connect",generate(P).replace("track(node.Activated,","node.Activated:Connect"))
 def test_dynamic_discovery(self):self.assertIn("pg.DescendantAdded",generate(P))
 def test_no_remote_calls(self):self.assertNotIn(":FireServer(",generate(P))
 def test_no_injected_keys(self):self.assertNotIn("VirtualInputManager",generate(P))
 def test_bad_place(self):
  with self.assertRaises(ValueError):generate(0)
 def test_bad_delay(self):
  with self.assertRaises(ValueError):generate(P,0)
 def test_one(self):self.assertEqual(summarize([event()])["totalEvents"],1)
 def test_signal(self):self.assertEqual(summarize([event()])["groups"][0]["signals"][0]["operator"],"increase")
 def test_decrease(self):self.assertEqual(summarize([event(before=2,after=1)])["groups"][0]["signals"][0]["operator"],"decrease")
 def test_capture_count(self):self.assertEqual(summarize([event(),event(index=2,capture="def")])["groups"][0]["independentCaptures"],2)
 def test_not_verified(self):self.assertFalse(summarize([event()])["verified"])
 def test_no_execution(self):self.assertFalse(summarize([event()])["executionEnabled"])
 def test_gui_group(self):self.assertEqual(summarize([event(kind="gui")])["groups"][0]["kind"],"gui")
 def test_empty(self):self.assertEqual(summarize([])["groups"],[])
 def test_parse(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"log.txt";p.write_text("LYCOLES_V87_EVENT "+json.dumps(event())+"\n")
   events,warnings=parse([p],P)
   self.assertEqual(len(events),1)
   self.assertFalse(warnings)
 def test_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"log.txt";line="LYCOLES_V87_EVENT "+json.dumps(event())
   p.write_text(line+"\n"+line+"\n")
   self.assertEqual(len(parse([p],P)[0]),1)
 def test_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"log.txt";p.write_text("LYCOLES_V87_EVENT "+json.dumps(event())+"\nLYCOLES_V87_EVENT "+json.dumps(event(after=5))+"\n")
   with self.assertRaises(ValueError):parse([p],P)
 def test_wrong_place_ignored(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"log.txt";p.write_text("LYCOLES_V87_EVENT "+json.dumps(event())+"\n")
   self.assertEqual(len(parse([p],P+1)[0]),0)
if __name__=="__main__":unittest.main()
