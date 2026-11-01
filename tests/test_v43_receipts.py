import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
verify=load("receipt_verifier_v43")
collector=load("receipt_collector_v43")

def manifest():
    return {"schemaVersion":"42.0","placeId":3623096087,"scanId":"scan",
            "sourceFingerprint":"abc123","readOnly":True,
            "features":[{"id":"inspect-training","kind":"read-only-inspection",
                         "gameplayVerified":False,
                         "evidencePaths":["Workspace.Weights.Bar","ReplicatedStorage.Stats"]}]}
def receipt():
    return {"schemaVersion":"43.0","placeId":3623096087,"scanId":"scan",
            "sourceFingerprint":"abc123","checks":[{"path":"Workspace.Weights.Bar","found":True},
                                                    {"path":"ReplicatedStorage.Stats","found":False}]}

class TestV43(unittest.TestCase):
    def test_complete(self):
        r=verify.verify(manifest(),receipt())
        self.assertTrue(r["complete"])
        self.assertEqual(r["features"][0]["foundPaths"],1)
        self.assertFalse(r["runtimeVerified"])
    def test_partial(self):
        r=receipt();r["checks"].pop()
        self.assertFalse(verify.verify(manifest(),r)["complete"])
    def test_scan_mismatch(self):
        r=receipt();r["scanId"]="other"
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_fingerprint_mismatch(self):
        r=receipt();r["sourceFingerprint"]="other"
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_place_mismatch(self):
        r=receipt();r["placeId"]=123
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_unknown_path(self):
        r=receipt();r["checks"][0]["path"]="Workspace.Forged"
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_duplicate_path(self):
        r=receipt();r["checks"].append(r["checks"][0].copy())
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_nonboolean(self):
        r=receipt();r["checks"][0]["found"]=1
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_extra_field(self):
        r=receipt();r["checks"][0]["extra"]=True
        with self.assertRaises(ValueError):verify.verify(manifest(),r)
    def test_empty_receipt(self):
        r=receipt();r["checks"]=[]
        self.assertEqual(verify.verify(manifest(),r)["checksReceived"],0)
    def test_unsupported_contract(self):
        m=manifest();m["features"][0]["gameplayVerified"]=True
        with self.assertRaises(ValueError):verify.verify(m,receipt())
    def test_generator_luau_table(self):
        s=collector.generate(manifest())
        self.assertIn('local paths = {"Workspace.Weights.Bar"',s)
        self.assertIn("HttpService:JSONEncode",s)
    def test_generator_no_remotes(self):
        s=collector.generate(manifest())
        self.assertNotIn("FireServer",s)
        self.assertNotIn("InvokeServer",s)
    def test_generator_bad_manifest(self):
        m=manifest();m["readOnly"]=False
        with self.assertRaises(ValueError):collector.generate(m)
    def test_generator_quote(self):
        self.assertEqual(collector.quote('a"b'),'"a\\"b"')
