import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from evidence_correlator_v67 import compile_evidence, build

PLACE=85896571713843
def discovery():
    entry={"index":1,"entries":[{"path":"Players/test/leaderstats/Bubbles","className":"IntValue","value":"1"}]}
    return "\n".join([f"LYCOLES_V54_BATCH_STREAM_BEGIN {PLACE} 1",
      "LYCOLES_V54_BATCH_BEGIN 1 1",
      "LYCOLES_V54_BATCH 1/1/1 "+json.dumps(entry),
      "LYCOLES_V54_BATCH_END 1","LYCOLES_V54_BATCH_STREAM_END"])
def telemetry(path="Players.test.leaderstats.Bubbles",end=True):
    header={"schemaVersion":"66.telemetry","placeId":PLACE,"eventCount":1,"ticks":2}
    event={"tick":2,"kind":"stat","path":path,"before":"1","after":"2"}
    return "\n".join(["LYCOLES_V66_HEADER "+json.dumps(header),
      "LYCOLES_V66_EVENT 1 "+json.dumps(event)]+(["LYCOLES_V66_END 1"] if end else []))

class TestV67(unittest.TestCase):
    def test_correlates_paths(self):
        r=compile_evidence(discovery(),telemetry(),PLACE)
        self.assertEqual(r["manifest"]["correlatedPaths"],1)
        self.assertEqual(r["correlations"][0]["changeCount"],1)
        self.assertFalse(r["manifest"]["readyForActionGeneration"])
    def test_unmatched(self):
        r=compile_evidence(discovery(),telemetry("Players.test.other"),PLACE)
        self.assertEqual(r["manifest"]["unmatchedTelemetryEvents"],1)
    def test_incomplete_telemetry(self):
        r=compile_evidence(discovery(),telemetry(end=False),PLACE)
        self.assertFalse(r["manifest"]["gates"]["telemetryComplete"])
    def test_wrong_place(self):
        with self.assertRaises(ValueError):compile_evidence(discovery(),telemetry(),123)
    def test_invalid_place(self):
        for place in (0,-1,True):
            with self.assertRaises(ValueError):compile_evidence(discovery(),telemetry(),place)
    def test_files_written(self):
        with tempfile.TemporaryDirectory() as temp:
            r=build(discovery(),telemetry(),PLACE,pathlib.Path(temp))
            self.assertEqual(r["manifest"]["automaticExecutableActions"],0)
            for name in ("release-manifest-v67.json","correlations-v67.json",
                         "unmatched-events-v67.json","telemetry-summary-v67.json"):
                self.assertTrue((pathlib.Path(temp)/name).is_file())
if __name__=="__main__":unittest.main()
