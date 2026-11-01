import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from release_pipeline_v104 import build,generate,audit,luau,parts
def fixture():
 return {'placeId':123,'observations':[
 {'path':'game.Workspace.Egg','className':'Tool'},
 {'path':['PlayerGui','HUD','Coins'],'className':'TextLabel'},
 {'path':'Workspace.Egg','className':'Tool'},
 {'path':'ServerStorage.Secret','className':'Tool'},
 {'path':'Workspace.Remote','className':'RemoteEvent'},
 {'path':'Workspace.Door','className':'ProximityPrompt'}]}
class Tests(unittest.TestCase):
 def test_count(self):self.assertEqual(build(fixture(),123)['acceptedCount'],3)
 def test_rejections(self):self.assertEqual(build(fixture(),123)['rejectedCount'],3)
 def test_accounting(self):
  r=build(fixture(),123);self.assertEqual(r['inputCount'],r['acceptedCount']+r['rejectedCount'])
 def test_duplicate(self):self.assertEqual(build(fixture(),123)['rejections']['duplicate_path'],1)
 def test_reject_root(self):self.assertIsNone(parts('ServerStorage.Secret'))
 def test_prefix(self):self.assertEqual(parts('game.Workspace.Egg'),['Workspace','Egg'])
 def test_place_mismatch(self):
  with self.assertRaises(ValueError):build(fixture(),456)
 def test_bool_place(self):
  with self.assertRaises(ValueError):build(fixture(),True)
 def test_missing_collection(self):
  with self.assertRaises(ValueError):build({},123)
 def test_empty(self):self.assertEqual(build([],123)['acceptedCount'],0)
 def test_sorted(self):
  r=build(fixture(),123);self.assertEqual(r['objects'],sorted(r['objects'],key=lambda o:(o['path'],o['className'])))
 def test_no_actions(self):self.assertEqual(build(fixture(),123)['gameplayFunctionsGenerated'],0)
 def test_read_only(self):
  code=luau(build(fixture(),123))
  for x in ('FireServer','InvokeServer','loadstring','HttpGet','VirtualInputManager','hookmetamethod'):self.assertNotIn(x,code)
 def test_place_guard(self):self.assertIn('game.PlaceId ~= 123',luau(build(fixture(),123)))
 def test_generate(self):
  with tempfile.TemporaryDirectory() as d:self.assertTrue(generate(fixture(),123,d)['ok'])
 def test_audit(self):
  with tempfile.TemporaryDirectory() as d:
   generate(fixture(),123,d);self.assertTrue(audit(d)['ok'])
 def test_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   generate(fixture(),123,d)
   with (Path(d)/'LycolesObserverV104.client.lua').open('a') as f:f.write('tamper')
   self.assertFalse(audit(d)['ok'])
 def test_reproducible(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   generate(fixture(),123,a);generate(fixture(),123,b)
   self.assertEqual((Path(a)/'manifest-v104.json').read_bytes(),(Path(b)/'manifest-v104.json').read_bytes())
 def test_conflicting_class(self):
  x=[{'path':'Workspace.Part','className':'Tool'},{'path':'Workspace.Part','className':'TextLabel'}]
  self.assertEqual(build(x,123)['rejections']['conflicting_class'],1)
 def test_output_limit(self):
  x=[{'path':['Workspace','Part'+str(i)],'className':'Tool'} for i in range(200)]
  r=build(x,123);self.assertEqual(r['acceptedCount'],150);self.assertEqual(r['rejections']['output_limit'],50)
 def test_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'manifest-v104.json').symlink_to(Path(d)/'outside')
   self.assertFalse(audit(d)['ok'])
 def test_deterministic(self):self.assertEqual(build(fixture(),123),build(fixture(),123))
if __name__=='__main__':unittest.main()
