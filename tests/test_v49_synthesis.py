import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from feature_synthesizer_v49 import synthesize
M={"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"f","features":[{"id":"inspect-training","family":"training","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Workspace.A","Workspace.B"]}]}
R={"schemaVersion":"48.0","placeId":123,"scanId":"s","sourceFingerprint":"f","samples":3,"mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,"paths":{"Workspace.A":{"visibleSamples":3,"stateTransitions":1,"valueChanged":True,"classification":"changing"},"Workspace.B":{"visibleSamples":0,"stateTransitions":0,"valueChanged":False,"classification":"not-observed"}}}
class V49(unittest.TestCase):
 def test_synthesis(self):
  o=synthesize(M,R);self.assertEqual(o["featureCount"],1);self.assertEqual(o["features"][0]["candidateState"],"change-observed")
 def test_no_approval(self):self.assertFalse(synthesize(M,R)["gameplayAutomationApproved"])
 def test_determinism(self):self.assertEqual(synthesize(M,R),synthesize(M,R))
 def test_wrong_place(self):
  with self.assertRaises(ValueError):synthesize(M,{**R,"placeId":456})
 def test_wrong_scan(self):
  with self.assertRaises(ValueError):synthesize(M,{**R,"scanId":"bad"})
 def test_missing_path(self):
  with self.assertRaises(ValueError):synthesize(M,{**R,"paths":{"Workspace.A":R["paths"]["Workspace.A"]}})
 def test_invalid_samples(self):
  with self.assertRaises(ValueError):synthesize(M,{**R,"samples":0})
 def test_bad_claim(self):
  with self.assertRaises(ValueError):synthesize(M,{**R,"gameplayAutomationApproved":True})
 def test_bad_transition(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]["stateTransitions"]=4
  with self.assertRaises(ValueError):synthesize(M,r)
 def test_bad_classification(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]["classification"]="stable-visible"
  with self.assertRaises(ValueError):synthesize(M,r)
 def test_bad_value_changed(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.B"]["valueChanged"]=True
  with self.assertRaises(ValueError):synthesize(M,r)
 def test_presence_only(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]={"visibleSamples":3,"stateTransitions":0,"valueChanged":False,"classification":"stable-visible"}
  self.assertEqual(synthesize(M,r)["features"][0]["candidateState"],"presence-only")
 def test_unobserved(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]={"visibleSamples":0,"stateTransitions":0,"valueChanged":False,"classification":"not-observed"}
  self.assertEqual(synthesize(M,r)["features"][0]["candidateState"],"no-evidence")
 def test_duplicate_feature(self):
  with self.assertRaises(ValueError):synthesize({**M,"features":M["features"]*2},R)
if __name__=="__main__":unittest.main()
