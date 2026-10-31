import importlib.util
import pathlib
import unittest

p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"merge_observations.py"
spec=importlib.util.spec_from_file_location("merge_observations",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MergeTests(unittest.TestCase):
    def baseline(self):
        return {"integrity":{"scanComplete":True,"placeId":123,"scanId":"base"},
          "sourceDiagnostics":{"scanMode":"full"},
          "features":[{"feature":"rebirth","interactionEvents":1,"observedEvents":1,
            "verifiedClientOutcomes":0,"clientCorroboratedEvents":0,
            "temporalTransitionEvents":0,"implementationReady":False}]}
    def observation(self):
        return {"integrity":{"scanComplete":True,"placeId":123,"scanId":"delta"},
          "sourceDiagnostics":{"scanMode":"dynamic-observations"},
          "features":[{"feature":"rebirth","interactionEvents":2,"observedEvents":2,
            "verifiedClientOutcomes":1,"clientCorroboratedEvents":1,
            "temporalTransitionEvents":1}]}
    def test_merge_preserves_baseline_and_counts(self):
        b=self.baseline()
        merged=m.merge_evidence(b,[self.observation()])
        self.assertEqual(merged["features"][0]["interactionEvents"],3)
        self.assertEqual(merged["features"][0]["verifiedClientOutcomes"],1)
        self.assertEqual(b["features"][0]["interactionEvents"],1)
        self.assertFalse(merged["releaseGate"]["gameplayAutomationApproved"])
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            m.merge_evidence(self.baseline(),[self.observation(),self.observation()])
    def test_different_place_rejected(self):
        o=self.observation();o["integrity"]["placeId"]=999
        with self.assertRaises(ValueError):m.merge_evidence(self.baseline(),[o])
    def test_dynamic_cannot_be_baseline(self):
        b=self.baseline();b["sourceDiagnostics"]["scanMode"]="dynamic-observations"
        with self.assertRaises(ValueError):m.merge_evidence(b,[])
if __name__=="__main__":unittest.main()
