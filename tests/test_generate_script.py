"""Run with: python3 -m unittest discover -s tests -v"""
import importlib.util, pathlib, unittest
source=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_script.py"
spec=importlib.util.spec_from_file_location("generator",source)
generator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
class GeneratorTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"placeId":3623096087,"scanId":"testscan","scanComplete":True},
                "features":[{"feature":"rebirth"},{"feature":"pets"}]}
    def gameplay(self):
        return {"schemaVersion":"110.gameplay-understanding.1","placeId":3623096087,
            "scanId":"testscan","model":"composable_capabilities","genre":None,
            "objectiveCandidates":[],"progressionLoops":[],
            "systems":[{"label":"Companions","evidenceTier":"structural_candidate"}],
            "requestedCapabilityAssessment":None,"claims":{
                "sourceAuthenticityVerified":False,"primaryObjectiveVerified":False,
                "causalityProven":False,"serverAuthorityVerified":False,"replayable":False,
                "runtimeVerified":False,"gameplayVerified":False,"actionOutcomesVerified":False}}

    def test_generates_client_utility(self):
        result=generator.render(self.plan())
        self.assertIn("3623096087",result)
        self.assertIn('button("Stats"',result)
        self.assertIn('button("Menus"',result)
        self.assertIn("Receiver payload digests: unavailable",result)
        self.assertIn("Response authenticity: unverified",result)
        self.assertNotIn("FireServer(",result)
        self.assertNotIn("InvokeServer(",result)
    def test_gameplay_understanding_is_displayed_without_verification(self):
        result=generator.render(self.plan(),self.gameplay())
        self.assertIn("Gameplay systems: 1",result)
        self.assertIn("Companions [structural_candidate]",result)
        self.assertIn("No gameplay mechanics are verified",result)
    def test_forged_gameplay_understanding_is_blocked(self):
        gameplay=self.gameplay();gameplay["claims"]["gameplayVerified"]=True
        with self.assertRaisesRegex(ValueError,"gameplay understanding claims"):
            generator.render(self.plan(),gameplay)

    def test_requested_capability_is_displayed_as_unverified(self):
        plan=self.plan();plan["requestedCapability"]="Show observable pet inventory"
        result=generator.render(plan)
        self.assertIn("Requested capability: Show observable pet inventory",result)
        self.assertIn("Request status: evidence review only; gameplay is unverified",result)
    def test_receiver_overlay_is_reported_separately(self):
        provenance={"schemaVersion":"30.2.source-provenance.1",
            "inputMode":"receiver-import","scanId":"delta","placeId":3623096087,"partCount":2,
            "resumeCheckpointAuthenticated":False,"receiverResponseAuthenticityVerified":False,
            "localPayloadEquivalent":False,"sourceAuthenticityVerified":False,
            "causalityProven":False,"serverAuthorityVerified":False,"replayable":False,
            "gameplayVerified":False,"actionOutcomesVerified":False,
            "receiverStoredPayloadDigestsVerified":True,"receiverIntegrityVerified":True,
            "receiverAcknowledgementDigestEquivalent":False,
            "receiverStoredPayloadDigestsRevalidatedThisRun":True}
        plan=self.plan();plan["evidenceOverlays"]=[{
            "scanId":"delta","parts":2,"sourceProvenance":provenance}]
        result=generator.render(plan)
        self.assertIn("Dynamic evidence overlays: 1",result)
        self.assertIn("Overlay sources: 1 receiver import, 0 local multipart; separate provenance",result)
    def test_malformed_requested_capability_blocked(self):
        for request in ("x"*241,"🙂"*61,"Show\u0085status"):
            with self.subTest(request=repr(request)):
                plan=self.plan();plan["requestedCapability"]=request
                with self.assertRaisesRegex(ValueError,"Malformed requested capability"):
                    generator.render(plan)

    def test_invalid_scan_blocked(self):
        plan=self.plan();plan["integrity"]["scanComplete"]=False
        with self.assertRaises(ValueError):generator.render(plan)
    def test_malformed_feature_blocked(self):
        plan=self.plan();plan["features"]=[{"feature":4}]
        with self.assertRaises(ValueError):generator.render(plan)
    def test_forged_source_authenticity_blocked(self):
        plan=self.plan();plan["sourceProvenance"]={
            "inputMode":"receiver-import","resumeCheckpointAuthenticated":False,
            "receiverResponseAuthenticityVerified":True,"localPayloadEquivalent":False,
            "sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"gameplayVerified":False,
            "receiverStoredPayloadDigestsVerified":True,"receiverIntegrityVerified":True,
            "receiverStoredPayloadDigestsRevalidatedThisRun":True}
        with self.assertRaisesRegex(ValueError,"unsupported verification"):
            generator.render(plan)
    def test_escape_untrusted_feature_name(self):
        plan=self.plan();plan["features"]=[{"feature":'abc"\\\\\nscript'}]
        result=generator.render(plan)
        self.assertIn("abc",result)
        self.assertNotIn("FireServer(",result)
if __name__=="__main__":unittest.main()
