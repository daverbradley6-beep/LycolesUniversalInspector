import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("game_first_v39",ROOT/"tools"/"game_first_v39.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def bundle():
    return {"scanId":"test","placeId":3623096087,"expectedParts":2,
            "parts":[{"partIndex":1,"objects":[]},
                     {"partIndex":2,"objects":[
                         {"path":"Workspace.machineBarbellsFolder.Boulder.barType","class":"StringValue"},
                         {"path":"ReplicatedStorage.shared.runtime.tradeSessions.tradeSession","class":"Folder"},
                         {"path":"Workspace.machineBarbellsFolder.Boulder.barType","class":"StringValue"}]}]}

class TestGameFirst(unittest.TestCase):
    def test_realistic_game_families(self):
        report=mod.discover(bundle())
        ids={f["id"] for f in report["families"]}
        self.assertIn("training",ids)
        self.assertIn("trading",ids)
        self.assertNotIn("hairdresser",ids)
    def test_counts_and_collisions(self):
        s=mod.discover(bundle())["summary"]
        self.assertEqual((s["indexedRecords"],s["uniquePaths"],s["pathCollisions"]),(3,2,1))
    def test_no_automation_claim(self):
        r=mod.discover(bundle())
        self.assertFalse(r["gameplayAutomationApproved"])
        self.assertTrue(all(not x["automationReady"] for x in r["families"]))
    def test_empty_scan(self):
        b=bundle();b["parts"][1]["objects"]=[]
        self.assertEqual(mod.discover(b)["families"],[])
    def test_missing_part(self):
        b=bundle();b["parts"].pop()
        with self.assertRaises(ValueError):mod.discover(b)
    def test_duplicate_part(self):
        b=bundle();b["parts"][1]["partIndex"]=1
        with self.assertRaises(ValueError):mod.discover(b)
    def test_bad_class(self):
        b=bundle();b["parts"][1]["objects"][0].pop("class")
        with self.assertRaises(ValueError):mod.discover(b)
    def test_invalid_identity(self):
        b=bundle();b["placeId"]=True
        with self.assertRaises(ValueError):mod.discover(b)
    def test_luau_read_only(self):
        script=mod.generate_luau(mod.discover(bundle()))
        self.assertIn("FindFirstChild",script)
        self.assertIn("ScrollingFrame",script)
        self.assertNotIn("FireServer",script)
        self.assertNotIn("InvokeServer",script)
    def test_luau_filters_roots(self):
        r=mod.discover(bundle())
        r["families"].append({"examplePaths":["UnknownRoot.Bad","Workspace.Safe"]})
        s=mod.generate_luau(r)
        self.assertNotIn("UnknownRoot.Bad",s)
        self.assertIn("Workspace.Safe",s)
    def test_schema_guard(self):
        with self.assertRaises(ValueError):mod.generate_luau({"schemaVersion":"38.0"})
