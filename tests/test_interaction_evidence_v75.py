import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from interaction_evidence_v75 import script,events,propose
PLACE=85896571713843
PATH=[{"name":"HUD","className":"ScreenGui","ordinal":1},{"name":"Hatch","className":"TextButton","ordinal":1}]
def catalog():
 return {"schemaVersion":"72.candidates","placeId":PLACE,"candidates":[{"id":"ui_1","action":{"uniquePath":PATH}}]}
def event(i,before=0,after=1,path=PATH):
 return {"schemaVersion":"75.event","placeId":PLACE,"captureId":"a","index":i,"uniquePath":path,"before":{"Hatches":before},"after":{"Hatches":after}}
class Tests(unittest.TestCase):
 def test_script(self):self.assertIn("LYCOLES_V75_EVENT",script(PLACE))
 def test_no_remote(self):self.assertNotIn(":FireServer(",script(PLACE))
 def test_place_guard(self):
  with self.assertRaises(ValueError):script(0)
 def test_delay_guard(self):
  with self.assertRaises(ValueError):script(PLACE,delay=20)
 def test_parse(self):
  x=events("06:00LYCOLES_V75_EVENT "+json.dumps(event(1)),PLACE)
  self.assertEqual(len(x),1)
 def test_dedup(self):
  s="LYCOLES_V75_EVENT "+json.dumps(event(1))
  self.assertEqual(len(events(s+"\n"+s,PLACE)),1)
 def test_bad_json(self):self.assertEqual(events("LYCOLES_V75_EVENT {bad",PLACE),[])
 def test_two_repeats(self):
  d=propose(catalog(),[event(1,0,1),event(2,1,2)],PLACE)
  self.assertEqual(d["proposals"]["ui_1"]["operator"],"increased")
 def test_one_repeat(self):self.assertEqual(propose(catalog(),[event(1)],PLACE)["proposals"],{})
 def test_conflicting_direction(self):
  self.assertEqual(propose(catalog(),[event(1,0,1),event(2,2,1)],PLACE)["proposals"],{})
 def test_no_match(self):
  e=event(1,path=[{"name":"Different","className":"TextButton","ordinal":1}])
  self.assertEqual(propose(catalog(),[e,e],PLACE)["proposals"],{})
 def test_unverified(self):
  self.assertFalse(propose(catalog(),[event(1,0,1),event(2,1,2)],PLACE)["verified"])
if __name__=="__main__":unittest.main()
