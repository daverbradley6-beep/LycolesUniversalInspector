import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from evidence_compiler_v45 import compile_contracts

M = {"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"h","features":[{"id":"inspect-training","family":"training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A","Workspace.B"]}]}
R = {"schemaVersion":"44.0","placeId":123,"scanId":"s","sourceFingerprint":"h","snapshotsAnalyzed":2,"runtimeVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,"paths":{"Workspace.A":{"foundSnapshots":2,"totalSnapshots":2,"status":"persistent","reasons":{"found":2}},"Workspace.B":{"foundSnapshots":1,"totalSnapshots":2,"status":"intermittent","reasons":{"found":1,"missing-segment":1}}}}
class V45(unittest.TestCase):
 def test_compilation(self):
  x=compile_contracts(M,R);self.assertEqual(x["featureCount"],1);self.assertEqual(x["features"][0]["stablePathCount"],1)
 def test_deterministic(self):self.assertEqual(compile_contracts(M,R),compile_contracts(M,R))
 def test_no_approval(self):self.assertFalse(compile_contracts(M,R)["gameplayAutomationApproved"])
 def test_bad_schema(self):
  with self.assertRaises(ValueError):compile_contracts({**M,"schemaVersion":"wrong"},R)
 def test_bad_identity(self):
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"scanId":"wrong"})
 def test_bad_runtime_claim(self):
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"runtimeVerified":True})
 def test_missing_path(self):
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"paths":{"Workspace.A":R["paths"]["Workspace.A"]}})
 def test_extra_path(self):
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"paths":{**R["paths"],"Workspace.C":R["paths"]["Workspace.A"]}})
 def test_bad_histogram(self):
  p={**R["paths"]["Workspace.A"],"reasons":{"found":1}}
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"paths":{**R["paths"],"Workspace.A":p}})
 def test_bad_status(self):
  p={**R["paths"]["Workspace.A"],"status":"intermittent"}
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"paths":{**R["paths"],"Workspace.A":p}})
 def test_bad_count(self):
  with self.assertRaises(ValueError):compile_contracts(M,{**R,"snapshotsAnalyzed":0})
 def test_duplicate_paths(self):
  f={**M["features"][0],"evidencePaths":["Workspace.A","Workspace.A"]}
  with self.assertRaises(ValueError):compile_contracts({**M,"features":[f]},R)
if __name__=="__main__":unittest.main()
