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
    def test_incomplete(self):
        with self.assertRaises(ValueError):
            module.compile_workflows({"integrity":{"scanComplete":False},"features":[]})
if __name__=="__main__":
    unittest.main()
