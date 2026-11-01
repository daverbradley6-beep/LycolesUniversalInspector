import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from balanced_discovery_v54 import generate,parse_receipt,analyze,dashboard
def fixture():
 return {"schemaVersion":"54.0","placeId":3623096087,"observations":[
 {"index":1,"entries":[{"path":"Workspace/\"A\"#1@IntValue","className":"IntValue","value":"1"},{"path":"Players","className":"Players"}]},
 {"index":2,"entries":[{"path":"Workspace/\"A\"#1@IntValue","className":"IntValue","value":"2"},{"path":"ReplicatedStorage","className":"ReplicatedStorage"}]}
 ]}
class V54(unittest.TestCase):
 def test_generator(self):
  s=generate(3623096087)
  for token in ('LYCOLES_V54_CHUNK','orderedChildren','perRoot','game.PlaceId~=3623096087','clientReceiptUntrusted=true'):self.assertIn(token,s)
 def test_bounds(self):
  for args in ({"samples":25},{"interval":0},{"cap":100}):
   with self.assertRaises(ValueError):generate(123,**args)
 def test_changes(self):
  r=analyze(fixture(),3623096087)
  self.assertEqual(r["changingPaths"],1)
  self.assertEqual(r["recordedEntries"],4)
  self.assertFalse(r["gameplayAutomationApproved"])
 def test_wrong_place(self):
  with self.assertRaises(ValueError):analyze(fixture(),2)
 def test_chunks(self):
  raw=json.dumps(fixture())
  data="LYCOLES_V54_BEGIN 2\nLYCOLES_V54_CHUNK 1/2 "+raw[:100]+"\nLYCOLES_V54_CHUNK 2/2 "+raw[100:]+"\nLYCOLES_V54_END"
  self.assertEqual(parse_receipt(data),fixture())
 def test_missing_chunk(self):
  with self.assertRaises(ValueError):parse_receipt("LYCOLES_V54_BEGIN 2\nLYCOLES_V54_CHUNK 1/2 {}\nLYCOLES_V54_END")
 def test_duplicate_legacy(self):
  r={"schemaVersion":"53.0","placeId":123,"observations":[{"index":1,"entries":[{"path":"Workspace/\"A\"","className":"Model"},{"path":"Workspace/\"A\"","className":"Model"}]},{"index":2,"entries":[{"path":"Workspace/\"A\"","className":"Model"}]}]}
  report=analyze(r)
  self.assertEqual(report["ambiguousDuplicateOccurrences"],1)
 def test_dashboard(self):
  s=dashboard(analyze(fixture()))
  self.assertIn('ScrollingFrame',s)
  self.assertIn('verified actions',s)
  self.assertNotIn('FireServer',s)
if __name__=="__main__":unittest.main()
