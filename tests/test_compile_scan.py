"""Run: python3 -m unittest discover -s tests -v"""
import importlib.util, json, pathlib, tempfile, unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_scan.py"
spec=importlib.util.spec_from_file_location("compiler",SOURCE)
compiler=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)

class ScanCompilerTests(unittest.TestCase):
    def parts(self,folder,missing=False,duplicate=False):
        base={"scanId":"abc12345","placeId":3623096087,"partCount":2,"version":"8.0","objects":[]}
        a=dict(base,partIndex=1,scanStats={"recorded":2,"complete":True},
               featureEvidence={"rebirth":{}},objects=[{"path":"Workspace.A","class":"Part","scanOrdinal":1}])
        b=dict(base,partIndex=2,interactionHistoryChunk=[{"featureCandidate":"rebirth","evidenceLevel":"interaction-observed","outcomeVerified":False}],
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
    def test_mixed_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);self.parts(path)
            b=json.loads((path/"2.json").read_text());b["scanId"]="other123"
            (path/"2.json").write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,"Mixed scan"):compiler.compile_scan(path)
if __name__=="__main__":unittest.main()
