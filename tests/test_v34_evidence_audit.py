"""v34 static cross-check tests."""
import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("audit_v34",ROOT/"tools"/"audit_feature_evidence_v34.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def features(name="Cashier",digest="abc"):
    return {"schemaVersion":"32.0","features":[{"id":"f1","name":name,"sourceFile":"game.lua","sourceSha256":digest}]}
def corpus(digest="abc",names=("Cashier",)):
    return {"schemaVersion":"34.0","reports":[{"file":"game.lua","sha256":digest,"functions":[{"name":n,"line":1} for n in names]}]}
class AuditTests(unittest.TestCase):
    def test_matched(self):
        r=m.audit(features(),corpus())
        self.assertEqual(r["features"][0]["status"],"lexically-corroborated")
        self.assertFalse(r["approvedForGameplayAutomation"])
    def test_mismatch(self):
        self.assertEqual(m.audit(features(),corpus("different"))["features"][0]["status"],"source-hash-mismatch")
    def test_missing_definition(self):
        self.assertEqual(m.audit(features(),corpus(names=()))["features"][0]["status"],"function-not-found")
    def test_missing_source(self):
        self.assertEqual(m.audit(features(),{"schemaVersion":"34.0","reports":[]})["features"][0]["status"],"missing-source-evidence")
    def test_top_level_not_approved(self):
        self.assertEqual(m.audit(features("<top-level>"),corpus(names=()))["features"][0]["status"],"requires-manual-review")
    def test_invalid_schema(self):
        with self.assertRaises(ValueError):m.audit({"schemaVersion":"31.0"},corpus())
if __name__=="__main__":unittest.main()
