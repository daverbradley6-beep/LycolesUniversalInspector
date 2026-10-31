"""v33 proposal gating tests."""
import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("propose",ROOT/"tools"/"propose_diagnostics.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def report(paths):
    return {"schemaVersion":"32.0","features":[{"id":"f1","name":"CashierJob",
        "dependencies":{"paths":paths}}]}
class Proposals(unittest.TestCase):
    def test_requires_review(self):
        r=m.propose(report(["workspace.Jobs.Cashier"]),1234)
        self.assertEqual(len(r["features"]),1)
        self.assertFalse(r["features"][0]["reviewed"])
    def test_filters_unsafe_paths(self):
        r=m.propose(report(['workspace.Foo");print(1)',"workspace.Safe"]),1234)
        self.assertEqual(r["features"][0]["paths"],["workspace.Safe"])
    def test_no_paths_no_proposal(self):
        self.assertEqual(m.propose(report([]),1234)["features"],[])
    def test_bad_place(self):
        with self.assertRaises(ValueError):m.propose(report([]),"1234")
    def test_bad_schema(self):
        with self.assertRaises(ValueError):m.propose({"schemaVersion":"31.0"},1234)
if __name__=="__main__":unittest.main()
