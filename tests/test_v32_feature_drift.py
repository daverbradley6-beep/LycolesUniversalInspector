"""v32 structural drift tests."""
import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("compare_feature_reports",ROOT/"tools"/"compare_feature_reports.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def doc(*features):
    return {"schemaVersion":"32.0","features":list(features)}
def f(name,paths=()):
    return {"sourceFile":"game.lua","name":name,
            "dependencies":{"paths":list(paths),"lookups":[],"services":[]}}
class DriftTests(unittest.TestCase):
    def test_no_change(self):
        self.assertEqual(module.compare(doc(f("job",("a",))),doc(f("job",("a",))))["changeCount"],0)
    def test_added(self):
        result=module.compare(doc(),doc(f("job")))
        self.assertEqual(result["changes"][0]["change"],"added")
    def test_removed(self):
        result=module.compare(doc(f("job")),doc())
        self.assertEqual(result["changes"][0]["change"],"removed")
    def test_changed_path(self):
        result=module.compare(doc(f("job",("old",))),doc(f("job",("new",))))
        self.assertEqual(result["changes"][0]["change"],"dependency-drift")
        self.assertEqual(result["changes"][0]["added"]["paths"],["new"])
        self.assertEqual(result["verifiedRepairCount"],0)
    def test_invalid_schema(self):
        with self.assertRaises(ValueError):module.compare({"schemaVersion":"31.0"},doc())
    def test_duplicate_names(self):
        with self.assertRaises(ValueError):module.compare(doc(f("job"),f("job")),doc())
if __name__=="__main__":unittest.main()
