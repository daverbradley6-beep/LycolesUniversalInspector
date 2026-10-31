"""v32 feature intelligence regression tests."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("feature_intelligence",ROOT/"tools"/"feature_intelligence.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE='''local Players = game:GetService("Players")
local function CashierJob()
 local desk = workspace.Environment.Locations.BloxyBurgers.CashierWorkstations
 local order = desk:FindFirstChild("CustomerOrder")
 button.Activated:Connect(function() end)
end
local function HairdresserJob()
 local chair = workspace.Environment.Locations.StylezHairStudio.HairdresserWorkstations
 local colour = chair:WaitForChild("HairColor")
end
'''
class FeatureTests(unittest.TestCase):
    def test_two_named_functions(self):
        result=module.extract("Bloxburg.txt",SOURCE)
        self.assertEqual(len(result["features"]),2)
        self.assertEqual([x["name"] for x in result["features"]],["CashierJob","HairdresserJob"])
    def test_category_and_dependencies(self):
        a,b=module.extract("Bloxburg.txt",SOURCE)["features"]
        self.assertIn("cashier",a["categories"])
        self.assertIn("hairdresser",b["categories"])
        self.assertIn("CustomerOrder",a["dependencies"]["lookups"])
        self.assertIn("HairColor",b["dependencies"]["lookups"])
    def test_provenance_and_no_verification(self):
        a=module.extract("a.lua",SOURCE)["features"][0]
        self.assertEqual(a["line"],2)
        self.assertFalse(a["clientRuntimeVerified"])
        self.assertFalse(a["serverOutcomeVerified"])
    def test_deterministic(self):
        self.assertEqual(module.extract("a.lua",SOURCE),module.extract("a.lua",SOURCE))
    def test_opaque(self):
        result=module.extract("x.lua","-- Luraph Obfuscator\nreturn 1")
        self.assertEqual(result["classification"],"opaque")
        self.assertEqual(result["features"],[])
    def test_match_exact_and_missing(self):
        report={"schemaVersion":"32.0","features":module.extract("Bloxburg.txt",SOURCE)["features"]}
        result=module.match_inspection(report,{"placeId":1234,"scanId":"scan-1","objects":[
            {"path":"workspace.Environment.Locations.BloxyBurgers.CashierWorkstations","name":"CustomerOrder"}]})
        self.assertEqual(len(result["matches"]),2)
        self.assertIn(result["matches"][0]["status"],("all-observed","partial"))
        self.assertFalse(result["matches"][0]["gameplayConfirmed"])
    def test_reject_invalid_identity(self):
        with self.assertRaises(ValueError):
            module.match_inspection({"schemaVersion":"32.0","features":[]},{"placeId":"bad","scanId":"x","objects":[]})
    def test_directory_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)
            (p/"Bloxburg.txt").write_text(SOURCE,encoding="utf-8")
            r=module.analyze_directory(p)
            self.assertEqual(r["summary"]["sourceFiles"],1)
            self.assertEqual(r["summary"]["features"],2)
            self.assertEqual(r["summary"]["errors"],0)
    def test_top_level(self):
        r=module.extract("simple.lua",'local x = game:GetService("Players")')
        self.assertEqual(len(r["features"]),1)
        self.assertEqual(r["features"][0]["name"],"<top-level>")
    def test_invalid_dir(self):
        with self.assertRaises(ValueError):
            module.analyze_directory("/not/a/real/lycoles/directory")
if __name__=="__main__":unittest.main()
