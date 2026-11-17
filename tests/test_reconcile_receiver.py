import importlib.util
import json
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
path=ROOT/"tools"/"reconcile_receiver.py"
TRANSPORT_CASES=json.loads((ROOT/"tests"/"fixtures"/"report_transport_v301_cases.json").read_text(encoding="utf-8"))
spec=importlib.util.spec_from_file_location("reconcile_receiver",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.local={"scanId":"scan-a","placeId":3623096087,"expectedParts":755,
                    "objectCount":128040}
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
    def test_direct_integrity_response_verifies_receiver_availability(self):
        integrity={"scanId":"scan-a","placeId":3623096087,"partCount":755,
                   "receivedParts":755,"missingParts":[],"identityErrors":[],
                   "indexedObjects":128040,"uniqueObjectKeys":128040,
                   "duplicateObjectKeys":0,"expectedObjects":128040,
                   "complete":True,"integrityStatus":"verified"}
        result=module.compare(self.local,integrity)
        self.assertEqual(result["status"],"RECEIVER_INTEGRITY_VERIFIED")
        self.assertTrue(result["receiverIntegrityVerified"])
        self.assertTrue(result["downstreamReportAvailable"])
        self.assertFalse(result["verifiedEquivalent"])
        self.assertFalse(result["receiverResponseAuthenticityVerified"])
    def test_direct_integrity_requires_local_object_count_match(self):
        integrity={"scanId":"scan-a","placeId":3623096087,"partCount":755,
                   "receivedParts":755,"missingParts":[],"identityErrors":[],
                   "indexedObjects":128039,"uniqueObjectKeys":128039,
                   "duplicateObjectKeys":0,"expectedObjects":128039,
                   "complete":True,"integrityStatus":"verified"}
        result=module.compare(self.local,integrity)
        self.assertEqual(result["status"],"RECEIVER_INTEGRITY_INCOMPLETE")
        self.assertFalse(result["receiverIntegrityVerified"])

    def test_direct_incomplete_integrity_response_stays_unavailable(self):
        integrity={"scanId":"scan-a","placeId":3623096087,"partCount":755,
                   "receivedParts":754,"missingParts":[755],"identityErrors":[],
                   "indexedObjects":128039,"uniqueObjectKeys":128039,
                   "duplicateObjectKeys":0,"expectedObjects":128040,
                   "complete":False,"integrityStatus":"incomplete"}
        result=module.compare(self.local,integrity)
        self.assertEqual(result["status"],"RECEIVER_INTEGRITY_INCOMPLETE")
        self.assertFalse(result["receiverIntegrityVerified"])
        self.assertFalse(result["downstreamReportAvailable"])
    def test_all_local_transport_snapshots_accept_separate_receiver_integrity(self):
        scan_id=TRANSPORT_CASES["scanId"]
        integrity={"scanId":scan_id,"placeId":3623096087,"partCount":755,
                   "receivedParts":755,"missingParts":[],"identityErrors":[],
                   "indexedObjects":128040,"uniqueObjectKeys":128040,
                   "duplicateObjectKeys":0,"expectedObjects":128040,
                   "complete":True,"integrityStatus":"verified"}
        for case in TRANSPORT_CASES["cases"]:
            with self.subTest(case=case["name"]):
                local={"scanId":scan_id,"placeId":3623096087,"expectedParts":755,
                       "objectCount":128040,"reportTransport":case["reportTransport"]}
                result=module.compare(local,integrity)
                self.assertTrue(result["receiverIntegrityVerified"])
                self.assertTrue(result["downstreamReportAvailable"])
                self.assertFalse(result["verifiedEquivalent"])
                self.assertFalse(result["receiverResponseAuthenticityVerified"])
if __name__=="__main__":unittest.main()
