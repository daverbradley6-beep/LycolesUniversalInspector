"""Lycoles v33 safe diagnostic generator tests."""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("diagnostic",ROOT/"tools"/"generate_diagnostic_gui.py")
g=importlib.util.module_from_spec(s)
s.loader.exec_module(g)
def spec(action="read_object_presence",paths=None):
    return {"schemaVersion":"33.0","placeId":3623096087,
            "features":[{"name":"ObjectPresence","reviewed":True,"action":action,
                         "paths":["workspace.SafeFolder"] if paths is None else paths}]}
class DiagnosticTests(unittest.TestCase):
    def test_valid_generation(self):
        lua=g.generate(spec())
        self.assertIn('assert(game.PlaceId == 3623096087',lua)
        self.assertIn('button("Close",close)',lua)
        self.assertIn('ObjectPresence',lua)
    def test_four_actions(self):
        for action in sorted(g.ALLOWED):
            paths=["workspace.SafeFolder"] if action=="read_object_presence" else []
            self.assertIn(action,g.generate(spec(action,paths)))
    def test_no_unsafe_calls(self):
        lua=g.generate(spec())
        for token in ("FireServer(", "InvokeServer(", "loadstring(", "hookmetamethod(", "getrawmetatable("):
            self.assertNotIn(token,lua)
    def test_reject_unreviewed(self):
        x=spec();x["features"][0]["reviewed"]=False
        with self.assertRaises(ValueError):g.generate(x)
    def test_reject_remote_action(self):
        with self.assertRaises(ValueError):g.generate(spec("invoke_remote"))
    def test_reject_injection_path(self):
        with self.assertRaises(ValueError):g.generate(spec(paths=['workspace.A");print("oops")']))
    def test_reject_bad_place(self):
        x=spec();x["placeId"]="3623096087"
        with self.assertRaises(ValueError):g.generate(x)
    def test_reject_duplicates(self):
        x=spec();x["features"].append(dict(x["features"][0]))
        with self.assertRaises(ValueError):g.generate(x)
    def test_reject_empty(self):
        x=spec();x["features"]=[]
        with self.assertRaises(ValueError):g.generate(x)
    def test_reject_unknown_schema(self):
        x=spec();x["schemaVersion"]="32.0"
        with self.assertRaises(ValueError):g.generate(x)
    def test_deterministic(self):
        self.assertEqual(g.generate(spec()),g.generate(spec()))
if __name__=="__main__":unittest.main()
