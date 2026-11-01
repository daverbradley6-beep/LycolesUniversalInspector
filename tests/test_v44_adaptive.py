import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from adaptive_probe_v44 import paths,generate,analyze
M={"schemaVersion":"42.0","readOnly":True,"scanId":"s","placeId":123,"sourceFingerprint":"h","features":[{"id":"inspect-training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A","Players.LocalPlayer.PlayerGui.Hud"]}]}
def receipt(rows):
 pp=paths(M)
 return {"schemaVersion":"44.0","scanId":"s","placeId":123,"sourceFingerprint":"h","snapshots":[{"index":i+1,"checks":[{"path":p,"found":b,"reason":"found" if b else "missing-segment","depth":1,**({} if b else {"missingSegment":"A"})} for p,b in zip(pp,row)]} for i,row in enumerate(rows)]}
class V44(unittest.TestCase):
 def test_generator(self):
  s=generate(M)
  for marker in ("LYCOLES_V44_RECEIPT_BEGIN","os.clock()","FindFirstChild","game.PlaceId","PlayerGui"):self.assertIn(marker,s)
 def test_states(self):
  r=analyze(M,receipt([[True,False],[True,True]]))
  self.assertEqual([r["paths"][p]["status"] for p in paths(M)],["persistent","intermittent"])
  self.assertFalse(r["gameplayAutomationApproved"])
 def test_not_observed(self):self.assertEqual(analyze(M,receipt([[False,False]]))["features"][0]["not-observed"],2)
 def test_identity(self):
  r=receipt([[True,True]]);r["scanId"]="wrong"
  with self.assertRaises(ValueError):analyze(M,r)
 def test_duplicate(self):
  r=receipt([[True,True]]);r["snapshots"][0]["checks"][1]["path"]=r["snapshots"][0]["checks"][0]["path"]
  with self.assertRaises(ValueError):analyze(M,r)
 def test_incomplete(self):
  r=receipt([[True,True]]);r["snapshots"][0]["checks"].pop()
  with self.assertRaises(ValueError):analyze(M,r)
 def test_reason(self):
  r=receipt([[True,True]]);r["snapshots"][0]["checks"][0]["reason"]="missing-segment"
  with self.assertRaises(ValueError):analyze(M,r)
 def test_missing_segment(self):
  r=receipt([[False,True]]);r["snapshots"][0]["checks"][0].pop("missingSegment")
  with self.assertRaises(ValueError):analyze(M,r)
 def test_empty(self):
  with self.assertRaises(ValueError):analyze(M,receipt([]))
 def test_limit(self):
  with self.assertRaises(ValueError):analyze(M,receipt([[True,True]]*33))
 def test_contract(self):
  with self.assertRaises(ValueError):generate({**M,"readOnly":False})
 def test_unknown(self):
  r=receipt([[True,True]]);r["snapshots"][0]["checks"][0]["path"]="Workspace.Z"
  with self.assertRaises(ValueError):analyze(M,r)
if __name__=="__main__":unittest.main()
