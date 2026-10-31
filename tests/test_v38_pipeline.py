import importlib.util
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v38",ROOT/"tools"/"receiver_pipeline_v38.py")
v38=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v38)

def batches():
    return [{"scanId":"abc","expectedParts":2,"parts":[{"partIndex":1,"objects":[],"scanStats":{"recorded":1500}}]},
            {"scanId":"abc","expectedParts":2,"parts":[{"partIndex":2,"objects":[{"path":"Workspace.A","class":"Part"},{"path":"Workspace.A","class":"Part"}]}]}]

class TestV38(unittest.TestCase):
    def test_assemble(self):
        self.assertEqual(v38.assemble(batches(),3623096087)["expectedParts"],2)
    def test_collisions(self):
        self.assertEqual(v38.summarize(v38.assemble(batches(),1))["pathCollisions"],1)
    def test_record_count_distinct(self):
        s=v38.summarize(v38.assemble(batches(),1))
        self.assertEqual((s["reportedObservations"],s["indexedRecords"]),(1500,2))
        self.assertFalse(s["coverageVerified"])
    def test_missing_part(self):
        with self.assertRaises(ValueError):v38.assemble(batches()[:1],1)
    def test_conflicting_part(self):
        b=batches();b.append({"scanId":"abc","expectedParts":2,"parts":[{"partIndex":2,"objects":[]}]})
        with self.assertRaises(ValueError):v38.assemble(b,1)
    def test_mixed_scan(self):
        b=batches();b[1]["scanId"]="other"
        with self.assertRaises(ValueError):v38.assemble(b,1)
    def test_invalid_place(self):
        with self.assertRaises(ValueError):v38.assemble(batches(),True)
    def test_duplicate_identical_part(self):
        b=batches();b.append(batches()[1])
        self.assertEqual(len(v38.assemble(b,1)["parts"]),2)
    def test_invalid_class(self):
        b=batches();b[1]["parts"][0]["objects"][0].pop("class")
        with self.assertRaises(ValueError):v38.summarize(v38.assemble(b,1))
    def test_plan(self):
        f={"schemaVersion":"32.0","features":[{"id":"f","name":"sample","dependencies":{"paths":["Workspace.A","Workspace.B"]}}]}
        r=v38.plan(f,v38.assemble(batches(),1))["features"][0]
        self.assertEqual(r["status"],"partial")
        self.assertEqual(r["ambiguousPaths"]["Workspace.A"],2)
        self.assertFalse(r["approvedForAutomation"])
    def test_wrong_schema(self):
        with self.assertRaises(ValueError):v38.plan({"schemaVersion":"31.0"},v38.assemble(batches(),1))
