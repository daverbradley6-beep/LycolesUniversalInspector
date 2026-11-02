"""End-to-end offline build tests. Run: python3 -m unittest discover -s tests -v"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"tools"/"build_release.py"
MANIFEST_FIXTURE=ROOT/"tests"/"fixtures"/"bubble_gum_infinity_manifest_v30_sanitized.json"
spec=importlib.util.spec_from_file_location("release_builder",SOURCE)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

def make_parts(directory,missing=False,event=None):
    scan={"scanId":"testscan123","placeId":3623096087,"partCount":2,
          "version":"10.0","objects":[]}
    one=dict(scan,partIndex=1,scanStats={"recorded":2,"complete":True},
             featureEvidence={"rebirth":{}},
             objects=[{"path":"Workspace.A","class":"Part","scanOrdinal":1}])
    interaction=event or {"featureCandidate":"rebirth",
        "evidenceLevel":"interaction-observed","outcomeVerified":False}
    two=dict(scan,partIndex=2,objects=[{"path":"Workspace.B","class":"Part","scanOrdinal":2}],
             interactionHistoryChunk=[interaction])
    (directory/"1.json").write_text(json.dumps(one))
    if not missing:(directory/"2.json").write_text(json.dumps(two))

class ReleaseBuilderTests(unittest.TestCase):
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
            builder.build(parts,base/"out")
            self.assertEqual(original,z.read_bytes())
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
            make_parts(parts,event=event)
            manifest=builder.build(parts,base/"out")
            workflows=json.loads((base/"out"/"workflow-specs.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflowEvidenceSummary"]["observableOutcomeCandidates"],1)
            self.assertEqual(workflows["workflows"][0]["evidenceLevel"],"observable-outcome-candidate-unverified")
            self.assertFalse(workflows["workflows"][0]["automaticallyExecutable"])
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
