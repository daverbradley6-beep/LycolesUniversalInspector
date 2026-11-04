"""Run: python3 -m unittest discover -s tests -v"""
import importlib.util, json, pathlib, tempfile, unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_scan.py"
spec=importlib.util.spec_from_file_location("compiler",SOURCE)
compiler=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)

class ScanCompilerTests(unittest.TestCase):
    def parts(self,folder,missing=False,duplicate=False,event=None):
        base={"scanId":"abc12345","placeId":3623096087,"partCount":2,"version":"8.0","objects":[]}
        a=dict(base,partIndex=1,scanStats={"recorded":2,"complete":True},
               featureEvidence={"rebirth":{}},objects=[{"path":"Workspace.A","class":"Part","scanOrdinal":1}])
        interaction=event or {"featureCandidate":"rebirth","evidenceLevel":"interaction-observed","outcomeVerified":False}
        b=dict(base,partIndex=2,interactionHistoryChunk=[interaction],
               objects=[{"path":"Workspace.A" if duplicate else "Workspace.B","class":"Part","scanOrdinal":1}])
        (folder/"1.json").write_text(json.dumps(a))
        if not missing:(folder/"2.json").write_text(json.dumps(b))
    def test_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            result=compiler.compile_scan(path)
            self.assertEqual(result["integrity"]["objects"],2)
            self.assertEqual(result["features"][0]["status"],"interaction-observed")
            self.assertFalse(result["releaseGate"]["gameplayAutomationApproved"])

    def test_local_source_provenance_binds_exact_current_part_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            expected=[compiler.hashlib.sha256((path/f"{index}.json").read_bytes()).hexdigest()
                      for index in (1,2)]
            provenance=compiler.compile_scan(path)["sourceProvenance"]
            self.assertEqual(provenance["schemaVersion"], "30.2.source-provenance.2")
            self.assertEqual(provenance["inputMode"], "local-multipart")
            self.assertTrue(provenance["localPartContentDigestsComputed"])
            self.assertEqual(
                provenance["partContentDigests"],
                [{"partIndex": index, "sha256": digest}
                 for index,digest in enumerate(expected,1)],
            )
            self.assertFalse(provenance["sourceAuthenticityVerified"])
            self.assertFalse(provenance["localPayloadEquivalent"])

    def test_actionable_objects_retain_bounded_prompt_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            first=json.loads((path/"1.json").read_text())
            first["objects"][0]={"path":"Workspace.Egg.Prompt","class":"ProximityPrompt",
                "scanOrdinal":1,"interaction":{"actionText":"Hatch","objectText":"Rainbow Egg",
                "holdDuration":0,"maxActivationDistance":10}}
            (path/"1.json").write_text(json.dumps(first))
            result=compiler.compile_scan(path)
            self.assertEqual(result["actionableObjectCount"],1)
            self.assertFalse(result["actionableObjectsTruncated"])
            self.assertEqual(result["actionableObjects"][0]["interaction"]["objectText"],"Rainbow Egg")

    def test_interaction_path_identity_is_validated_and_preserved(self):
        identity=[{"name":"Workspace","className":"Workspace","ordinal":1},
            {"name":"Egg.With.Dot","className":"Model","ordinal":2},
            {"name":"Prompt","className":"ProximityPrompt","ordinal":1}]
        event={"path":"Workspace.Egg.With.Dot.Prompt","pathIdentity":identity,
            "controlType":"ProximityPrompt.Triggered","featureCandidate":"pets",
            "evidenceLevel":"interaction-observed","outcomeVerified":False}
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,event=event)
            result=compiler.compile_scan(path)
            self.assertEqual(result["observedInteractionHistory"][0]["pathIdentity"],identity)
            event["pathIdentity"][1]["ordinal"]=0
            self.parts(path,event=event)
            with self.assertRaisesRegex(ValueError,"Malformed interaction path identity"):
                compiler.compile_scan(path)
            event["pathIdentity"][1].update(name="Other",ordinal=2)
            self.parts(path,event=event)
            with self.assertRaisesRegex(ValueError,"Malformed interaction path identity"):
                compiler.compile_scan(path)

    def test_pre_activation_baselines_and_pending_windows_are_preserved(self):
        event={"path":"PlayerGui.Shop.Buy","controlType":"GuiButton.Activated",
            "featureCandidate":"shops","evidenceLevel":"interaction-observed",
            "outcomeVerified":False,"baselineSource":"GuiButton.InputBegan",
            "baselineTiming":"pre-activation","baselineAgeSeconds":0.02,
            "preActivationBaselineAvailable":True}
        diagnostics={"callbacksFired":1,"preActivationListenersAttached":1,
            "preActivationCaptures":1,"preActivationBaselinesUsed":1,
            "callbackBaselinesUsed":0,"stalePreActivationCaptures":0,
            "preActivationCaptureFailures":0,"pendingObservationEvents":1,
            "observationWindowsExpected":3,"observationWindowsCompleted":2,
            "observationWindowsFailed":0,"observationWindowAccountingValid":True,
            "evidenceLossPossible":True,"observationWindowsSeconds":[0.35,1.25,3.0],
            "baselineTimingPolicy":"pre-activation when a bounded supported signal is fresh; otherwise explicit activation-callback fallback"}
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,event=event)
            first=json.loads((path/"1.json").read_text());first["interactionDiagnostics"]=diagnostics
            (path/"1.json").write_text(json.dumps(first))
            result=compiler.compile_scan(path)
            feature=next(item for item in result["features"] if item["feature"]=="shops")
            self.assertEqual(feature["preActivationBaselineEvents"],1)
            self.assertTrue(result["interactionObservationSummary"]["evidenceLossPossible"])
            self.assertEqual(result["interactionObservationSummary"]["pendingObservationEvents"],1)
            event["preActivationBaselineAvailable"]=False
            self.parts(path,event=event)
            with self.assertRaisesRegex(ValueError,"baseline timing"):
                compiler.compile_scan(path)
            event["preActivationBaselineAvailable"]=True;self.parts(path,event=event)
            first=json.loads((path/"1.json").read_text())
            diagnostics["evidenceLossPossible"]=False;first["interactionDiagnostics"]=diagnostics
            (path/"1.json").write_text(json.dumps(first))
            with self.assertRaisesRegex(ValueError,"observation diagnostics"):
                compiler.compile_scan(path)

    def test_session_relative_interaction_timing_is_validated(self):
        event={"path":"PlayerGui.Shop.Buy","controlType":"GuiButton.Activated",
            "featureCandidate":"shops","evidenceLevel":"interaction-observed",
            "outcomeVerified":False,"sessionId":"session-a","sessionElapsedSeconds":12.345}
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,event=event)
            first=json.loads((path/"1.json").read_text());first["sessionId"]="session-a"
            (path/"1.json").write_text(json.dumps(first))
            result=compiler.compile_scan(path)
            self.assertEqual(result["sourceDiagnostics"]["sessionTimedInteractionEvents"],1)
            self.assertTrue(result["sourceDiagnostics"]["sessionTimingComplete"])
            self.assertEqual(result["observedInteractionHistory"][0]["sessionElapsedSeconds"],12.345)
            event["sessionId"]="session-b";self.parts(path,event=event)
            first=json.loads((path/"1.json").read_text());first["sessionId"]="session-a"
            (path/"1.json").write_text(json.dumps(first))
            with self.assertRaisesRegex(ValueError,"session timing"):
                compiler.compile_scan(path)

    def test_callback_baseline_discloses_possible_synchronous_loss(self):
        diagnostics={"callbacksFired":1,"preActivationListenersAttached":0,
            "preActivationCaptures":0,"preActivationBaselinesUsed":0,
            "callbackBaselinesUsed":1,"stalePreActivationCaptures":0,
            "preActivationCaptureFailures":0,"pendingObservationEvents":0,
            "observationWindowsExpected":3,"observationWindowsCompleted":3,
            "observationWindowsFailed":0,"observationWindowAccountingValid":True,
            "evidenceLossPossible":True,"observationWindowsSeconds":[0.35,1.25,3.0],
            "baselineTimingPolicy":"pre-activation when a bounded supported signal is fresh; otherwise explicit activation-callback fallback"}
        summary=compiler._interaction_observation_summary(diagnostics)
        self.assertTrue(summary["evidenceLossPossible"])
        self.assertIn("callback-time baselines may miss synchronous activation changes",
            summary["limitations"])
        self.assertEqual(summary["preActivationCaptureFailures"],0)
        diagnostics.update({"callbacksFired":0,"preActivationBaselinesUsed":0,
            "callbackBaselinesUsed":0,"preActivationCaptureFailures":1,
            "observationWindowsExpected":0,"observationWindowsCompleted":0,
            "evidenceLossPossible":True})
        summary=compiler._interaction_observation_summary(diagnostics)
        self.assertEqual(summary["preActivationCaptureFailures"],1)
        self.assertTrue(summary["evidenceLossPossible"])
        self.assertIn("one or more pre-activation captures failed",summary["limitations"])




    def test_duplicate_part_with_different_raw_bytes_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            duplicate=json.loads((path/"1.json").read_text())
            (path/"duplicate.json").write_text(json.dumps(duplicate,indent=2))
            with self.assertRaisesRegex(ValueError,"Conflicting duplicate part bytes"):
                compiler.compile_scan(path)

    def test_missing_part(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,missing=True)
            with self.assertRaisesRegex(ValueError,"Missing parts"):compiler.compile_scan(path)
    def test_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,duplicate=True)
            with self.assertRaisesRegex(ValueError,"Duplicate object"):compiler.compile_scan(path)
    def test_v301_observable_candidate_is_preserved_as_unverified_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
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
            self.parts(path,event=event)
            feature=compiler.compile_scan(path)["features"][0]
            self.assertEqual(feature["observableOutcomeCandidates"],1)
            self.assertEqual(feature["featureStateCorrelations"],1)
            self.assertEqual(feature["featureGuiCorrelations"],0)
            self.assertFalse(feature["implementationReady"])
    def test_v301_candidate_with_positive_verification_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            event={"featureCandidate":"rebirth","evidenceLevel":"interaction-observed",
                   "outcomeVerified":False,"featureStateEvidence":{
                       "feature":"rebirth","classification":"feature-consistent-observable-change",
                       "status":"candidate-needs-causal-validation","matchedKeys":["Data.Rebirths"],
                       "sourceAuthenticityVerified":False,"causalityProven":False,
                       "serverVerified":False,"gameplayVerified":False},
                   "observableOutcomeCandidate":{
                       "feature":"rebirth","classification":"feature-consistent-observable-change",
                       "evidenceKinds":["state-change"],"overlappingInteractionsPossible":True,
                       "sourceAuthenticityVerified":False,"causalityProven":True,
                       "serverAuthorityVerified":False,"gameplayVerified":False}}
            self.parts(path,event=event)
            with self.assertRaisesRegex(ValueError,"candidate evidence claims verification"):
                compiler.compile_scan(path)
    def test_local_manifest_must_match_multipart_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            manifest={"scanId":"other123","placeId":3623096087,"objectCount":2,
                      "partCount":2,"expectedParts":2}
            (path/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,"Local manifest identity mismatch"):
                compiler.compile_scan(path)
    def test_local_manifest_must_match_multipart_object_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            manifest={"scanId":"abc12345","placeId":3623096087,"objectCount":3,
                      "partCount":2,"expectedParts":2}
            (path/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,"Local manifest object count mismatch"):
                compiler.compile_scan(path)

    def test_mixed_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            b=json.loads((path/"2.json").read_text());b["scanId"]="other123"
            (path/"2.json").write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,"Mixed scan"):compiler.compile_scan(path)
if __name__=="__main__":unittest.main()
