import sys, pathlib, json, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from evidence_pipeline_v62 import import_console, catalog
from evidence_correlator_v67 import compile_evidence

PLACE=85896571713843
def batch():
    record={"index":3,"entries":[{"root":"Players","path":"Players/\"tester\"#1@Player/\"leaderstats\"#1@Folder/\"Bubbles\"#1@IntValue","className":"IntValue","value":"321"}]}
    return "05:43:25LYCOLES_V54_BATCH 3/44/46 "+json.dumps(record)
def telemetry():
    header={"schemaVersion":"66.telemetry","placeId":PLACE,"ticks":2,"eventCount":0}
    return "LYCOLES_V66_HEADER "+json.dumps(header)+"\nLYCOLES_V66_END 0"
class TestPartialRecovery(unittest.TestCase):
    def test_headerless_batch_retained(self):
        receipt=import_console(batch())
        self.assertIsNone(receipt["placeId"])
        self.assertEqual(receipt["recoveredPartialBatches"],1)
        self.assertEqual(len(receipt["samples"]),1)
        self.assertFalse(receipt["samples"][0]["complete"])
        self.assertEqual(len(catalog(receipt)["capabilities"]),1)
    def test_unverified_provenance(self):
        result=compile_evidence(batch(),telemetry(),PLACE)
        m=result["manifest"]
        self.assertEqual(m["discoveryPlaceIdSource"],"cli_unverified")
        self.assertFalse(m["gates"]["placeIdsMatch"])
        self.assertFalse(m["gates"]["discoveryComplete"])
        self.assertFalse(m["readyForActionGeneration"])
    def test_explicit_mismatch_rejected(self):
        source="LYCOLES_V54_BATCH_STREAM_BEGIN 123 1\n"+batch()
        with self.assertRaisesRegex(ValueError,"mismatch"):
            compile_evidence(source,telemetry(),PLACE)
    def test_empty_discovery_rejected(self):
        with self.assertRaisesRegex(ValueError,"no recoverable batches"):
            compile_evidence("",telemetry(),PLACE)
if __name__=="__main__": unittest.main()
