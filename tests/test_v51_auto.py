import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from auto_actions_v51 import compile_auto
from action_contract_v50 import generate
M={"schemaVersion":"42.0","readOnly":True,"placeId":123,"scanId":"s","sourceFingerprint":"f","features":[{"id":"inspect-ui","kind":"read-only-inspection","gameplayVerified":False,"evidencePaths":["Players.LocalPlayer.PlayerGui.Hud.Score","Workspace.A"]}]}
R={"schemaVersion":"48.0","placeId":123,"scanId":"s","sourceFingerprint":"f","samples":3,"mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,"paths":{"Players.LocalPlayer.PlayerGui.Hud.Score":{"visibleSamples":3,"stateTransitions":1,"valueChanged":True,"classification":"changing"},"Workspace.A":{"visibleSamples":3,"stateTransitions":0,"valueChanged":False,"classification":"stable-visible"}}}
class V51(unittest.TestCase):
 def test_action(self):
  c,a=compile_auto(M,R);self.assertEqual(len(c["actions"]),1);self.assertEqual(a["excludedPaths"],1)
 def test_generated_luau(self):
  c,_=compile_auto(M,R);self.assertIn("Activated:Connect",generate(c))
 def test_read_only(self):
  c,_=compile_auto(M,R);self.assertTrue(all(x["kind"]=="read-value" for x in c["actions"]))
 def test_deterministic(self):self.assertEqual(compile_auto(M,R),compile_auto(M,R))
 def test_limit(self):self.assertEqual(compile_auto(M,R,limit=1)[1]["generatedActions"],1)
 def test_bad_limit(self):
  with self.assertRaises(ValueError):compile_auto(M,R,limit=65)
 def test_bad_scan(self):
  with self.assertRaises(ValueError):compile_auto(M,{**R,"scanId":"other"})
 def test_bad_claim(self):
  with self.assertRaises(ValueError):compile_auto(M,{**R,"mechanicVerified":True})
 def test_missing_path(self):
  with self.assertRaises(ValueError):compile_auto(M,{**R,"paths":{}})
 def test_invalid_count(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]["visibleSamples"]=9
  with self.assertRaises(ValueError):compile_auto(M,r)
 def test_invalid_classification(self):
  r=copy.deepcopy(R);r["paths"]["Workspace.A"]["classification"]="changing"
  with self.assertRaises(ValueError):compile_auto(M,r)
 def test_no_local_path(self):
  r=copy.deepcopy(R);r["paths"]["Players.LocalPlayer.PlayerGui.Hud.Score"]["visibleSamples"]=0;r["paths"]["Players.LocalPlayer.PlayerGui.Hud.Score"]["stateTransitions"]=0;r["paths"]["Players.LocalPlayer.PlayerGui.Hud.Score"]["valueChanged"]=False;r["paths"]["Players.LocalPlayer.PlayerGui.Hud.Score"]["classification"]="not-observed"
  c,a=compile_auto(M,r);self.assertEqual(c["actions"],[]);self.assertEqual(a["generatedActions"],0)
 def test_no_server_calls(self):
  c,_=compile_auto(M,R);self.assertNotIn("FireServer(",generate(c))
if __name__=="__main__":unittest.main()
