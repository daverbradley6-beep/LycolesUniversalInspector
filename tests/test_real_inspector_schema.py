"""Real inspector multipart schema and evidence-corroboration regression tests."""
import importlib.util,json,pathlib,tempfile,unittest
source=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_scan.py"
spec=importlib.util.spec_from_file_location("scan_compiler_v11",source)
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)

class RealSchemaTests(unittest.TestCase):
    def make(self,path):
        base={"scanId":"testRealScan123","placeId":3623096087,"partCount":3,"objects":[],"sessionId":"session-1"}
        metadata=dict(base,partIndex=1,scanStats={"recorded":2,"complete":True,"mode":"universal-snapshot-v4.1","omitted":5},
            diagnostics={"complete":True,"rootAccountingValid":True},
            featureReadiness={"rebirth":{"readiness":"state-change-candidate-needs-validation"}},
            featureEvidence={"rebirth":{"status":"candidate-needs-verification"}},
            interactionDiagnostics={"historyTotal":1})
        event={"featureCandidate":"rebirth","evidenceLevel":"temporal-state-change-observed",
               "clientStateCorroborated":True,"outcomeVerified":False,
               "stateChanges":[{"key":"leaderstats.Rebirths","before":8,"after":9}]}
        history=dict(base,partIndex=2,interactionHistoryChunk=[event],interactionHistoryStart=1)
        objects=dict(base,partIndex=3,objects=[
            {"path":"Workspace.PartA","class":"Part"},
            {"path":"Workspace.PartB","class":"Part"}])
        for index,data in enumerate((metadata,history,objects),1):
            (path/f"part-{index}.json").write_text(json.dumps(data))
        (path/"manifest.json").write_text(json.dumps({"objectCount":2,"partCount":3}))
    def test_real_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp);self.make(p)
            plan=compiler.compile_scan(p)
            self.assertEqual(plan["integrity"]["objects"],2)
            self.assertEqual(plan["integrity"]["interactionEvents"],1)
            self.assertEqual(plan["features"][0]["clientCorroboratedEvents"],1)
            self.assertEqual(plan["features"][0]["verifiedClientOutcomes"],0)
            self.assertFalse(plan["features"][0]["implementationReady"])
            self.assertTrue(plan["sourceDiagnostics"]["rootAccountingValid"])
    def test_incomplete_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp);self.make(p)
            m=json.loads((p/"part-1.json").read_text());m["diagnostics"]["complete"]=False
            (p/"part-1.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"incomplete"):compiler.compile_scan(p)
    def test_missing_object(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp);self.make(p)
            m=json.loads((p/"part-3.json").read_text());m["objects"].pop()
            (p/"part-3.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,"Object count mismatch"):compiler.compile_scan(p)
if __name__=="__main__":unittest.main()
