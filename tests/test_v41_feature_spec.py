import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("feature_spec_v41",ROOT/"tools"/"feature_spec_v41.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def discovery():
    return {"schemaVersion":"39.0","placeId":3623096087,"scanId":"test",
            "families":[{"id":"training","examplePaths":["Workspace.machineBarbellsFolder.Boulder.barType",
                                                        "Workspace.machineBarbellsFolder.Boulder.barType"]},
                        {"id":"trading","examplePaths":["ReplicatedStorage.shared.runtime.tradeSessions"]}]}

class TestV41(unittest.TestCase):
    def test_specs_from_game_evidence(self):
        r=mod.build(discovery())
        self.assertEqual(r["featureCount"],2)
        self.assertEqual([f["family"] for f in r["features"]],["training","trading"])
    def test_dedup(self):
        self.assertEqual(len(mod.build(discovery())["features"][0]["evidencePaths"]),1)
    def test_no_gameplay_approval(self):
        r=mod.build(discovery())
        self.assertFalse(r["gameplayAutomationApproved"])
        self.assertTrue(all(not f["gameplayImplementationAvailable"] for f in r["features"]))
    def test_missing_schema(self):
        with self.assertRaises(ValueError):mod.build({"schemaVersion":"38.0"})
    def test_empty_families(self):
        d=discovery();d["families"]=[]
        self.assertEqual(mod.build(d)["featureCount"],0)
    def test_unknown_family(self):
        d=discovery();d["families"]=[{"id":"unclassified","examplePaths":["Workspace.X"]}]
        self.assertEqual(mod.build(d)["featureCount"],0)
    def test_invalid_path(self):
        d=discovery();d["families"][0]["examplePaths"]=[None]
        with self.assertRaises(ValueError):mod.build(d)
    def test_luau_table(self):
        script=mod.generate(mod.build(discovery()))
        self.assertIn("local features = {{name=",script)
        self.assertIn("Check paths",script)
    def test_luau_no_remotes(self):
        script=mod.generate(mod.build(discovery()))
        self.assertNotIn("FireServer",script)
        self.assertNotIn("InvokeServer",script)
    def test_luau_escaping(self):
        self.assertEqual(mod.luau_string('a"b'),'"a\\"b"')
    def test_reject_unsafe_spec(self):
        s=mod.build(discovery())
        s["features"][0]["gameplayImplementationAvailable"]=True
        with self.assertRaises(ValueError):mod.generate(s)
    def test_invalid_place(self):
        d=discovery();d["placeId"]=True
        with self.assertRaises(ValueError):mod.build(d)
