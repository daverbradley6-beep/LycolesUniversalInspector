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

    def test_semantic_actions_use_bounded_context(self):
        self.assertIn("local function semanticActionKind(obj, feature)",SRC)
        self.assertIn("kind, actionSource = semanticActionKind(obj,feature)",SRC)
        self.assertIn('feature=="pets" and (lower:find("hatch",1,true) or lower:find("egg",1,true))',SRC)
        self.assertIn('if n:find("hatch",1,true) or n=="egg" then return "hatch" end',SRC)
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
