import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gui_contract_compiler_v81 import validate,compile_luau
P=85896571713843
def contract(approved=True,ident="hatch",kind="gui"):
 return {"id":ident,"approved":approved,"input":[kind,[{"name":"HUD","className":"ScreenGui","ordinal":1},{"name":"Button","className":"ImageButton","ordinal":1}]],"executionEnabled":False}
def doc(*cs):return {"placeId":P,"contracts":list(cs)}
class Tests(unittest.TestCase):
 def test_approved(self):self.assertEqual(len(validate(doc(contract()),P)),1)
 def test_unapproved(self):self.assertEqual(validate(doc(contract(False)),P),[])
 def test_empty(self):self.assertEqual(validate(doc(),P),[])
 def test_place(self):
  with self.assertRaises(ValueError):validate(doc(contract()),1)
 def test_duplicate(self):
  with self.assertRaises(ValueError):validate(doc(contract(),contract()),P)
 def test_keyboard(self):
  with self.assertRaises(ValueError):validate(doc(contract(kind="keyboard")),P)
 def test_bad_id(self):
  with self.assertRaises(ValueError):validate(doc(contract(ident="a b")),P)
 def test_invalid_path(self):
  c=contract();c["input"][1]=[]
  with self.assertRaises(ValueError):validate(doc(c),P)
 def test_invalid_ordinal(self):
  c=contract();c["input"][1][0]["ordinal"]=0
  with self.assertRaises(ValueError):validate(doc(c),P)
 def test_bad_button(self):
  c=contract();c["input"][1][-1]["className"]="Frame"
  with self.assertRaises(ValueError):validate(doc(c),P)
 def test_limit(self):
  with self.assertRaises(ValueError):validate(doc(*[contract(False) for _ in range(101)]),P)
 def test_string_path(self):
  c=contract();c["input"][1]=json.dumps(c["input"][1])
  self.assertEqual(len(validate(doc(c),P)),1)
 def test_bad_json_path(self):
  c=contract();c["input"][1]="bad"
  with self.assertRaises(ValueError):validate(doc(c),P)
 def test_auto_execution_rejected(self):
  c=contract();c["executionEnabled"]=True
  with self.assertRaises(ValueError):validate(doc(c),P)
 def test_compile(self):self.assertIn("actions[contract.id]",compile_luau(validate(doc(contract()),P),P))
 def test_no_remote(self):self.assertNotIn(":FireServer(",compile_luau([],P))
 def test_no_autorun(self):self.assertIn("no actions auto-run",compile_luau([],P))
 def test_place_guard(self):self.assertIn("game.PlaceId~="+str(P),compile_luau([],P))
 def test_unicode(self):
  c=contract();c["input"][1][0]["name"]="🥚 Hatches"
  self.assertIn("Hatches",compile_luau(validate(doc(c),P),P))
 def test_injection(self):
  c=contract();c["input"][1][0]["name"]='x"); error("oops'
  generated=compile_luau(validate(doc(c),P),P)
  self.assertNotIn('name="x"); error("oops',generated)
if __name__=="__main__":unittest.main()
