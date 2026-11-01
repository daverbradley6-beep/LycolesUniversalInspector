import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from live_discovery_v53 import generate,analyze

def receipt():
 return {"schemaVersion":"53.0","placeId":123,"observations":[
  {"index":1,"truncated":False,"entries":[{"path":"Workspace","className":"Workspace"},{"path":"Workspace/\"A.B\"","className":"IntValue","value":"1"}]},
  {"index":2,"truncated":False,"entries":[{"path":"Workspace","className":"Workspace"},{"path":"Workspace/\"A.B\"","className":"IntValue","value":"2"},{"path":"Players","className":"Players"}]}
 ]}
class V53(unittest.TestCase):
 def test_generator(self):
  s=generate(123)
  for token in ('LYCOLES_V53_BEGIN','GetChildren()','JSONEncode(child.Name)','game.PlaceId~=123','clientReceiptUntrusted=true'):self.assertIn(token,s)
 def test_no_number_concat(self):self.assertNotIn('..11..',generate(123))
 def test_bounds(self):
  for args in ({"seconds":121},{"period":0},{"max_objects":10000}):
   with self.assertRaises(ValueError):generate(123,**args)
 def test_analysis(self):
  r=analyze(receipt(),123)
  self.assertEqual(r["discoveredPaths"],3)
  self.assertEqual(r["changingPaths"],2)
  self.assertFalse(r["gameplayAutomationApproved"])
  self.assertTrue(next(x for x in r["paths"] if 'A.B' in x["path"])["valueChanged"])
 def test_wrong_place(self):
  with self.assertRaises(ValueError):analyze(receipt(),999)
 def test_duplicate(self):
  r=receipt();r["observations"][0]["entries"].append(r["observations"][0]["entries"][0])
  with self.assertRaises(ValueError):analyze(r)
 def test_invalid_sample(self):
  r=receipt();r["observations"][1]["index"]=3
  with self.assertRaises(ValueError):analyze(r)
 def test_truncation(self):
  r=receipt();r["observations"][0]["truncated"]=True
  self.assertEqual(analyze(r)["truncatedSamples"],1)
if __name__=="__main__":unittest.main()
