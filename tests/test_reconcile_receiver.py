import importlib.util
import pathlib
import unittest
path=pathlib.Path(__file__).resolve().parents[1]/"tools"/"reconcile_receiver.py"
spec=importlib.util.spec_from_file_location("reconcile_receiver",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.local={"scanId":"scan-a","placeId":3623096087,"expectedParts":755}
        self.remote={"scans":[{"scanId":"scan-a","placeId":3623096087,
                    "expectedParts":755,"indexedParts":755}],"hasMore":False}
    def test_matching_counts_not_verified(self):
        result=module.compare(self.local,self.remote)
        self.assertEqual(result["status"],"PART_COUNTS_MATCH_UNVERIFIED")
        self.assertFalse(result["verifiedEquivalent"])
    def test_missing_scan(self):
        self.remote["scans"]=[]
        self.assertEqual(module.compare(self.local,self.remote)["status"],
                         "NOT_FOUND_IN_PROVIDED_INDEX")
    def test_incomplete_pagination(self):
        self.remote["scans"]=[];self.remote["hasMore"]=True
        self.assertFalse(module.compare(self.local,self.remote)["indexExhaustive"])
    def test_part_mismatch(self):
        self.remote["scans"][0]["indexedParts"]=754
        self.assertEqual(module.compare(self.local,self.remote)["status"],
                         "PART_COUNT_MISMATCH")
    def test_place_mismatch(self):
        self.remote["scans"][0]["placeId"]=1
        self.assertEqual(module.compare(self.local,self.remote)["status"],
                         "PLACE_MISMATCH")
    def test_duplicate_scan(self):
        self.remote["scans"].append(dict(self.remote["scans"][0]))
        with self.assertRaises(ValueError):module.compare(self.local,self.remote)
if __name__=="__main__":unittest.main()
