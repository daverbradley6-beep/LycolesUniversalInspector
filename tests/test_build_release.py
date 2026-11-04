"""End-to-end offline build tests. Run: python3 -m unittest discover -s tests -v"""
import importlib.util
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
TRANSPORT_FIXTURE=ROOT/"tests"/"fixtures"/"report_transport_v301_cases.json"
TRANSPORT_CASES=json.loads(TRANSPORT_FIXTURE.read_text(encoding="utf-8"))["cases"]

def transport_snapshot(case,expected_parts):
    transport=json.loads(json.dumps(case["reportTransport"]))
    acknowledged=transport["acknowledgedParts"]
    if acknowledged=="ALL":acknowledged=expected_parts
    elif acknowledged=="ALL_BUT_ONE":acknowledged=expected_parts-1
    elif acknowledged=="PARTIAL":acknowledged=max(1,expected_parts//2)
    transport["acknowledgedParts"]=acknowledged
    transport["expectedParts"]=expected_parts
    return transport

SOURCE=ROOT/"tools"/"build_release.py"
MANIFEST_FIXTURE=ROOT/"tests"/"fixtures"/"bubble_gum_infinity_manifest_v30_sanitized.json"
spec=importlib.util.spec_from_file_location("release_builder",SOURCE)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

def make_parts(directory,missing=False,event=None,transport=None,request=None,
               scan_id="testscan123",scan_mode=None):
    scan={"scanId":scan_id,"placeId":3623096087,"partCount":2,
          "version":"10.0","objects":[]}
    scan_stats={"recorded":2,"complete":True}
    if scan_mode is not None:scan_stats["mode"]=scan_mode
    one=dict(scan,partIndex=1,scanStats=scan_stats,
             featureEvidence={"rebirth":{}},featureRequest=request,
             objects=[{"path":"Workspace.A","class":"Part","scanOrdinal":1}])
    interaction=event or {"featureCandidate":"rebirth",
        "evidenceLevel":"interaction-observed","outcomeVerified":False}
    two=dict(scan,partIndex=2,objects=[{"path":"Workspace.B","class":"Part","scanOrdinal":2}],
             interactionHistoryChunk=[interaction])
    (directory/"1.json").write_text(json.dumps(one))
    if not missing:(directory/"2.json").write_text(json.dumps(two))
    if transport is not None:
        manifest={"scanId":scan["scanId"],"placeId":scan["placeId"],
                  "objectCount":2,"partCount":2,"expectedParts":2,
                  "reportTransport":transport}
        (directory/"manifest.json").write_text(json.dumps(manifest))

class ReleaseBuilderTests(unittest.TestCase):
    def test_correlated_egg_prompt_generates_executable_trial(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            event={"featureCandidate":"pets","path":"Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
                "controlType":"ProximityPrompt.Triggered","evidenceLevel":"temporal-state-change-observed",
                "outcomeVerified":False,"stateChanges":[{"key":"leaderstats.🥚 Hatches","before":285,"after":286}]}
            make_parts(parts,event=event,
                request="Automatically hatch the selected egg in multi mode")
            first=json.loads((parts/"1.json").read_text())
            first["featureEvidence"]={"pets":{}}
            first["objects"][0]={"path":event["path"],"class":"ProximityPrompt","scanOrdinal":1,
                "interaction":{"actionText":"Hatch","objectText":"Rainbow Egg","holdDuration":0,
                    "maxActivationDistance":10}}
            (parts/"1.json").write_text(json.dumps(first))
            manifest=builder.build(parts,base/"out")
            self.assertTrue(manifest["promptInteractionTrial"]["generated"])
            self.assertTrue(manifest["promptInteractionTrial"]["automaticMovement"])
            self.assertFalse(manifest["promptInteractionTrial"]["gameplayVerified"])
            self.assertTrue(manifest["eggAutofarmTrial"]["compatibilityAlias"])
            source=(base/"out"/"LycolesGeneratedUtility.lua").read_text()
            readiness=json.loads((base/"out"/"generation-readiness.json").read_text())
            self.assertEqual(readiness["request"]["status"],"generated-bounded-subset")
            self.assertTrue(readiness["request"]["generatedSubsetAvailable"])
            self.assertFalse(readiness["request"]["fullRequestImplemented"])
            self.assertEqual(readiness["generatedCapabilities"][0]["targetLabel"],"Rainbow Egg")
            self.assertEqual([item["id"] for item in readiness["unavailableRequestedBehavior"]],
                ["auto-game-mode","multi-game-mode"])
            self.assertEqual(manifest["generationReadiness"]["summary"],readiness["summary"])
            self.assertRegex(manifest["generationReadiness"]["sha256"],r"^[a-f0-9]{64}$")
            self.assertEqual(manifest["generationReadiness"]["sha256"],
                hashlib.sha256((base/"out"/"generation-readiness.json").read_bytes()).hexdigest())
            self.assertIn("Generation request: generated-bounded-subset",source)
            self.assertIn("Unavailable: multi-game-mode",source)

            self.assertIn("fireproximityprompt(prompt)",source)
            self.assertIn("interactionstart=",source)
            self.assertIn("interactionstop=",source)

            self.assertIn('_G.LycolesGameCommands={',source)
            self.assertIn('definition.category:match("^Game[:%w%s%-]+$")',source)
            self.assertTrue((base/"out"/"LycolesPromptInteractions.lua").exists())
            self.assertFalse((base/"out"/"LycolesEggAutofarm.lua").exists())

    def test_prompt_feedback_is_evaluated_and_bundled_without_verification_upgrade(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            event={"featureCandidate":"pets","path":"Workspace.Egg.Prompt.ProximityPrompt",
                "controlType":"ProximityPrompt.Triggered","evidenceLevel":"temporal-state-change-observed",
                "outcomeVerified":False,"stateChanges":[{"key":"leaderstats.Hatches","before":5,"after":6}]}
            make_parts(parts,event=event)
            first=json.loads((parts/"1.json").read_text())
            first["featureEvidence"]={"pets":{}}
            first["objects"][0]={"path":event["path"],"class":"ProximityPrompt","scanOrdinal":1,
                "interaction":{"actionText":"Hatch","objectText":"Egg","holdDuration":0,
                    "maxActivationDistance":10}}
            (parts/"1.json").write_text(json.dumps(first))
            builder.build(parts,base/"initial")
            discovery=json.loads((base/"initial"/"action-capabilities.json").read_text())
            target=discovery["promptInteractions"]["targets"][0]
            raw=json.dumps(discovery,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
            feedback={"schemaVersion":"112.prompt-trial-feedback.1",
                "placeId":discovery["placeId"],"scanId":discovery["scanId"],
                "discoverySHA256":hashlib.sha256(raw).hexdigest(),"sessionId":"release-test-session",
                "entries":[{"sequence":1,"targetPath":target["path"],
                    "outcomeKey":target["selectedOutcome"]["key"],
                    "expected":target["selectedOutcome"]["change"],"before":5,"after":6,
                    "observedExpectedChange":True,"status":"expected-change-observed",
                    "message":"bounded test observation","observedAtUnix":1793635200}],
                "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
                    "serverAuthorityVerified":False,"runtimeVerified":False,
                    "gameplayVerified":False,"actionOutcomesVerified":False}}
            feedback_path=base/"feedback.json";feedback_path.write_text(json.dumps(feedback))
            manifest=builder.build(parts,base/"out",prompt_feedback_path=feedback_path)
            summary=manifest["promptTrialFeedback"]
            self.assertTrue(summary["submitted"])
            self.assertEqual(summary["expectedChangesObserved"],1)
            self.assertFalse(summary["runtimeVerified"])
            evaluated=json.loads((base/"out"/"prompt-trial-evaluation.json").read_text())
            self.assertFalse(evaluated["gameplayVerified"])
            with zipfile.ZipFile(next((base/"out").glob("*.zip"))) as archive:
                self.assertIn("prompt-trial-evaluation.json",archive.namelist())



    def test_build_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            make_parts(parts)
            first=builder.build(parts,base/"out")
            self.assertEqual(first["validation"]["expectedControls"],4)
            self.assertEqual(first["implementedGameplayAutomation"],[])
            z=next((base/"out").glob("*.zip"))
            original=z.read_bytes()
            with zipfile.ZipFile(z) as archive:
                self.assertIn("LycolesGeneratedUtility.lua",archive.namelist())
                self.assertIn("release-manifest.json",archive.namelist())
                self.assertIn("feature-coverage.json",archive.namelist())
                self.assertIn("review-contracts-template.json",archive.namelist())
                self.assertIn("source-provenance.json",archive.namelist())
                self.assertIn("gameplay-understanding.json",archive.namelist())
                self.assertIn("generation-readiness.json",archive.namelist())
                self.assertIn("LycolesAdminCommands.lua",archive.namelist())
                result_name="Lycoles-3623096087-generated-result.json"
                self.assertIn(result_name,archive.namelist())
                generated_result=json.loads(archive.read(result_name))
                self.assertFalse(generated_result["packageAuthenticityVerified"])
                self.assertFalse(generated_result["executionAuthorized"])

            admin=(base/"out"/"LycolesAdminCommands.lua").read_text()
            combined=(base/"out"/"LycolesGeneratedUtility.lua").read_text()
            self.assertEqual(first["adminCommandFramework"]["commands"],
                ["fly","unfly","noclip","clip","tp","goto","speed","jump",
                 "coords","systems","readiness","reset","rejoin","cmds","help","stopall","hidegui"])
            self.assertFalse(first["adminCommandFramework"]["runtimeVerified"])
            self.assertIn("Admin Commands",first["implementedClientControls"])
            self.assertIn("Lycoles universal local utility commands",admin)
            self.assertIn("System candidates (unverified)",admin)
            self.assertIn("Generation readiness: no-capability-requested",admin)
            self.assertIn("bounded generated: 0",admin)
            self.assertIn(admin,combined)
            self.assertNotIn("FireServer(",admin)
            self.assertNotIn("InvokeServer(",admin)
            gameplay=json.loads((base/"out"/"gameplay-understanding.json").read_text())
            generated=(base/"out"/"LycolesGeneratedUtility.lua").read_text()
            self.assertEqual(gameplay["model"],"composable_capabilities")
            self.assertFalse(gameplay["claims"]["gameplayVerified"])
            self.assertEqual(first["gameplayUnderstanding"]["summary"],gameplay["summary"])
            self.assertRegex(first["gameplayUnderstanding"]["sha256"],r"^[a-f0-9]{64}$")
            self.assertIn("Gameplay systems:",generated)
            self.assertIn("No gameplay mechanics are verified",generated)
            provenance=json.loads((base/"out"/"source-provenance.json").read_text())
            self.assertEqual(provenance["inputMode"],"local-multipart")
            self.assertFalse(provenance["receiverIntegrityVerified"])
            self.assertFalse(provenance["receiverResponseAuthenticityVerified"])
            self.assertFalse(provenance["localPayloadEquivalent"])
            self.assertFalse(provenance["replayable"])
            self.assertFalse(provenance["actionOutcomesVerified"])
            builder.build(parts,base/"out")
            self.assertEqual(original,z.read_bytes())
    def test_request_blockers_reach_generated_utility(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            make_parts(parts,request="Automatically hatch selected egg in multi mode")
            manifest=builder.build(parts,base/"out")
            blockers=manifest["gameplayUnderstanding"]["requestedCapabilityAssessment"]["blockers"]
            self.assertIn("egg_selection_observation",blockers)
            self.assertIn("mode_selection_observation",blockers)
            generated=(base/"out"/"LycolesGeneratedUtility.lua").read_text()
            self.assertIn("Request missing:",generated)
            self.assertIn("egg_selection_observation",generated)
    def test_dynamic_overlay_provenance_remains_separate_from_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            observations=base/"observations";observations.mkdir()
            make_parts(parts)
            make_parts(observations,scan_id="dynamic456",scan_mode="dynamic-observations")
            output=base/"out"
            manifest=builder.build(parts,output,observation_dirs=[observations])
            baseline=json.loads((output/"source-provenance.json").read_text())
            overlays=json.loads((output/"evidence-overlay-provenance.json").read_text())
            generated=(output/"LycolesGeneratedUtility.lua").read_text()
            bundled_readme=(output/"README.txt").read_text()
            self.assertEqual(baseline["scanId"],"testscan123")
            self.assertEqual(overlays["baselineScanId"],"testscan123")
            self.assertEqual(overlays["overlayCount"],1)
            self.assertEqual(overlays["overlays"][0]["scanId"],"dynamic456")
            self.assertEqual(overlays["overlays"][0]["sourceProvenance"]["scanId"],"dynamic456")
            self.assertFalse(overlays["sourceAuthenticityVerified"])
            self.assertEqual(manifest["evidenceOverlayProvenance"]["overlayCount"],1)
            self.assertRegex(manifest["evidenceOverlayProvenance"]["sha256"],r"^[a-f0-9]{64}$")
            self.assertIn("Dynamic evidence overlays: 1",generated)
            self.assertIn("separate provenance",bundled_readme)
            with zipfile.ZipFile(next(output.glob("*.zip"))) as archive:
                self.assertIn("evidence-overlay-provenance.json",archive.namelist())
    def test_v301_candidate_reaches_workflow_artifacts_without_action_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            event={"featureCandidate":"rebirth","evidenceLevel":"temporal-state-change-observed",
                   "outcomeVerified":False,"featureStateEvidence":{
                       "feature":"rebirth","classification":"feature-consistent-observable-change",
                       "status":"candidate-needs-causal-validation","matchedKeys":["Data.Rebirths"],
                       "sourceAuthenticityVerified":False,"causalityProven":False,
                       "serverVerified":False,"gameplayVerified":False},
                   "observableOutcomeCandidate":{
                       "feature":"rebirth","classification":"feature-consistent-observable-change",
                       "evidenceKinds":["state-change"],"overlappingInteractionsPossible":True,
                       "sourceAuthenticityVerified":False,"causalityProven":False,
                       "serverAuthorityVerified":False,"gameplayVerified":False}}
            request="Show observable rebirth status"
            make_parts(parts,event=event,request=request)
            manifest=builder.build(parts,base/"out")
            workflows=json.loads((base/"out"/"workflow-specs.json").read_text(encoding="utf-8"))
            plan=json.loads((base/"out"/"capability-plan.json").read_text(encoding="utf-8"))
            generated=(base/"out"/"LycolesGeneratedUtility.lua").read_text(encoding="utf-8")
            self.assertEqual(manifest["workflowEvidenceSummary"]["observableOutcomeCandidates"],1)
            self.assertEqual(workflows["workflows"][0]["evidenceLevel"],"observable-outcome-candidate-unverified")
            self.assertFalse(workflows["workflows"][0]["automaticallyExecutable"])
            self.assertEqual(plan["requestedCapability"],request)
            self.assertEqual(manifest["requestedCapability"],request)
            self.assertIn("Requested capability: "+request,generated)
            self.assertIn("Request status: evidence review only; gameplay is unverified",generated)
            self.assertEqual(manifest["implementedGameplayAutomation"],[])
    def test_transport_lifecycle_manifests_are_multipart_compatible(self):
        for index,case in enumerate(TRANSPORT_CASES):
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as temp:
                base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
                make_parts(parts,transport=transport_snapshot(case,2))
                output=base/f"out-{index}"
                manifest=builder.build(parts,output)
                plan=json.loads((output/"capability-plan.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["scanId"],"testscan123")
                self.assertEqual(plan["integrity"]["parts"],2)
                self.assertEqual(manifest["implementedGameplayAutomation"],[])
    def test_incomplete_scan_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            make_parts(parts,missing=True)
            with self.assertRaisesRegex(ValueError,"Missing parts"):
                builder.build(parts,base/"out")
    def test_manifest_only_input_emits_structured_blockers_without_release(self):
        with tempfile.TemporaryDirectory() as temp:
            output=pathlib.Path(temp)/"out"
            result=builder.build(MANIFEST_FIXTURE,output)
            self.assertFalse(result["generationReadiness"]["scriptGenerationReady"])
            self.assertIn("full_multipart_report_unavailable",result["generationReadiness"]["blockers"])
            self.assertTrue((output/"manifest-readiness-v109.json").is_file())
            self.assertFalse(any(output.glob("*.zip")))
            self.assertFalse((output/"LycolesGeneratedUtility.lua").exists())
    def test_manifest_only_cli_returns_blocked_status_with_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            output=pathlib.Path(temp)/"out"
            completed=subprocess.run(
                [sys.executable,str(SOURCE),str(MANIFEST_FIXTURE),"--output",str(output)],
                capture_output=True,text=True,check=False)
            self.assertEqual(completed.returncode,2)
            self.assertIn("BUILD BLOCKED: manifest-only input",completed.stderr)
            report=json.loads((output/"manifest-readiness-v109.json").read_text(encoding="utf-8"))
            self.assertFalse(report["claims"]["gameplayVerified"])
    def test_manifest_only_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);link=base/"manifest.json"
            link.symlink_to(MANIFEST_FIXTURE)
            with self.assertRaisesRegex(ValueError,"invalid manifest input"):
                builder.build(link,base/"out")
    def test_disallowed_operations_rejected(self):
        with self.assertRaisesRegex(ValueError,"Forbidden"):
            builder.validate_lua(builder.load_module('generate_script.py','test_generator').render({'integrity':{'placeId':1,'scanComplete':True},'features':[]})+'\nFireServer(1)',1)
    def test_place_guard_required(self):
        with self.assertRaisesRegex(ValueError,"place guard"):
            builder.validate_lua("local x=1",123)
if __name__=="__main__":unittest.main()
