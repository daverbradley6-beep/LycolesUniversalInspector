import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from authorized_action_compiler_v94 import validate,compile_server,compile_client,generate

PLACE=85896571713843
def spec():
 return {"schemaVersion":"94.actions","placeId":PLACE,"actions":[
  {"id":"Collect","kind":"increment_stat","stat":"Coins","amount":1,"cooldownSeconds":1},
  {"id":"Mark","kind":"set_attribute","attribute":"Ready","value":True},
  {"id":"Return","kind":"teleport_to_part","part":"SpawnLocation"}]}
class CompilerTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(spec())["placeId"],PLACE)
 def test_server_handlers(self):self.assertIn("OnServerEvent",compile_server(spec()))
 def test_server_rate_limit(self):self.assertIn("handler.cooldown",compile_server(spec()))
 def test_server_guard(self):self.assertIn("game.PlaceId",compile_server(spec()))
 def test_server_stat_check(self):self.assertIn("IntValue",compile_server(spec()))
 def test_server_teleport_check(self):self.assertIn("BasePart",compile_server(spec()))
 def test_client_buttons(self):self.assertIn("addButton",compile_client(spec()))
 def test_client_close(self):self.assertIn("addButton('Close',nil)",compile_client(spec()))
 def test_no_arbitrary_payload(self):self.assertIn("type(actionId) ~= 'string'",compile_server(spec()))
 def test_reject_unknown_kind(self):
  x=spec();x["actions"][0]["kind"]="invoke_remote"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_duplicate(self):
  x=spec();x["actions"][1]["id"]="Collect"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_bad_id(self):
  x=spec();x["actions"][0]["id"]="bad-id"
  with self.assertRaises(ValueError):validate(x)
 def test_reject_bad_place(self):
  x=spec();x["placeId"]=0
  with self.assertRaises(ValueError):validate(x)
 def test_reject_empty(self):
  x=spec();x["actions"]=[]
  with self.assertRaises(ValueError):validate(x)
 def test_reject_negative_increment(self):
  x=spec();x["actions"][0]["amount"]=-1
  with self.assertRaises(ValueError):validate(x)
 def test_reject_cooldown(self):
  x=spec();x["actions"][0]["cooldownSeconds"]=0
  with self.assertRaises(ValueError):validate(x)
 def test_reject_attribute_table(self):
  x=spec();x["actions"][1]["value"]={"danger":"value"}
  with self.assertRaises(ValueError):validate(x)
 def test_reject_oversized_attribute(self):
  x=spec();x["actions"][1]["value"]="x"*121
  with self.assertRaises(ValueError):validate(x)
 def test_unicode(self):
  x=spec();x["actions"][1]["attribute"]="Eggs";x["actions"][1]["value"]="🥚"
  self.assertIn("🥚",compile_server(x))
 def test_output_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   manifest=generate(spec(),d)
   for name,digest in manifest["files"].items():
    self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),digest)
 def test_not_verified(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(generate(spec(),d)["verifiedInGame"])
 def test_stable_output(self):
  self.assertEqual(compile_server(spec()),compile_server(spec()))
if __name__=="__main__":unittest.main()
