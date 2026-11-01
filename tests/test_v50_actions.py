import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from action_contract_v50 import generate,validate
S={"schemaVersion":"50.0","placeId":123,"actions":[{"id":"read-score","kind":"read-value","path":"Players.LocalPlayer.leaderstats.Score"},{"id":"toggle-menu","kind":"toggle-local-visibility","path":"Players.LocalPlayer.PlayerGui.HUD.Menu"},{"id":"set-title","kind":"set-local-text","path":"Players.LocalPlayer.PlayerGui.HUD.Title","value":"Hello"}]}
class TestV50(unittest.TestCase):
 def test_generate(self):
  s=generate(S);self.assertIn("Activated:Connect",s);self.assertIn("toggle-local-visibility",s);self.assertNotIn("FireServer(",s)
 def test_deterministic(self):self.assertEqual(generate(S),generate(S))
 def test_count(self):self.assertEqual(len(validate(S)["actions"]),3)
 def test_sorted(self):self.assertEqual(validate(S)["actions"][0]["id"],"read-score")
 def test_schema(self):
  with self.assertRaises(ValueError):validate({**S,"schemaVersion":"49.0"})
 def test_place(self):
  with self.assertRaises(ValueError):validate({**S,"placeId":True})
 def test_empty(self):
  with self.assertRaises(ValueError):validate({**S,"actions":[]})
 def test_duplicate(self):
  with self.assertRaises(ValueError):validate({**S,"actions":S["actions"]*2})
 def test_remote(self):
  s=copy.deepcopy(S);s["actions"][0]["kind"]="fire-remote"
  with self.assertRaises(ValueError):validate(s)
 def test_outside_local(self):
  s=copy.deepcopy(S);s["actions"][0]["path"]="Workspace.Part"
  with self.assertRaises(ValueError):validate(s)
 def test_text_bound(self):
  s=copy.deepcopy(S);s["actions"][2]["value"]="x"*121
  with self.assertRaises(ValueError):validate(s)
 def test_unexpected_value(self):
  s=copy.deepcopy(S);s["actions"][0]["value"]="bad"
  with self.assertRaises(ValueError):validate(s)
 def test_empty_segment(self):
  s=copy.deepcopy(S);s["actions"][0]["path"]="Players.LocalPlayer..Score"
  with self.assertRaises(ValueError):validate(s)
 def test_no_unsafe(self):
  for token in ("InvokeServer(","getgenv(","hookmetamethod("):self.assertNotIn(token,generate(S))
if __name__=="__main__":unittest.main()
