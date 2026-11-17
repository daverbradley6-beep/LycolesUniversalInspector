import copy
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DISCOVERY = load("prompt_feedback_discovery", "discover_action_capabilities.py")
GENERATOR = load("prompt_feedback_generator", "generate_prompt_interactions.py")
EVALUATOR = load("prompt_feedback_evaluator", "evaluate_prompt_trial_feedback.py")
FIXTURE = json.loads((ROOT / "tests" / "fixtures" /
                      "bubble_gum_infinity_manifest_v30_sanitized.json").read_text())


class PromptTrialFeedbackTests(unittest.TestCase):
    def discovery(self):
        plan = {
            "integrity": {"scanComplete": True, "placeId": FIXTURE["placeId"],
                          "scanId": "bubble-gum-feedback-scan"},
            "observedInteractionHistory": json.loads(json.dumps(
                FIXTURE["interactionDiagnostics"]["recentInteractions"])),
            "actionableObjects": [], "actionableObjectsTruncated": True,
        }
        return DISCOVERY.analyze(plan)

    def feedback(self, discovery):
        target = next(item for item in discovery["promptInteractions"]["targets"]
                      if item["trialGenerationReady"])
        outcome = target["selectedOutcome"]
        return {
            "schemaVersion": "112.prompt-trial-feedback.1",
            "placeId": discovery["placeId"], "scanId": discovery["scanId"],
            "discoverySHA256": EVALUATOR._digest(discovery),
            "sessionId": "controlled-client-session-1",
            "entries": [{
                "sequence": 1, "targetPath": target["path"],
                "outcomeKey": outcome["key"], "expected": outcome["change"],
                "before": 285, "after": 286, "observedExpectedChange": True,
                "status": "expected-change-observed",
                "message": "Observed bounded scalar direction", "observedAtUnix": 1793635200,
            }],
            "claims": {key: False for key in EVALUATOR.FALSE_CLAIMS},
        }

    def test_generated_trial_exports_discovery_bound_feedback(self):
        source = GENERATOR.render(self.discovery())
        for token in ("112.prompt-trial-feedback.1", "discoverySHA256=",
                      "_G.LycolesPromptTrialFeedback", "recordFeedback(",
                      "interactionfeedback=", "HttpService:JSONEncode(feedback)"):
            self.assertIn(token, source)

    def test_expected_change_is_ingested_as_runtime_correlation_only(self):
        discovery = self.discovery()
        result = EVALUATOR.evaluate(discovery, self.feedback(discovery))
        self.assertEqual(result["summary"], {
            "submittedAttempts": 1, "expectedChangesObserved": 1})
        self.assertTrue(result["targets"][0]["runtimeCorrelationObserved"])
        self.assertFalse(result["targets"][0]["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])
        self.assertFalse(result["causalityProven"])

    def test_feedback_digest_and_selected_outcome_are_required(self):
        discovery = self.discovery()
        feedback = self.feedback(discovery)
        feedback["discoverySHA256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            EVALUATOR.evaluate(discovery, feedback)
        feedback = self.feedback(discovery)
        feedback["entries"][0]["outcomeKey"] = "Data.Gems"
        with self.assertRaisesRegex(ValueError, "Invalid prompt feedback entry"):
            EVALUATOR.evaluate(discovery, feedback)

    def test_forged_observed_change_and_unknown_target_fail_closed(self):
        discovery = self.discovery()
        feedback = self.feedback(discovery)
        feedback["entries"][0]["after"] = 285
        with self.assertRaisesRegex(ValueError, "outcome claim mismatch"):
            EVALUATOR.evaluate(discovery, feedback)
        feedback = self.feedback(discovery)
        feedback["entries"][0]["targetPath"] = "Workspace.Forged.Prompt"
        with self.assertRaisesRegex(ValueError, "Invalid prompt feedback entry"):
            EVALUATOR.evaluate(discovery, feedback)

    def test_tool_feedback_status_is_bound_without_verification_upgrade(self):
        discovery=self.discovery();target=copy.deepcopy(next(
            item for item in discovery["promptInteractions"]["targets"]
            if item["trialGenerationReady"]))
        target.update({"path":"LocalPlayer.Backpack.Training Sword","label":"Training Sword",
            "controlType":"Tool.Activated","activationContractReady":True,
            "replayContractAvailable":True})
        discovery["promptInteractions"]["targets"]=[]
        discovery["toolInteractions"]={"targets":[target]}
        outcome=target["selectedOutcome"]
        feedback={"schemaVersion":EVALUATOR.SCHEMA,"placeId":discovery["placeId"],
            "scanId":discovery["scanId"],"discoverySHA256":EVALUATOR._digest(discovery),
            "sessionId":"controlled-tool-session","entries":[{"sequence":1,
                "targetPath":target["path"],"outcomeKey":outcome["key"],
                "expected":outcome["change"],"before":10,"after":10,
                "observedExpectedChange":False,"status":"tool-disabled",
                "message":"Observed Tool is currently disabled","observedAtUnix":1793635200},
                {"sequence":2,"targetPath":target["path"],"outcomeKey":outcome["key"],
                "expected":outcome["change"],"before":None,"after":None,
                "observedExpectedChange":False,"status":"tool-metadata-drift",
                "message":"Tool activation prerequisite metadata changed","observedAtUnix":1793635201}],
            "claims":{key:False for key in EVALUATOR.FALSE_CLAIMS}}
        result=EVALUATOR.evaluate(discovery,feedback)
        self.assertFalse(result["targets"][0]["runtimeCorrelationObserved"])
        self.assertFalse(result["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])

    def test_guided_gui_feedback_status_remains_unverified(self):
        discovery=self.discovery();target=copy.deepcopy(next(
            item for item in discovery["promptInteractions"]["targets"]
            if item["trialGenerationReady"]))
        target.update({"path":"PlayerGui.HUD.Shop.Buy","label":"Buy Upgrade",
            "controlType":"GuiButton.Activated","guidedActivationContractReady":True,
            "automaticActivationAvailable":False,"replayContractAvailable":False})
        discovery["promptInteractions"]["targets"]=[]
        discovery["guiInteractions"]={"targets":[target]}
        outcome=target["selectedOutcome"]
        feedback={"schemaVersion":EVALUATOR.SCHEMA,"placeId":discovery["placeId"],
            "scanId":discovery["scanId"],"discoverySHA256":EVALUATOR._digest(discovery),
            "sessionId":"controlled-gui-session","entries":[{"sequence":1,
                "targetPath":target["path"],"outcomeKey":outcome["key"],
                "expected":outcome["change"],"before":10,"after":None,
                "observedExpectedChange":False,"status":"gui-activation-timeout",
                "message":"Highlighted GUI control was not activated within 5 seconds",
                "observedAtUnix":1793635200}],
            "claims":{key:False for key in EVALUATOR.FALSE_CLAIMS}}
        result=EVALUATOR.evaluate(discovery,feedback)
        self.assertFalse(result["targets"][0]["runtimeCorrelationObserved"])
        self.assertFalse(result["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])



if __name__ == "__main__":
    unittest.main()
