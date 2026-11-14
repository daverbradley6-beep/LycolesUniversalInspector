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
            discovery=result["universalDiscovery"]
            self.assertEqual(discovery["schemaVersion"],"30.7.universal-discovery.1")
            self.assertIn("summary",discovery)
            self.assertIn("interactables",discovery)

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

    def test_universal_discovery_extracts_interactable_and_state_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            event={"path":"Workspace.Egg.Prompt","controlType":"ProximityPrompt.Triggered",
                "featureCandidate":"pets","evidenceLevel":"temporal-state-change-observed",
                "outcomeVerified":False,
                "stateChanges":[{"key":"leaderstats.Coins","before":100,"after":90}]}
            self.parts(path,event=event)
            first=json.loads((path/"1.json").read_text())
            first["scanStats"]["recorded"]=3
            first["objects"]=[
                {"path":"Workspace.Egg.Prompt","class":"ProximityPrompt","scanOrdinal":1,
                    "interaction":{"actionText":"Hatch","objectText":"Rainbow Egg",
                        "holdDuration":0,"maxActivationDistance":10,
                        "anchorPath":"Workspace.Egg","anchorPosition":{"x":1,"y":2,"z":3}}},
                {"path":"Workspace.Worlds.Overworld.ShopDoor","class":"Part",
                    "scanOrdinal":2,"position":{"x":10,"y":15,"z":20},
                    "attributes":{"Cost":5000}},
            ]
            (path/"1.json").write_text(json.dumps(first))
            result=compiler.compile_scan(path)
            discovery=result["universalDiscovery"]
            self.assertGreaterEqual(len(discovery["interactables"]),1)
            self.assertEqual(discovery["interactables"][0]["mechanism"],"proximity_prompt")
            self.assertEqual(discovery["interactables"][0]["position"],{"x":1.0,"y":2.0,"z":3.0})
            self.assertGreaterEqual(len(discovery["regions"]),1)
            self.assertTrue(any(item["classification"]=="requirement_or_cost_signal"
                for item in discovery["economySignals"]))
            self.assertTrue(any(item["key"]=="leaderstats.Coins"
                for item in discovery["stateChangeSignals"]))

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
            result=compiler.compile_scan(path)
            self.assertNotIn("pathIdentity",result["observedInteractionHistory"][0])

            event["pathIdentity"][1].update(name="Other",ordinal=2)
            self.parts(path,event=event)
            result=compiler.compile_scan(path)
            self.assertNotIn("pathIdentity",result["observedInteractionHistory"][0])

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


    def test_input_event_callback_baseline_source_is_accepted(self):
        event={"path":"PlayerGui.Shop.Buy","controlType":"InputBegan.MouseButton1",
            "featureCandidate":"shops","evidenceLevel":"interaction-observed",
            "outcomeVerified":False,"baselineSource":"input-event-callback",
            "baselineTiming":"input-event-callback","baselineAgeSeconds":None,
            "preActivationBaselineAvailable":False}
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path,event=event)
            result=compiler.compile_scan(path)
            feature=next(item for item in result["features"] if item["feature"]=="shops")
            self.assertEqual(feature["activationCallbackBaselineEvents"],1)
            self.assertEqual(feature["preActivationBaselineEvents"],0)

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


    def test_legacy_unattributed_callback_baseline_is_tolerated_with_loss_flag(self):
        diagnostics={"callbacksFired":1,"preActivationListenersAttached":2329,
            "preActivationCaptures":0,"preActivationBaselinesUsed":0,
            "callbackBaselinesUsed":0,"stalePreActivationCaptures":0,
            "preActivationCaptureFailures":0,"pendingObservationEvents":0,
            "observationWindowsExpected":3,"observationWindowsCompleted":2,
            "observationWindowsFailed":0,"observationWindowAccountingValid":False,
            "evidenceLossPossible":False,"observationWindowsSeconds":[0.35,1.25,3.0],
            "baselineTimingPolicy":"pre-activation when a bounded supported signal is fresh; otherwise explicit activation-callback fallback"}
        summary=compiler._interaction_observation_summary(diagnostics)
        self.assertTrue(summary["evidenceLossPossible"])
        self.assertFalse(summary["observationWindowAccountingValid"])
        self.assertIn("one or more callbacks had no attributed baseline at export time",
            summary["limitations"])




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

    def test_chunked_interaction_diagnostics_are_reconstructed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan123","placeId":3623096087,"partCount":4,
                  "version":"30.6.52","objects":[]}
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "historyExportMode":"separate-bounded-parts",
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":3,
                    "cursorObservationHistoryExportMode":"separate-bounded-parts",
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[
                    {"sampleType":"mouse-movement","source":"MouseMovement"},
                    {"sampleType":"mouse-movement","source":"MouseMovement"},
                ])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=3,
                interactionDiagnosticsChunk=[
                    {"sampleType":"mouse-click","source":"MouseButton1"},
                ])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            plan=compiler.compile_scan(path)
            self.assertEqual(plan["integrity"]["objects"],2)
            self.assertEqual(plan["integrity"]["interactionEvents"],0)
            self.assertEqual(
                len((plan.get("interactionDiagnostics") or {}).get("cursorObservationHistory") or []),
                3,
            )

    def test_chunked_interaction_diagnostics_sequence_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan124","placeId":3623096087,"partCount":4,
                  "version":"30.6.52","objects":[]}
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":3,
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{"sampleType":"mouse-movement"}])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=3,
                interactionDiagnosticsChunk=[{"sampleType":"mouse-click"}])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"chunk sequence mismatch"):
                compiler.compile_scan(path)

    def test_chunked_interaction_diagnostics_multi_key_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan125","placeId":3623096087,"partCount":5,
                  "version":"30.6.53","objects":[]}
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":2,
                    "clickTargetObservations":[],
                    "clickTargetObservationsTotal":2,
                })
            cursor_chunk=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[
                    {"sampleType":"mouse-movement"},
                    {"sampleType":"mouse-click"},
                ])
            click_chunk_one=dict(base,partIndex=3,interactionDiagnosticsChunkKey="clickTargetObservations",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{"id":"click_1"}])
            click_chunk_two=dict(base,partIndex=4,interactionDiagnosticsChunkKey="clickTargetObservations",
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{"id":"click_2"}])
            objects=dict(base,partIndex=5,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,cursor_chunk,click_chunk_one,click_chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            plan=compiler.compile_scan(path)
            diagnostics=plan.get("interactionDiagnostics") or {}
            self.assertEqual(len(diagnostics.get("cursorObservationHistory") or []),2)
            self.assertEqual(len(diagnostics.get("clickTargetObservations") or []),2)
            self.assertEqual((diagnostics.get("clickTargetObservations") or [])[1].get("id"),"click_2")


    def test_chunked_interaction_summary_fragments_are_reconstructed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan126","placeId":3623096087,"partCount":4,
                  "version":"30.6.67","objects":[]}
            summary_payload={
                "schemaVersion":"31.0.targeted-evidence-session.1",
                "sessionId":"targeted-session-1",
                "samples":{
                    "cameraSamples":[{"kind":"camera","x":1},{"kind":"camera","x":2}],
                    "timelineEvents":[{"kind":"timeline","step":1}],
                },
                "requestProgress":{"combat-camera-weapon-correlation":{"status":"collecting"}},
            }
            encoded=json.dumps(summary_payload,sort_keys=True,separators=(",",":"))
            midpoint=max(1,len(encoded)//2)
            first_fragment=encoded[:midpoint]
            second_fragment=encoded[midpoint:]
            chunk_key="targetedCaptureSessionSummaryChunkedFragments"
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "targetedCaptureSessionSummary":{},
                    "targetedCaptureSessionSummaryExportMode":"separate-bounded-parts",
                    "targetedCaptureSessionSummaryChunkSchema":"30.6.interaction-diagnostics-fragment-chunk.1",
                    "targetedCaptureSessionSummaryChunkKind":"json-fragment",
                    "targetedCaptureSessionSummaryChunkKey":chunk_key,
                    "targetedCaptureSessionSummaryEncodedLength":len(encoded),
                    "chunkedInteractionDiagnosticSummaryFields":[{
                        "field":"targetedCaptureSessionSummary",
                        "chunkKey":chunk_key,
                        "chunkKind":"json-fragment",
                        "encodedLength":len(encoded),
                        "fragmentCount":2,
                    }],
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "fragmentIndex":1,
                    "fragment":first_fragment,
                    "fragmentLength":len(first_fragment),
                }])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{
                    "fragmentIndex":2,
                    "fragment":second_fragment,
                    "fragmentLength":len(second_fragment),
                }])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            plan=compiler.compile_scan(path)
            diagnostics=plan.get("interactionDiagnostics") or {}
            rebuilt=diagnostics.get("targetedCaptureSessionSummary") or {}
            self.assertEqual(rebuilt.get("schemaVersion"),"31.0.targeted-evidence-session.1")
            samples=rebuilt.get("samples") or {}
            self.assertEqual(len(samples.get("cameraSamples") or []),2)
            self.assertEqual(len(samples.get("timelineEvents") or []),1)

    def test_chunked_interaction_summary_hex_fragments_are_reconstructed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan132","placeId":3623096087,"partCount":4,
                  "version":"30.6.68","objects":[]}
            payload={
                "schemaVersion":"31.0.targeted-evidence-session.1",
                "sessionId":"hex-summary-session",
                "samples":{
                    "cameraSamples":[{"kind":"camera","note":"🔥"*60}],
                    "timelineEvents":[{"kind":"timeline","step":7}],
                },
            }
            encoded=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
            hex_payload=encoded.encode("utf-8").hex()
            split=max(2,len(hex_payload)//2)
            chunk_key="targetedCaptureSessionSummaryChunkedFragments"
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "targetedCaptureSessionSummary":{},
                    "targetedCaptureSessionSummaryExportMode":"separate-bounded-parts",
                    "targetedCaptureSessionSummaryChunkSchema":"30.6.interaction-diagnostics-fragment-chunk.2",
                    "targetedCaptureSessionSummaryChunkKind":"json-fragment",
                    "targetedCaptureSessionSummaryChunkEncoding":"hex-utf8-json",
                    "targetedCaptureSessionSummaryChunkKey":chunk_key,
                    "targetedCaptureSessionSummaryEncodedLength":len(encoded),
                    "chunkedInteractionDiagnosticSummaryFields":[{
                        "field":"targetedCaptureSessionSummary",
                        "chunkKey":chunk_key,
                        "chunkKind":"json-fragment",
                        "chunkEncoding":"hex-utf8-json",
                        "encodedLength":len(encoded),
                        "fragmentCount":2,
                    }],
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-fragment-chunk.2",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":2,
                    "fragmentHex":hex_payload[:split],
                    "fragmentHexLength":len(hex_payload[:split]),
                }])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-fragment-chunk.2",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":2,
                    "fragmentCount":2,
                    "fragmentHex":hex_payload[split:],
                    "fragmentHexLength":len(hex_payload[split:]),
                }])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data,ensure_ascii=False))
            plan=compiler.compile_scan(path)
            rebuilt=((plan.get("interactionDiagnostics") or {}).get("targetedCaptureSessionSummary") or {})
            self.assertEqual(rebuilt.get("sessionId"),"hex-summary-session")
            samples=rebuilt.get("samples") or {}
            self.assertEqual(len(samples.get("cameraSamples") or []),1)

    def test_chunked_interaction_summary_fragment_sequence_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan127","placeId":3623096087,"partCount":4,
                  "version":"30.6.67","objects":[]}
            payload={"schemaVersion":"31.0.targeted-evidence-session.1","samples":{"cameraSamples":[{"x":1}]}}
            encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
            midpoint=max(1,len(encoded)//2)
            chunk_key="targetedCaptureSessionSummaryChunkedFragments"
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "targetedCaptureSessionSummary":{},
                    "targetedCaptureSessionSummaryChunkKey":chunk_key,
                    "chunkedInteractionDiagnosticSummaryFields":[{
                        "field":"targetedCaptureSessionSummary",
                        "chunkKey":chunk_key,
                        "chunkKind":"json-fragment",
                        "encodedLength":len(encoded),
                        "fragmentCount":2,
                    }],
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{"fragmentIndex":1,"fragment":encoded[:midpoint],"fragmentLength":len(encoded[:midpoint])}])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{"fragmentIndex":3,"fragment":encoded[midpoint:],"fragmentLength":len(encoded[midpoint:])}])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"summary fragment sequence"):
                compiler.compile_scan(path)


    def test_chunked_diagnostic_item_fragments_reconstruct_with_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan128","placeId":3623096087,"partCount":4,
                  "version":"30.6.68","objects":[]}
            original={
                "sampleType":"click-target",
                "path":"LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Selected.Action.Button",
                "context":{
                    "note":"火"*1400,
                    "nested":{"values":[{"label":"δ","enabled":True},{"label":"λ","enabled":False}]},
                },
            }
            encoded=json.dumps(original,sort_keys=True,separators=(",",":"),ensure_ascii=False)
            hex_payload=encoded.encode("utf-8").hex()
            split=max(2,len(hex_payload)//2)
            fragment_one=hex_payload[:split]
            fragment_two=hex_payload[split:]
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "clickTargetObservations":[],
                    "clickTargetObservationsTotal":1,
                    "clickTargetObservationsExportMode":"separate-bounded-parts",
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey="clickTargetObservations",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "chunkKind":"diagnostic-item-fragment",
                    "chunkKey":"clickTargetObservations",
                    "collectionKey":"clickTargetObservations",
                    "recordId":"clickTargetObservations:1",
                    "originalIndex":1,
                    "fieldPath":"interactionDiagnostics.clickTargetObservations[1]",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":2,
                    "encodedLength":len(encoded),
                    "fragmentHex":fragment_one,
                    "fragmentHexLength":len(fragment_one),
                }])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey="clickTargetObservations",
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "chunkKind":"diagnostic-item-fragment",
                    "chunkKey":"clickTargetObservations",
                    "collectionKey":"clickTargetObservations",
                    "recordId":"clickTargetObservations:1",
                    "originalIndex":1,
                    "fieldPath":"interactionDiagnostics.clickTargetObservations[1]",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":2,
                    "fragmentCount":2,
                    "encodedLength":len(encoded),
                    "fragmentHex":fragment_two,
                    "fragmentHexLength":len(fragment_two),
                }])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data,ensure_ascii=False))
            plan=compiler.compile_scan(path)
            diagnostics=plan.get("interactionDiagnostics") or {}
            rebuilt=(diagnostics.get("clickTargetObservations") or [{}])[0]
            self.assertEqual(rebuilt.get("sampleType"),"click-target")
            self.assertEqual((rebuilt.get("context") or {}).get("note"),"火"*1400)

    def test_chunked_diagnostic_item_fragment_missing_piece_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan129","placeId":3623096087,"partCount":3,
                  "version":"30.6.68","objects":[]}
            payload={"sampleType":"cursor","blob":"X"*200}
            encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
            fragment=encoded.encode("utf-8").hex()
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":1,
                })
            chunk=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "recordId":"cursorObservationHistory:1",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":2,
                    "encodedLength":len(encoded),
                    "fragmentHex":fragment,
                    "fragmentHexLength":len(fragment),
                }])
            objects=dict(base,partIndex=3,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Missing diagnostic fragments"):
                compiler.compile_scan(path)

    def test_chunked_diagnostic_item_fragment_duplicate_sequence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan130","placeId":3623096087,"partCount":4,
                  "version":"30.6.68","objects":[]}
            payload={"sampleType":"cursor","blob":"Y"*220}
            encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
            hex_payload=encoded.encode("utf-8").hex()
            split=max(2,len(hex_payload)//2)
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":1,
                })
            chunk_one=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "recordId":"cursorObservationHistory:1",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":2,
                    "encodedLength":len(encoded),
                    "fragmentHex":hex_payload[:split],
                    "fragmentHexLength":len(hex_payload[:split]),
                }])
            chunk_two=dict(base,partIndex=3,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "recordId":"cursorObservationHistory:1",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":2,
                    "encodedLength":len(encoded),
                    "fragmentHex":hex_payload[split:],
                    "fragmentHexLength":len(hex_payload[split:]),
                }])
            objects=dict(base,partIndex=4,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk_one,chunk_two,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Malformed diagnostic fragment sequence"):
                compiler.compile_scan(path)

    def test_chunked_diagnostic_item_fragment_corrupt_hex_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            base={"scanId":"chunkscan131","placeId":3623096087,"partCount":3,
                  "version":"30.6.68","objects":[]}
            payload={"sampleType":"cursor","blob":"Z"*64}
            encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
            corrupt_hex=encoded.encode("utf-8").hex()[:-2] + "gg"
            metadata=dict(base,partIndex=1,
                scanStats={"recorded":2,"complete":True},
                diagnostics={"complete":True,"rootAccountingValid":True},
                featureEvidence={"rebirth":{}},
                interactionDiagnostics={
                    "historyTotal":0,
                    "cursorObservationHistory":[],
                    "cursorObservationHistoryTotal":1,
                })
            chunk=dict(base,partIndex=2,interactionDiagnosticsChunkKey="cursorObservationHistory",
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[{
                    "schemaVersion":"30.6.interaction-diagnostics-item-fragment.1",
                    "recordId":"cursorObservationHistory:1",
                    "fragmentEncoding":"hex-utf8-json",
                    "fragmentIndex":1,
                    "fragmentCount":1,
                    "encodedLength":len(encoded),
                    "fragmentHex":corrupt_hex,
                    "fragmentHexLength":len(corrupt_hex),
                }])
            objects=dict(base,partIndex=3,objects=[
                {"path":"Workspace.A","class":"Part","scanOrdinal":1},
                {"path":"Workspace.B","class":"Part","scanOrdinal":1},
            ])
            for idx,data in enumerate((metadata,chunk,objects),1):
                (path/f"{idx}.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Corrupt diagnostic item"):
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
