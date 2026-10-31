import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"evaluate_runtime_feedback.py"
spec=importlib.util.spec_from_file_location("feedback",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FeedbackTests(unittest.TestCase):
    def plan(self):
        return {"placeId":3623096087,"checks":[{"feature":"rebirth","transaction":"1",
            "leaderstatsKeys":["Rebirths","Strength"]}]}
    def report(self):
        return {"schemaVersion":"22.0","placeId":3623096087,
          "results":[{"feature":"rebirth","transaction":"1",
             "before":{"Rebirths":18,"Strength":189769},
             "after":{"Rebirths":19,"Strength":0}}]}
    def test_observed_transition_not_automatic_approval(self):
        out=m.evaluate(self.plan(),self.report())
        self.assertEqual(out["summary"]["clientChangesObserved"],1)
        self.assertEqual(out["summary"]["runtimeGameplayVerified"],0)
        self.assertFalse(out["results"][0]["gameplayAutomationApproved"])
        self.assertEqual(out["results"][0]["changes"]["Rebirths"]["after"],19)
    def test_wrong_place_rejected(self):
        r=self.report();r["placeId"]=123
        with self.assertRaises(ValueError):m.evaluate(self.plan(),r)
    def test_unknown_state_key_rejected(self):
        r=self.report();r["results"][0]["after"]["Hidden"]=1
        with self.assertRaises(ValueError):m.evaluate(self.plan(),r)
    def test_duplicate_check_rejected(self):
        r=self.report();r["results"].append(dict(r["results"][0]))
        with self.assertRaises(ValueError):m.evaluate(self.plan(),r)
    def test_missing_values_incomplete(self):
        r=self.report();r["results"][0]["after"]={}
        self.assertEqual(m.evaluate(self.plan(),r)["results"][0]["status"],"incomplete-observation")
if __name__=="__main__":unittest.main()
