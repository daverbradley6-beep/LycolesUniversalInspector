import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from auto_pipeline_v46 import extract,generate_auto,process,BEGIN,END
M={"schemaVersion":"42.0","readOnly":True,"scanId":"s","placeId":123,"sourceFingerprint":"h","features":[{"id":"inspect-training","family":"training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A"]}]}
R={"schemaVersion":"44.0","scanId":"s","placeId":123,"sourceFingerprint":"h","snapshots":[{"index":1,"checks":[{"path":"Workspace.A","found":True,"reason":"found","depth":1}]},{"index":2,"checks":[{"path":"Workspace.A","found":True,"reason":"found","depth":1}]}]}
def wrap(r):return "Output: "+BEGIN+"\nOutput: "+json.dumps(r)+"\nOutput: "+END+"\n"
class V46(unittest.TestCase):
 def test_auto(self):
  s=generate_auto(M)
  self.assertIn("task.spawn(function()",s)
  self.assertIn("task.wait(4)",s)
  self.assertNotIn("btn.Activated:Connect",s)
 def test_count(self):self.assertIn("for index=1, 8 do",generate_auto(M,count=8))
 def test_interval(self):self.assertIn("task.wait(6)",generate_auto(M,interval=6))
 def test_bad_count(self):
  with self.assertRaises(ValueError):generate_auto(M,count=9)
 def test_bad_interval(self):
  with self.assertRaises(ValueError):generate_auto(M,interval=1)
 def test_extract(self):self.assertEqual(extract(wrap(R)),R)
 def test_last(self):self.assertEqual(extract(wrap({**R,"scanId":"old"})+wrap(R)),R)
 def test_raw(self):self.assertEqual(extract(json.dumps(R)),R)
 def test_empty(self):
  with self.assertRaises(ValueError):extract("nothing")
 def test_broken(self):
  with self.assertRaises(ValueError):extract(BEGIN+"\nnot json\n"+END)
 def test_process(self):
  a,b,c=process(M,wrap(R))
  self.assertEqual(b["snapshotsAnalyzed"],2)
  self.assertEqual(c["featureCount"],1)
  self.assertFalse(c["gameplayAutomationApproved"])
 def test_mismatch(self):
  with self.assertRaises(ValueError):process(M,wrap({**R,"scanId":"wrong"}))
if __name__=="__main__":unittest.main()
