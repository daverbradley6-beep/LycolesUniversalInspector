import importlib.util
import pathlib
import unittest

path=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_workflows.py"
spec=importlib.util.spec_from_file_location("workflows",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WorkflowTests(unittest.TestCase):
    def test_evidence_levels(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"sample"},"features":[
            {"feature":"rebirth","interactionEvents":2,"clientCorroboratedEvents":1,
             "temporalTransitionEvents":1,"verifiedClientOutcomes":0}]}
        output=module.compile_workflows(plan)
        self.assertEqual(output["summary"]["clientCorroborated"],1)
        self.assertFalse(output["workflows"][0]["automaticallyExecutable"])
        review=module.render_review(output)
        self.assertIn("rebirth",review)
        self.assertIn("client-state-corroborated",review)
        self.assertIn("\n## Release decision",review)
    def test_unverified_observable_candidates_are_ranked_without_approval(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"sample"},"features":[
            {"feature":"rewards","interactionEvents":3,"clientCorroboratedEvents":0,
             "temporalTransitionEvents":2,"verifiedClientOutcomes":0,
             "observableOutcomeCandidates":2,"featureStateCorrelations":1,
             "featureGuiCorrelations":1}]}
        output=module.compile_workflows(plan)
        workflow=output["workflows"][0]
        self.assertEqual(workflow["evidenceLevel"],"observable-outcome-candidate-unverified")
        self.assertEqual(workflow["observableOutcomeCandidates"],2)
        self.assertEqual(output["summary"]["observableOutcomeCandidates"],2)
        self.assertFalse(any(output["claims"].values()))
        self.assertFalse(workflow["reproducibleActionContract"])
        self.assertFalse(workflow["automaticallyExecutable"])
        self.assertIn("correlation, not causal proof",module.render_review(output))
    def test_inconsistent_candidate_counters_are_reported_not_blocking(self):
        plan={"integrity":{"scanComplete":True,"placeId":123},"features":[
            {"feature":"pets","interactionEvents":1,"clientCorroboratedEvents":0,
             "temporalTransitionEvents":0,"verifiedClientOutcomes":0,
             "observableOutcomeCandidates":1,"featureStateCorrelations":2,
             "featureGuiCorrelations":1}]}
        output=module.compile_workflows(plan)
        workflow=output["workflows"][0]
        self.assertTrue(workflow["counterDiagnostics"]["inconsistent"])
        self.assertIn("featureStateCorrelations exceeds observableOutcomeCandidates", workflow["counterDiagnostics"]["issues"])
        self.assertEqual(output["summary"]["featuresWithCounterInconsistencies"],1)
    def test_incomplete(self):
        with self.assertRaises(ValueError):
            module.compile_workflows({"integrity":{"scanComplete":False},"features":[]})
if __name__=="__main__":
    unittest.main()
