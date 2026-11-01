import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from input_evidence_v76 import parse,script,summarize
P=85896571713843
def event(i,kind="keyboard",before=5,after=6,processed=False):
 details={"key":"E","gameProcessed":processed} if kind=="keyboard" else {"uniquePath":[{"name":"Button","className":"ImageButton","ordinal":1}]}
 return {"schemaVersion":"76.event","placeId":P,"captureId":"session","index":i,"kind":kind,"details":details,"before":{"Hatches":before},"after":{"Hatches":after}}
def log(e):return "06:42LYCOLES_V76_EVENT "+json.dumps(e)
class Tests(unittest.TestCase):
 def test_script_has_keyboard(self):self.assertIn("UIS.InputBegan:Connect",script(P))
 def test_script_has_gui(self):self.assertIn("node.Activated:Connect",script(P))
 def test_script_no_remote(self):self.assertNotIn(":FireServer(",script(P))
 def test_invalid_place(self):
  with self.assertRaises(ValueError):script(0)
 def test_invalid_delay(self):
  with self.assertRaises(ValueError):script(P,delay=11)
 def test_invalid_window(self):
  with self.assertRaises(ValueError):script(P,link_window=2)
 def test_parse_keyboard(self):self.assertEqual(len(parse([log(event(1))],P)),1)
 def test_parse_gui(self):self.assertEqual(len(parse([log(event(1,"gui"))],P)),1)
 def test_parse_dedup(self):self.assertEqual(len(parse([log(event(1)),log(event(1))],P)),1)
 def test_parse_wrong_place(self):self.assertEqual(parse([log(event(1))],123),[])
 def test_parse_corrupt(self):self.assertEqual(parse(["LYCOLES_V76_EVENT {broken"],P),[])
 def test_conflict(self):
  with self.assertRaises(ValueError):parse([log(event(1)),log(event(1,after=9))],P)
 def test_two_e_increase(self):
  s=summarize([event(1,after=6),event(2,before=6,after=7)])
  self.assertEqual(s["groups"][0]["candidateOutcomes"][0]["operator"],"increased")
 def test_one_e_no_proposal(self):self.assertEqual(summarize([event(1)])["groups"][0]["candidateOutcomes"],[])
 def test_conflicting_e_no_proposal(self):self.assertEqual(summarize([event(1),event(2,before=7,after=6)])["groups"][0]["candidateOutcomes"],[])
 def test_processed_separate(self):self.assertEqual(len(summarize([event(1),event(2,processed=True)])["groups"]),2)
 def test_gui_separate(self):self.assertEqual(len(summarize([event(1),event(2,kind="gui")])["groups"]),2)
 def test_unverified(self):self.assertFalse(summarize([event(1),event(2)])["verified"])
if __name__=="__main__":unittest.main()
