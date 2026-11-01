import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from release_auditor_v93 import audit

PLACE=85896571713843

def write_release(root,script=None,approved=False):
 root=Path(root)
 if script is None:script="if game.PlaceId ~= 85896571713843 then return end\n"
 files={
  "review-v92.json":json.dumps({"placeId":PLACE,"candidates":[{"approved":approved,"executionEnabled":False}]}).encode(),
  "implementation-backlog-v92.json":json.dumps({"items":[]}).encode(),
  "diagnostics-v92.luau":script.encode()
 }
 for name,data in files.items():(root/name).write_bytes(data)
 manifest={"placeId":PLACE,"verifiedInGame":False,
           "automaticallyGeneratedExecutableActions":0,
           "files":{n:hashlib.sha256(b).hexdigest() for n,b in files.items()}}
 (root/"manifest-v92.json").write_text(json.dumps(manifest))
 return manifest

class AuditTests(unittest.TestCase):
 def test_valid(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d)
   self.assertTrue(audit(d)["ok"])
 def test_missing_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIn("missing_manifest",audit(d)["issues"])
 def test_wrong_place(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d)
   self.assertIn("place_mismatch",audit(d,expected_place=PLACE+1)["issues"])
 def test_hash_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d)
   (Path(d)/"diagnostics-v92.luau").write_text("modified")
   self.assertIn("hash_mismatch:diagnostics-v92.luau",audit(d)["issues"])
 def test_missing_artifact(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d)
   (Path(d)/"review-v92.json").unlink()
   self.assertFalse(audit(d)["ok"])
 def test_unsafe_remote(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d,"if game.PlaceId ~= 1 then return end\nx:FireServer()")
   self.assertFalse(audit(d)["ok"])
 def test_unsafe_input(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d,"if game.PlaceId ~= 1 then return end\nVirtualInputManager")
   self.assertFalse(audit(d)["ok"])
 def test_missing_place_guard(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d,"print('hello')")
   self.assertFalse(audit(d)["ok"])
 def test_approved_contract(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d,approved=True)
   self.assertFalse(audit(d)["ok"])
 def test_unverified_claim(self):
  with tempfile.TemporaryDirectory() as d:
   m=write_release(d);m["verifiedInGame"]=True
   (Path(d)/"manifest-v92.json").write_text(json.dumps(m))
   self.assertFalse(audit(d)["ok"])
 def test_invalid_json(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d)
   (Path(d)/"manifest-v92.json").write_text("{")
   self.assertFalse(audit(d)["ok"])
 def test_invalid_sha(self):
  with tempfile.TemporaryDirectory() as d:
   m=write_release(d);m["files"]["review-v92.json"]="bad"
   (Path(d)/"manifest-v92.json").write_text(json.dumps(m))
   self.assertFalse(audit(d)["ok"])
 def test_invalid_name(self):
  with tempfile.TemporaryDirectory() as d:
   m=write_release(d);m["files"]["../outside"]="0"*64
   (Path(d)/"manifest-v92.json").write_text(json.dumps(m))
   self.assertFalse(audit(d)["ok"])
 def test_unknown_version(self):
  with self.assertRaises(ValueError):audit(".",version="999")
 def test_no_execution_claim(self):
  with tempfile.TemporaryDirectory() as d:
   m=write_release(d);m["automaticallyGeneratedExecutableActions"]=1
   (Path(d)/"manifest-v92.json").write_text(json.dumps(m))
   self.assertFalse(audit(d)["ok"])
 def test_unicode(self):
  with tempfile.TemporaryDirectory() as d:
   write_release(d,"if game.PlaceId ~= 1 then return end\nprint('🥚')")
   self.assertTrue(audit(d)["ok"])
if __name__=="__main__":unittest.main()
