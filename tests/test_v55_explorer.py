import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from evidence_explorer_v55 import parse_path,classify,compile_features,render
from balanced_discovery_v54 import analyze
class V55(unittest.TestCase):
 def fixture(self):
  p='ReplicatedStorage/"Strength"#1@IntValue'
  return analyze({"schemaVersion":"54.0","placeId":123,"observations":[
   {"index":1,"entries":[{"path":p,"className":"IntValue","value":"10"}]},
   {"index":2,"entries":[{"path":p,"className":"IntValue","value":"12"}]}]})
 def test_path(self):
  self.assertEqual(parse_path('Workspace/"Cube.001"#2@MeshPart')[1],{"name":"Cube.001","ordinal":2,"className":"MeshPart"})
 def test_escaped(self):
  self.assertEqual(parse_path('Workspace/"a\\\"b"#1@Model')[1]["name"],'a"b')
 def test_slash_in_quoted_name(self):
  self.assertEqual(parse_path('Workspace/"Meshes/JunglePortal"#1@MeshPart')[1]['name'],'Meshes/JunglePortal')
 def test_reject_legacy(self):
  self.assertIsNone(parse_path('Workspace/"Cube"'))
 def test_reject_unknown_root(self):
  self.assertIsNone(parse_path('ServerStorage/"A"#1@Part'))
 def test_category(self):
  self.assertEqual(classify('Workspace/"Gym"#1@Model','Model'),'Training')
 def test_compile(self):
  c=compile_features(self.fixture())
  self.assertEqual(len(c["features"]),1)
  self.assertFalse(c["features"][0]["gameplayActionVerified"])
 def test_render(self):
  s=render(compile_features(self.fixture()))
  self.assertIn('game.PlaceId~=123',s)
  self.assertIn('MouseButton1Click',s)
  self.assertIn('GetChildren()',s)
  self.assertNotIn('FireServer(',s)
  self.assertNotIn('InvokeServer(',s)
 def test_reject_action(self):
  c=compile_features(self.fixture())
  c["features"][0]["gameplayActionVerified"]=True
  with self.assertRaises(ValueError):render(c)
if __name__=="__main__":unittest.main()
