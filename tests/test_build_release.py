"""End-to-end offline build tests. Run: python3 -m unittest discover -s tests -v"""
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools"/"build_release.py"
spec=importlib.util.spec_from_file_location("release_builder",SOURCE)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

def make_parts(directory,missing=False):
    scan={"scanId":"testscan123","placeId":3623096087,"partCount":2,
          "version":"10.0","objects":[]}
    one=dict(scan,partIndex=1,scanStats={"recorded":2,"complete":True},
             featureEvidence={"rebirth":{}},
             objects=[{"path":"Workspace.A","class":"Part","scanOrdinal":1}])
    two=dict(scan,partIndex=2,objects=[{"path":"Workspace.B","class":"Part","scanOrdinal":2}],
             interactionHistoryChunk=[{"featureCandidate":"rebirth",
                 "evidenceLevel":"interaction-observed","outcomeVerified":False}])
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
    def test_incomplete_scan_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base=pathlib.Path(temp);parts=base/"parts";parts.mkdir()
            make_parts(parts,missing=True)
            with self.assertRaisesRegex(ValueError,"Missing parts"):
                builder.build(parts,base/"out")
    def test_disallowed_operations_rejected(self):
        with self.assertRaisesRegex(ValueError,"Forbidden"):
            builder.validate_lua(builder.load_module('generate_script.py','test_generator').render({'integrity':{'placeId':1,'scanComplete':True},'features':[]})+'\nFireServer(1)',1)
    def test_place_guard_required(self):
        with self.assertRaisesRegex(ValueError,"place guard"):
            builder.validate_lua("local x=1",123)
if __name__=="__main__":unittest.main()
