import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"propose_actions.py"
spec=importlib.util.spec_from_file_location("proposals",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProposalTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"scanComplete":True,"placeId":3623096087,"scanId":"scan1"},
          "classCounts":{"IntValue":4,"ScreenGui":2,"ProximityPrompt":1},
          "features":[{"feature":"rebirth"}]}
    def test_evidence_produces_review_required_proposals(self):
        result=m.propose(self.plan())
        self.assertEqual(len(result["proposals"]),3)
        self.assertEqual(result["automaticallyApproved"],0)
        self.assertTrue(all(p["reviewed"] is False for p in result["proposals"]))
        self.assertTrue(all(p["implementationReady"] is False for p in result["proposals"]))
        self.assertEqual(result["placeId"],3623096087)
    def test_no_evidence_no_proposals(self):
        plan=self.plan();plan["classCounts"]={}
        self.assertEqual(m.propose(plan)["proposals"],[])
    def test_incomplete_rejected(self):
        plan=self.plan();plan["integrity"]["scanComplete"]=False
        with self.assertRaises(ValueError):m.propose(plan)
    def test_malformed_counts_rejected(self):
        plan=self.plan();plan["classCounts"]["IntValue"]=-1
        with self.assertRaises(ValueError):m.propose(plan)
if __name__=="__main__":unittest.main()
