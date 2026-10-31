"""Static regression checks for inspector UI and upload semantics."""
import pathlib,re,unittest
SRC=(pathlib.Path(__file__).resolve().parents[1]/"LycolesUniversalInspector.lua").read_text()
class InspectorUITests(unittest.TestCase):
    def test_version(self):
        self.assertIn('local VERSION = "16.0.0"',SRC)
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
if __name__=="__main__":unittest.main()
