import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from secure_action_compiler_v95 import validate,compile_secure_server,compile_secure_client,generate,audit

def spec():
 return {"schemaVersion":"95.actions","placeId":123456,"enabled":True,
         "authorizedUserIds":[10001,20002],
         "actions":[{"id":"Collect","kind":"increment_stat","stat":"Coins",
                     "amount":1,"cooldownSeconds":1},
                    {"id":"Ready","kind":"set_attribute","attribute":"Ready","value":True},
                    {"id":"Spawn","kind":"teleport_to_part","part":"SpawnLocation"}]}

class SecureCompilerTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate(spec())["schemaVersion"],"94.actions")
 def test_server_allowlist(self):self.assertIn("authorizedUserIds[player.UserId]",compile_secure_server(spec()))
 def test_client_allowlist(self):self.assertIn("authorizedUserIds[player.UserId]",compile_secure_client(spec()))
 def test_cooldown(self):self.assertIn("handler.cooldown",compile_secure_server(spec()))
 def test_place_guard(self):self.assertIn("game.PlaceId",compile_secure_server(spec()))
 def test_server_stat_validation(self):self.assertIn("IntValue",compile_secure_server(spec()))
 def test_server_teleport_validation(self):self.assertIn("BasePart",compile_secure_server(spec()))
 def test_missing_ids(self):
  x=spec();x.pop("authorizedUserIds")
  with self.assertRaises(ValueError):validate(x)
 def test_empty_ids(self):
  x=spec();x["authorizedUserIds"]=[]
  with self.assertRaises(ValueError):validate(x)
 def test_duplicate_ids(self):
  x=spec();x["authorizedUserIds"]=[1,1]
  with self.assertRaises(ValueError):validate(x)
 def test_invalid_id(self):
  x=spec();x["authorizedUserIds"]=[True]
  with self.assertRaises(ValueError):validate(x)
 def test_disabled(self):
  x=spec();x["enabled"]=False
  with self.assertRaises(ValueError):validate(x)
 def test_missing_enabled(self):
  x=spec();x.pop("enabled")
  with self.assertRaises(ValueError):validate(x)
 def test_unsupported_action(self):
  x=spec();x["actions"][0]["kind"]="remote"
  with self.assertRaises(ValueError):validate(x)
 def test_duplicate_action(self):
  x=spec();x["actions"][1]["id"]="Collect"
  with self.assertRaises(ValueError):validate(x)
 def test_invalid_place(self):
  x=spec();x["placeId"]=0
  with self.assertRaises(ValueError):validate(x)
 def test_generate_and_audit(self):
  with tempfile.TemporaryDirectory() as d:
   generate(spec(),d)
   self.assertTrue(audit(d)["ok"])
 def test_manifest_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   m=generate(spec(),d)
   for name,digest in m["files"].items():
    self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),digest)
 def test_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   generate(spec(),d)
   with (Path(d)/"LycolesActionsV95.server.lua").open("a") as f:f.write("print('tamper')")
   self.assertFalse(audit(d)["ok"])
 def test_invalid_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   generate(spec(),d)
   p=Path(d)/"manifest-v95.json"
   m=json.loads(p.read_text());m["verifiedInGame"]=True;p.write_text(json.dumps(m))
   self.assertFalse(audit(d)["ok"])
 def test_missing_file(self):
  with tempfile.TemporaryDirectory() as d:
   generate(spec(),d)
   (Path(d)/"LycolesActionsV95.client.lua").unlink()
   self.assertFalse(audit(d)["ok"])
 def test_no_in_game_claim(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(generate(spec(),d)["verifiedInGame"])
 def test_determinism(self):self.assertEqual(compile_secure_server(spec()),compile_secure_server(spec()))
if __name__=="__main__":unittest.main()
