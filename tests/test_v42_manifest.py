import copy
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("generation_manifest_v42",ROOT/"tools"/"generation_manifest_v42.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def fixtures():
    discovery={"schemaVersion":"39.0","placeId":3623096087,"scanId":"test",
               "families":[{"id":"training","examplePaths":["Workspace.Weights.Bar"]},
                           {"id":"trading","examplePaths":["ReplicatedStorage.Trade"]}]}
    features={"schemaVersion":"41.0","placeId":3623096087,"scanId":"test",
              "features":[{"id":"inspect-training","family":"training","label":"Inspect Training",
                           "kind":"read-only-inspection","gameplayImplementationAvailable":False,
                           "evidencePaths":["Workspace.Weights.Bar"]}]}
    return features,discovery

class TestV42(unittest.TestCase):
    def test_compiles(self):
        s,d=fixtures();r=mod.compile_manifest(s,d)
        self.assertEqual(r["featureCount"],1)
        self.assertTrue(r["readOnly"])
    def test_deterministic(self):
        s,d=fixtures()
        self.assertEqual(mod.compile_manifest(s,d),mod.compile_manifest(s,d))
    def test_cross_scan_mismatch(self):
        s,d=fixtures();d["scanId"]="other"
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_cross_place_mismatch(self):
        s,d=fixtures();d["placeId"]=123
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_forged_path_rejected(self):
        s,d=fixtures();s["features"][0]["evidencePaths"]=["Workspace.Forged"]
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_unsupported_root(self):
        s,d=fixtures();s["features"][0]["evidencePaths"]=["Unknown.Forged"];d["families"][0]["examplePaths"]=["Unknown.Forged"]
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_gameplay_flag_rejected(self):
        s,d=fixtures();s["features"][0]["gameplayImplementationAvailable"]=True
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_duplicate_feature_rejected(self):
        s,d=fixtures();s["features"].append(copy.deepcopy(s["features"][0]))
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_duplicate_family_rejected(self):
        s,d=fixtures();d["families"].append(copy.deepcopy(d["families"][0]))
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_duplicate_path_rejected(self):
        s,d=fixtures();s["features"][0]["evidencePaths"]*=2
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_empty_features(self):
        s,d=fixtures();s["features"]=[]
        self.assertEqual(mod.compile_manifest(s,d)["featureCount"],0)
    def test_missing_schema(self):
        s,d=fixtures();s["schemaVersion"]="40.0"
        with self.assertRaises(ValueError):mod.compile_manifest(s,d)
    def test_explicit_unverified(self):
        s,d=fixtures();r=mod.compile_manifest(s,d)
        self.assertFalse(r["runtimeVerified"])
        self.assertFalse(r["gameplayAutomationApproved"])
        self.assertFalse(r["features"][0]["gameplayVerified"])
    def test_fingerprint_changes(self):
        s,d=fixtures();a=mod.compile_manifest(s,d)["sourceFingerprint"]
        d["families"][0]["examplePaths"].append("Workspace.Other")
        b=mod.compile_manifest(s,d)["sourceFingerprint"]
        self.assertNotEqual(a,b)
