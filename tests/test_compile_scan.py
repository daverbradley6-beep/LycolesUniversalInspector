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
    def test_mixed_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            b=json.loads((path/"2.json").read_text());b["scanId"]="other123"
            (path/"2.json").write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,"Mixed scan"):compiler.compile_scan(path)
if __name__=="__main__":unittest.main()
