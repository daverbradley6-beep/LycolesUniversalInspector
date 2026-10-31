"""v35 offline bridge tests."""
import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bridge35",ROOT/"tools"/"inspection_bridge_v35.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def scan(objects=None):
    return {"placeId":3623096087,"scanId":"scan-1","objects":objects if objects is not None else [
        {"path":"workspace.Jobs.Cashier","name":"Cashier"},
        {"path":"workspace.Jobs.Hairdresser","name":"Hairdresser"}]}
def feature(paths=None,names=None):
    return {"schemaVersion":"32.0","features":[{"id":"f1","name":"CashierJob",
        "dependencies":{"paths":paths or [],"lookups":names or []}}]}
class BridgeTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(m.normalize(scan())["objectCount"],2)
    def test_exact(self):
        r=m.bridge(feature(["workspace.Jobs.Cashier"]),m.normalize(scan()))
        self.assertEqual(r["features"][0]["status"],"exact-paths-observed")
        self.assertFalse(r["features"][0]["runtimeVerified"])
    def test_partial(self):
        r=m.bridge(feature(["workspace.Jobs.Cashier","workspace.Missing"]),m.normalize(scan()))
        self.assertEqual(r["features"][0]["status"],"partial-path-evidence")
    def test_missing(self):
        r=m.bridge(feature(["workspace.Missing"]),m.normalize(scan()))
        self.assertEqual(r["features"][0]["status"],"unresolved")
    def test_name_hint_not_identity(self):
        r=m.bridge(feature(names=["Cashier"]),m.normalize(scan()))["features"][0]
        self.assertEqual(r["status"],"unresolved")
        self.assertIn("Cashier",r["uniqueNameHints"])
    def test_ambiguous(self):
        s=m.normalize(scan([{"path":"workspace.A","name":"A"},{"path":"workspace.B","name":"A"}]))
        r=m.bridge(feature(names=["A"]),s)["features"][0]
        self.assertEqual(len(r["ambiguousNameHints"]["A"]),2)
    def test_reject_injection_path(self):
        s=m.normalize(scan([{"path":'workspace.X);print(1)',"name":"X"}]))
        self.assertEqual(s["rejectedObjects"],1)
    def test_invalid_place(self):
        with self.assertRaises(ValueError):m.normalize({"placeId":"1","scanId":"x","objects":[]})
    def test_missing_scan(self):
        with self.assertRaises(ValueError):m.normalize({"placeId":1,"objects":[]})
    def test_wrong_feature_schema(self):
        with self.assertRaises(ValueError):m.bridge({"schemaVersion":"31.0"},m.normalize(scan()))
    def test_audit_link(self):
        a={"schemaVersion":"34.0","features":[{"featureId":"f1","status":"lexically-corroborated"}]}
        r=m.bridge(feature(["workspace.Jobs.Cashier"]),m.normalize(scan()),a)
        self.assertEqual(r["features"][0]["lexicalStatus"],"lexically-corroborated")
    def test_proposal_unreviewed(self):
        r=m.bridge(feature(["workspace.Jobs.Cashier"]),m.normalize(scan()))
        self.assertFalse(m.propose(r)["features"][0]["reviewed"])
    def test_missing_not_proposed(self):
        r=m.bridge(feature(["workspace.Missing"]),m.normalize(scan()))
        self.assertEqual(m.propose(r)["features"],[])
    def test_nested_data(self):
        s=m.normalize({"placeId":1,"scanId":"s","data":{"objects":[{"path":"workspace.A"}]}})
        self.assertEqual(s["objectCount"],1)
    def test_order(self):
        self.assertEqual(m.normalize(scan()),m.normalize(scan(list(reversed(scan()["objects"])))))
    def test_no_dependencies(self):
        r=m.bridge(feature(),m.normalize(scan()))
        self.assertEqual(r["features"][0]["status"],"no-static-dependencies")
if __name__=="__main__":unittest.main()
