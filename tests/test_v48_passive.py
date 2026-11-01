import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from passive_observer_v48 import generate,analyze
M={"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"f","features":[{"id":"inspect-training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A"]}]}
def receipt(values):
 return {"schemaVersion":"48.0","placeId":123,"scanId":"s","sourceFingerprint":"f","observations":[{"index":i+1,"checks":[{"path":"Workspace.A","present":True,"className":"IntValue","value":v}]} for i,v in enumerate(values)]}
class V48(unittest.TestCase):
 def test_generate(self):
  s=generate(M)
  for x in ("LYCOLES_V48_BEGIN","task.spawn(function()","ValueBase","game.PlaceId","SAMPLE_COUNT"):self.assertTrue(x in s if x!="SAMPLE_COUNT" else x not in s)
 def test_no_numeric_concat_lexing(self):
  s=generate(M)
  self.assertIn('tostring(16).." samples"',s)
  self.assertNotIn('..16..',s)
  self.assertIn('tostring(index).."/"..tostring(16)',s)
 def test_default_count(self):self.assertIn("for index=1, 16 do",generate(M))
 def test_custom_count(self):self.assertIn("for index=1, 4 do",generate(M,seconds=6,period=2))
 def test_invalid_interval(self):
  with self.assertRaises(ValueError):generate(M,period=0)
 def test_invalid_duration(self):
  with self.assertRaises(ValueError):generate(M,seconds=121)
 def test_changes(self):
  r=analyze(M,receipt(["1","2","2"]))
  self.assertEqual(r["paths"]["Workspace.A"]["stateTransitions"],1)
  self.assertTrue(r["paths"]["Workspace.A"]["valueChanged"])
 def test_stable(self):self.assertEqual(analyze(M,receipt(["1","1"]))["paths"]["Workspace.A"]["classification"],"stable-visible")
 def test_no_approval(self):self.assertFalse(analyze(M,receipt(["1","2"]))["gameplayAutomationApproved"])
 def test_bad_identity(self):
  with self.assertRaises(ValueError):analyze(M,{**receipt(["1","2"]),"scanId":"bad"})
 def test_bad_schema(self):
  with self.assertRaises(ValueError):analyze(M,{**receipt(["1","2"]),"schemaVersion":"44.0"})
 def test_duplicate(self):
  r=receipt(["1","2"]);r["observations"][0]["checks"].append(r["observations"][0]["checks"][0])
  with self.assertRaises(ValueError):analyze(M,r)
 def test_missing_sample(self):
  with self.assertRaises(ValueError):analyze(M,receipt(["1"]))
 def test_bad_value(self):
  r=receipt(["1","2"]);r["observations"][0]["checks"][0]["value"]="x"*121
  with self.assertRaises(ValueError):analyze(M,r)
 def test_no_gameplay_remote(self):self.assertNotIn("FireServer(",generate(M))
if __name__=="__main__":unittest.main()
