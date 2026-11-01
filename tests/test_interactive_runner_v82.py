import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from interactive_runner_v82 import generate
P=85896571713843
def c(id="hatch",approved=True):
 return {"id":id,"approved":approved,"executionEnabled":False,"input":["gui",[{"name":"ScreenGui","className":"ScreenGui","ordinal":1},{"name":"Button","className":"ImageButton","ordinal":1}]]}
def doc(*contracts):return {"placeId":P,"contracts":list(contracts)}
class Tests(unittest.TestCase):
 def test_approved(self):self.assertEqual(generate(doc(c()),P)[1],1)
 def test_unapproved(self):self.assertEqual(generate(doc(c(approved=False)),P)[1],0)
 def test_multiple(self):self.assertEqual(generate(doc(c(),c("inventory")),P)[1],2)
 def test_empty(self):self.assertEqual(generate(doc(),P)[1],0)
 def test_wrong_place(self):
  with self.assertRaises(ValueError):generate(doc(c()),1)
 def test_duplicate(self):
  with self.assertRaises(ValueError):generate(doc(c(),c()),P)
 def test_keyboard_rejected(self):
  x=c();x["input"][0]="keyboard"
  with self.assertRaises(ValueError):generate(doc(x),P)
 def test_no_remote(self):self.assertNotIn(":FireServer(",generate(doc(c()),P)[0])
 def test_no_auto_run(self):self.assertIn("nothing auto-executed",generate(doc(c()),P)[0])
 def test_place_guard(self):self.assertIn("game.PlaceId~="+str(P),generate(doc(),P)[0])
 def test_unsupported_activation_fails_closed(self):
  script=generate(doc(c()),P)[0]
  self.assertNotIn("target:Activate()",script)
  self.assertIn("GuiButton has no public Activate() method",script)
  self.assertIn("requested=false",script)
 def test_visible_ancestor(self):self.assertIn("not current.Visible",generate(doc(c()),P)[0])
 def test_enabled_ancestor(self):self.assertIn("not current.Enabled",generate(doc(c()),P)[0])
 def test_snapshot(self):self.assertIn("local before=snapshot()",generate(doc(c()),P)[0])
 def test_result(self):self.assertIn("LYCOLES_V82_RESULT",generate(doc(c()),P)[0])
 def test_not_verified(self):self.assertIn("verified=false",generate(doc(c()),P)[0])
 def test_reentrant(self):self.assertIn("if busy then return end",generate(doc(c()),P)[0])
 def test_close(self):self.assertIn("gui:Destroy()",generate(doc(c()),P)[0])
 def test_unicode(self):
  x=c();x["input"][1][0]["name"]="🥚 Hatches"
  self.assertIn("Hatches",generate(doc(x),P)[0])
 def test_injection(self):
  x=c();x["input"][1][0]["name"]='x"); error("oops'
  self.assertNotIn('name="x"); error("oops',generate(doc(x),P)[0])
if __name__=="__main__":unittest.main()
