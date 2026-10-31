import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
adapter=load("receiver_adapter_v37")
matcher=load("match_receiver_features_v37")

def bundle():
    return {"scanId":"abc","placeId":3623096087,"expectedParts":2,
            "parts":[{"partIndex":1,"scanStats":{"recorded":1500},"objects":[]},
                     {"partIndex":2,"objects":[{"path":"Workspace.A","class":"Part"},
                                                {"path":"Workspace.A","class":"Part"},
                                                {"path":"Workspace.B","class":"Folder"}]}]}

class ReceiverTests(unittest.TestCase):
    def test_normalization(self):
        r=adapter.adapt(bundle())
        self.assertEqual(r["integrity"]["indexedObjectRecords"],3)
        self.assertEqual(r["integrity"]["reportedRecordedObservations"],1500)
        self.assertFalse(r["integrity"]["scanComplete"])
        self.assertEqual(r["integrity"]["pathCollisions"],1)
    def test_missing_parts(self):
        b=bundle();b["parts"].pop()
        with self.assertRaises(ValueError):adapter.adapt(b)
    def test_duplicate_parts(self):
        b=bundle();b["parts"][1]["partIndex"]=1
        with self.assertRaises(ValueError):adapter.adapt(b)
    def test_missing_identity(self):
        b=bundle();b.pop("placeId")
        with self.assertRaises(ValueError):adapter.adapt(b)
    def test_invalid_object(self):
        b=bundle();b["parts"][1]["objects"][0].pop("path")
        with self.assertRaises(ValueError):adapter.adapt(b)
    def test_match(self):
        features={"schemaVersion":"32.0","features":[{"id":"a","name":"test",
                  "dependencies":{"paths":["Workspace.A","Workspace.X"],"lookups":["A"]}}]}
        f=matcher.match(features,adapter.adapt(bundle()))["features"][0]
        self.assertEqual(f["status"],"partially-observed")
        self.assertEqual(f["ambiguousPaths"]["Workspace.A"],2)
        self.assertFalse(f["approvedForAutomation"])
    def test_reject_wrong_schema(self):
        with self.assertRaises(ValueError):
            matcher.match({"schemaVersion":"33.0"},adapter.adapt(bundle()))
