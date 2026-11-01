import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_to_contracts_v85 import convert,make_id,review_digest
P=85896571713843
def row(id="hatch"):
 return {"id":id,"attempts":4,"activationRequests":3,"independentCaptures":2,"expectedMatches":2,"expectedSignals":[{"stat":"🥚 Hatches","operator":"increase"}]}
def review(*rows):return {"schemaVersion":"83.review","actions":list(rows)}
def catalog(*items):return {"placeId":P,"contracts":list(items)}
def item(id="hatch",path=None):
 return {"id":id,"approved":True,"input":["gui",path if path is not None else [{"name":"Button","className":"ImageButton","ordinal":1}]]}
class Tests(unittest.TestCase):
 def test_basic(self):self.assertEqual(len(convert(review(row()),catalog(item()),P)["contracts"]),1)
 def test_no_auto_approval(self):self.assertFalse(convert(review(row()),catalog(item()),P)["contracts"][0]["approved"])
 def test_no_auto_execution(self):self.assertEqual(convert(review(row()),catalog(item()),P)["automaticallyExecuted"],0)
 def test_no_verification(self):self.assertFalse(convert(review(row()),catalog(item()),P)["contracts"][0]["evidence"]["verifiedInGame"])
 def test_expected(self):self.assertEqual(convert(review(row()),catalog(item()),P)["contracts"][0]["expectedSignals"][0]["stat"],"🥚 Hatches")
 def test_capture_count(self):self.assertEqual(convert(review(row()),catalog(item()),P)["contracts"][0]["evidence"]["independentCaptures"],2)
 def test_missing(self):self.assertEqual(len(convert(review(row()),catalog(),P)["skipped"]),1)
 def test_unsupported(self):
  x=item();x["input"][0]="keyboard"
  self.assertEqual(convert(review(row()),catalog(x),P)["skipped"][0]["reason"],"unsupported input")
 def test_bad_json_path(self):
  x=item(path="{oops")
  self.assertEqual(len(convert(review(row()),catalog(x),P)["skipped"]),1)
 def test_json_path(self):
  x=item(path='[{"name":"Button","className":"ImageButton","ordinal":1}]')
  self.assertEqual(len(convert(review(row()),catalog(x),P)["contracts"]),1)
 def test_wrong_place(self):
  with self.assertRaises(ValueError):convert(review(row()),catalog(item()),2)
 def test_bad_schema(self):
  with self.assertRaises(ValueError):convert({"actions":[]},catalog(),P)
 def test_duplicate_catalog(self):
  with self.assertRaises(ValueError):convert(review(row()),catalog(item(),item()),P)
 def test_id_prefix(self):self.assertTrue(make_id("123",set()).startswith("action_"))
 def test_id_dedup(self):
  seen=set();self.assertNotEqual(make_id("x",seen),make_id("x",seen))
 def test_empty(self):self.assertEqual(convert(review(),catalog(),P)["contracts"],[])
 def test_determinism(self):
  a=convert(review(row()),catalog(item()),P);b=convert(review(row()),catalog(item()),P)
  self.assertEqual(review_digest(a),review_digest(b))
 def test_id_sanitization(self):self.assertEqual(make_id("egg hatch",set()),"egg_hatch")
 def test_multiple(self):
  self.assertEqual(len(convert(review(row(),row("shop")),catalog(item(),item("shop")),P)["contracts"]),2)
 def test_non_gui_skipped(self):
  x=item();x["input"]=["remote",[]]
  self.assertEqual(len(convert(review(row()),catalog(x),P)["contracts"]),0)
if __name__=="__main__":unittest.main()
