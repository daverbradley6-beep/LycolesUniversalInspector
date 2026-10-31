import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]/"tools"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
actions=load("generate_client_actions")
validator=load("validate_contracts")
gui=load("generate_actions_gui")
gui_validator=load("validate_generated_gui")
draft=load("draft_client_contracts")
template=load("create_review_template")
proposer=load("propose_actions")
class ExtendedActionTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"scanComplete":True,"placeId":123,"scanId":"scan-123"},
          "features":[{"feature":"inspection"}],
          "classCounts":{"IntValue":4,"ScreenGui":2,"TextButton":3,"ProximityPrompt":2,
                         "Player":1,"Humanoid":1}}
    def test_six_actions_covered(self):
        p=self.plan()
        candidates=draft.draft(p)["proposals"]
        self.assertEqual(len(candidates),6)
        self.assertEqual({c["action"] for c in candidates},validator.ACTIONS)
        self.assertEqual(set(actions.ACTIONS),validator.ACTIONS)
    def test_review_bridge_stays_unapproved(self):
        p=self.plan()
        proposed=proposer.propose(p)
        doc=template.make_template(p,proposed)
        self.assertEqual(len(doc["contracts"]),6)
        with self.assertRaisesRegex(ValueError,"review"):
            validator.validate_contracts(p,doc)
        for contract in doc["contracts"]:contract["reviewed"]=True
        validated=validator.validate_contracts(p,doc)
        self.assertEqual(validated["clientActionsApproved"],6)
        lua=actions.render(validated)
        for name in validator.ACTIONS:self.assertIn("local function "+name+"()",lua)
        generated=gui.render(validated)
        self.assertEqual(gui_validator.validate(generated,sorted(validator.ACTIONS))["actionCount"],6)
        self.assertNotIn("FireServer(",generated)
    def test_mismatched_scan_rejected(self):
        p=self.plan()
        proposal=proposer.propose(p);proposal["scanId"]="other"
        with self.assertRaisesRegex(ValueError,"same scan"):
            template.make_template(p,proposal)
    def test_no_feature_no_reviewed_contract(self):
        p=self.plan();p["features"]=[]
        self.assertEqual(template.make_template(p,proposer.propose(p))["contracts"],[])
if __name__=="__main__":unittest.main()
