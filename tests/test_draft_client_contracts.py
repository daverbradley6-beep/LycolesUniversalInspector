import importlib.util
import pathlib
import unittest
path=pathlib.Path(__file__).resolve().parents[1]/"tools"/"draft_client_contracts.py"
spec=importlib.util.spec_from_file_location("draft",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class DraftTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"scanComplete":True,"placeId":3623096087,"scanId":"scan"},
          "classCounts":{"ScreenGui":4,"ProximityPrompt":2,"IntValue":8},
          "features":[{"feature":"training"}]}
    def test_draft_all_supported_readonly_candidates(self):
        result=module.draft(self.plan())
        self.assertEqual(len(result["proposals"]),3)
        self.assertEqual(result["knownFeatures"],["training"])
        self.assertTrue(result["reviewRequired"])
        self.assertFalse(result["gameplayAutomationApproved"])
        self.assertTrue(all(p["reviewed"] is False for p in result["proposals"]))
    def test_no_evidence_no_proposals(self):
        plan=self.plan();plan["classCounts"]={}
        self.assertEqual(module.draft(plan)["proposals"],[])
    def test_incomplete_scan_rejected(self):
        plan=self.plan();plan["integrity"]["scanComplete"]=False
        with self.assertRaises(ValueError):module.draft(plan)
    def test_bad_counts_rejected(self):
        plan=self.plan();plan["classCounts"]["IntValue"]=-1
        with self.assertRaises(ValueError):module.draft(plan)
if __name__=="__main__":unittest.main()
