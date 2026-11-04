"""Static regression checks for inspector UI and upload semantics."""
import pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=(ROOT/"LycolesUniversalInspector.lua").read_text()
VERSION=(ROOT/"version.txt").read_text().strip()
class InspectorUITests(unittest.TestCase):
    def test_version(self):
        self.assertRegex(VERSION,r"^\d+\.\d+\.\d+$")
        self.assertIn(f'local VERSION = "{VERSION}"',SRC)
        self.assertIn(f'-- Lycoles Universal Inspector v{VERSION}',SRC)
    def test_evidence_not_in_header(self):
        self.assertIn("autoEvidenceToggle.Parent = panel",SRC)
        self.assertIn("autoEvidenceToggle.Position = UDim2.fromOffset(380, 168)",SRC)
        self.assertNotIn("autoEvidenceToggle.Parent = interactionToggle.Parent",SRC)
    def test_output_does_not_cover_sidebar(self):
        self.assertIn("Size = UDim2.fromOffset(360, 164)",SRC)
        self.assertIn("Position = UDim2.fromOffset(12, 164)",SRC)
    def test_ack_not_misrepresented_as_integrity(self):
        self.assertIn("Receiver ACK ",SRC)
        self.assertIn("verify receiver integrity separately",SRC)
        self.assertIn("Receiver ACK is not full integrity proof.",SRC)
    def test_upload_part_decode_guarded(self):
        self.assertIn("local firstOk, first = pcall",SRC)
        self.assertIn("Upload blocked: malformed first part",SRC)
    def test_budget_visible(self):
        self.assertIn("Auto rescans: ",SRC)
        self.assertIn("AUTO_EVIDENCE_MAX_RESCANS = 4",SRC)
    def test_manifest_reports_upload_lifecycle(self):
        self.assertIn("reportTransport = uploadSnapshot(\"pre-upload\")",SRC)
        self.assertIn("uploadAttempted = uploadState.attempted",SRC)
        self.assertIn("receiverIntegrityVerified = false",SRC)
        self.assertIn("downstreamReportAvailable = false",SRC)
        self.assertIn("refreshLocalManifest(\"post-upload\")",SRC)
    def test_manifest_exposes_receiver_scan_id(self):
        self.assertIn("return parts, scanId",SRC)
        self.assertIn("local parts, reportScanId = prepareParts(result)",SRC)
        self.assertIn("scanId = reportScanId",SRC)
        self.assertIn("scanId=reportScanId",SRC)
        self.assertIn(r'.. "\\nScan ID: " .. tostring(resultData.scanId)',SRC)
    def test_manifest_preserves_receiver_acknowledgement_digests(self):
        self.assertIn('type(ack.sha256) == "string"',SRC)
        self.assertIn("acknowledgedPartDigests = digests",SRC)
        self.assertIn("sha256=ack.sha256",SRC)
    def test_local_export_writes_numbered_parts_and_manifest(self):
        self.assertIn('local save = button("SAVE REPORT", 260)',SRC)
        self.assertIn('for i,body in ipairs(pendingParts) do',SRC)
        self.assertIn('prefix.."_part-"..string.format("%04d",i)..".json"',SRC)
        self.assertIn('prefix.."_manifest.json"',SRC)
        self.assertIn('pendingManifest.localExport={',SRC)
        self.assertIn('exportedParts=exported,expectedParts=#pendingParts',SRC)
        self.assertIn('localPartContentDigestsComputed=false',SRC)
        self.assertIn('Saved complete report:',SRC)

    def test_two_tab_generation_request_ui(self):
        self.assertIn('Name = "InspectorTab"',SRC)
        self.assertIn('Name = "GeneratedScriptTab"',SRC)
        self.assertIn('Name = "GeneratedScriptPane"',SRC)
        self.assertIn('PlaceholderText = "Describe the client-visible capability to generate"',SRC)
        self.assertIn('Text = "PRODUCE SCRIPT"',SRC)
        self.assertIn('report.featureRequest',SRC)
        self.assertIn('featureRequest=meta and report.featureRequest or nil',SRC)
        self.assertIn('featureRequest = result.featureRequest',SRC)
        self.assertIn('local function inspect(requestType, featureRequest)',SRC)
        self.assertIn('inspect("feature-request", request)',SRC)
        self.assertNotIn('local requestedCapability',SRC)

    def test_generated_pane_tracks_evidence_handoff_without_verification_claims(self):
        self.assertIn('local function refreshGeneratedHandoff(phase)',SRC)
        self.assertIn('Request (not evidence):',SRC)
        self.assertIn('Local export: not attempted',SRC)
        self.assertIn('; integrity unverified',SRC)
        self.assertIn('offline compilation/validation pending; gameplay unverified',SRC)
        for phase in ('Scan complete','Upload blocked','Upload started','Upload finished',
                      'Local export finished'):
            self.assertIn(f'refreshGeneratedHandoff("{phase}")',SRC)

    def test_generated_result_loader_is_place_bound_and_display_only(self):
        self.assertIn('Name = "LoadGeneratedResult", Text = "LOAD RESULT"',SRC)
        self.assertIn('"Lycoles-"..tostring(game.PlaceId).."-generated-result.json"',SRC)
        self.assertIn('result.schemaVersion=="110.generated-result.1"',SRC)
        self.assertIn('result.schemaVersion=="113.generated-result.1"',SRC)
        self.assertIn('local function validateGeneratedReadiness(result)',SRC)
        self.assertIn('readiness.schemaVersion~="113.generation-readiness.1"',SRC)
        self.assertIn('result.placeId==game.PlaceId',SRC)
        self.assertIn('result.executionAuthorized==false',SRC)
        self.assertIn('generatedCodeOutput.Text=code',SRC)
        self.assertIn('Generated bounded capabilities:',SRC)
        self.assertIn('Full request implemented: false',SRC)
        self.assertIn('Runtime/gameplay verified: false',SRC)
        self.assertIn('package authenticity, runtime, execution, and gameplay remain unverified',SRC)
        self.assertNotIn('loadstring(code)',SRC)

    def test_interactions_capture_replay_relevant_control_metadata(self):
        self.assertIn('local function interactionDescriptor(obj,root,label)',SRC)
        self.assertIn('local function interactionPathIdentity(obj,root,label)',SRC)
        self.assertIn('pathIdentity=interactionPathIdentity(obj,root,label)',SRC)
        self.assertIn('item.kind~="official-tool-activation-trial"',SRC)

        self.assertIn('local function stateValueIdentity(obj,root)',SRC)
        self.assertIn('stateIdentityStatus=identity and "component-resolved" or "unavailable"',SRC)
        self.assertIn('keyboardKeyCode=obj.KeyboardKeyCode.Name',SRC)
        self.assertIn('gamepadKeyCode=obj.GamepadKeyCode.Name',SRC)
        self.assertIn('anchorPosition=anchor and anchor:IsA("BasePart")',SRC)
        self.assertIn('signal, controlType = obj.Activated, "Tool.Activated"',SRC)
        self.assertIn('combat={"combat","attack","damage","weapon","gun","ammo","reload","shoot"}',SRC)
        self.assertIn('controlMetadata=interactionDescriptor(obj,root,label)',SRC)
        self.assertIn('enabled=obj.Enabled,manualActivationOnly=obj.ManualActivationOnly',SRC)

    def test_semantic_actions_use_bounded_context(self):
        self.assertIn("local function semanticActionKind(obj, feature)",SRC)
        self.assertIn("kind, actionSource = semanticActionKind(obj,feature)",SRC)
        self.assertIn('feature=="pets" and (lower:find("hatch",1,true) or lower:find("egg",1,true))',SRC)
        self.assertIn('if n:find("hatch",1,true) or n=="egg" then return "hatch" end',SRC)
    def test_simulator_actions_capture_progression_and_conversion(self):
        self.assertIn('progression={"progression","bubble","capacity","blow","farm"}',SRC)
        self.assertIn('shops={"shop","purchase","store","sell","upgrade"}',SRC)
        self.assertIn('return "blow"',SRC)
        self.assertIn('elseif kind=="blow" then',SRC)
        self.assertIn('elseif kind=="sell" then',SRC)
        self.assertIn('corroborated=resourceDecrease and currencyIncrease',SRC)
        self.assertIn('feature=="progression" and (key:find("bubble",1,true)',SRC)

    def test_completed_candidates_are_observable_not_verified(self):
        self.assertIn("workflowStats.completedCandidates=workflowStats.completedCandidates+1",SRC)
        self.assertIn('classification="feature-consistent-observable-change"',SRC)
        self.assertIn("causalityProven=false",SRC)
        self.assertIn("historyItem.outcomeVerified=false",SRC)
    def test_feature_readiness_uses_relevant_state_only(self):
        self.assertIn("local featureStateEvidence=featureConsistentStateEvidence(feature,transactionFresh)",SRC)
        self.assertIn("if featureStateEvidence then item.stateChanges=item.stateChanges+1 end",SRC)
        self.assertIn("observable-outcome-candidate-needs-causal-validation",SRC)
    def test_state_snapshots_include_bounded_local_player_values(self):
        self.assertIn("MAX_STATE_SNAPSHOT_CANDIDATES = 1000",SRC)
        self.assertIn('property=="Value" and label=="LocalPlayer"',SRC)
        self.assertIn("for _,candidate in ipairs(stateSnapshotCandidates) do",SRC)
        self.assertIn('local primary=top.Name=="Data" or top.Name=="leaderstats"',SRC)
if __name__=="__main__":unittest.main()
