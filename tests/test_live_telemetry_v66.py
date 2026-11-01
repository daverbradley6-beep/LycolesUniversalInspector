import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from live_telemetry_v66 import generate,parse_log

def log():
    h={"schemaVersion":"66.telemetry","placeId":123,"eventCount":2,"ticks":4}
    e={"tick":2,"kind":"stat","path":"Players.test.leaderstats.Bubbles","before":"1","after":"2"}
    return "\n".join(["LYCOLES_V66_HEADER "+json.dumps(h),
                      "LYCOLES_V66_EVENT 1 "+json.dumps(e),
                      "LYCOLES_V66_EVENT 2 "+json.dumps({**e,"tick":3,"after":"3"}),
                      "LYCOLES_V66_END 2"])
class TestV66(unittest.TestCase):
    def test_generator(self):
        source=generate(123)
        self.assertIn("game.PlaceId~=123",source)
        self.assertIn("LYCOLES_V66_HEADER",source)
        self.assertIn("MAX_SCAN=4000",source)
    def test_read_only(self):
        source=generate(123)
        for forbidden in ("FireServer(", "InvokeServer(", "firetouchinterest(", "getgc("):
            self.assertNotIn(forbidden,source)
    def test_roundtrip(self):
        result=parse_log(log(),123)
        self.assertTrue(result["complete"])
        self.assertEqual(result["receivedEvents"],2)
        self.assertFalse(result["causalityVerified"])
    def test_partial(self):
        result=parse_log(log().replace("LYCOLES_V66_EVENT 2 ","MISSING "),123)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missingIndices"],[2])
    def test_place_mismatch(self):
        with self.assertRaises(ValueError):parse_log(log(),456)
    def test_duplicate_conflict(self):
        s=log()+"\nLYCOLES_V66_EVENT 1 "+json.dumps({"tick":5,"kind":"stat","path":"x","before":"1","after":"5"})
        with self.assertRaises(ValueError):parse_log(s,123)
    def test_invalid_limits(self):
        for args in ((0,), (True,), (123,19), (123,1001), (123,300,99), (123,300,10001)):
            with self.assertRaises(ValueError):generate(*args)
if __name__=="__main__":unittest.main()
