import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from action_result_analyzer_v83 import analyze, direction, load_expected, parse_logs

PLACE = 85896571713843

def result(action="hatch", requested=True, changes=None):
    return {
        "schemaVersion": "82.result", "placeId": PLACE, "id": action,
        "requested": requested, "observedChanges": changes or [], "verified": False
    }

def hatch_change():
    return {"stat": "🥚 Hatches", "before": 5, "after": 6}

class TestV83(unittest.TestCase):
    def test_numeric_increase(self): self.assertEqual(direction(1, 2), "increase")
    def test_numeric_decrease(self): self.assertEqual(direction(2, 1), "decrease")
    def test_toggle(self): self.assertEqual(direction(False, True), "toggle")
    def test_text(self): self.assertEqual(direction("closed", "open"), "change")
    def test_equal(self): self.assertIsNone(direction(1, 1))
    def test_type_mismatch(self): self.assertIsNone(direction(True, 1))
    def test_empty(self): self.assertEqual(analyze([])["actions"], [])
    def test_unverified(self): self.assertFalse(analyze([result()])["verified"])
    def test_execution_disabled(self): self.assertFalse(analyze([result()])["executionEnabled"])
    def test_failed(self): self.assertEqual(analyze([result(requested=False)])["actions"][0]["status"], "activation_failed")
    def test_requested_not_success(self): self.assertEqual(analyze([result()])["actions"][0]["status"], "observed_not_verified")
    def test_unicode(self):
        row = analyze([result(changes=[hatch_change()])])["actions"][0]
        self.assertEqual(row["observedSignals"][0]["stat"], "🥚 Hatches")
    def test_count(self):
        row = analyze([result(changes=[hatch_change()]), result(changes=[hatch_change()])])["actions"][0]
        self.assertEqual(row["observedSignals"][0]["observations"], 2)
    def test_no_duplicate_signal_per_result(self):
        row = analyze([result(changes=[hatch_change(), hatch_change()])])["actions"][0]
        self.assertEqual(row["observedSignals"][0]["observations"], 1)
    def test_expected_match(self):
        row = analyze([result(changes=[hatch_change()])], {"hatch": [{"stat": "🥚 Hatches", "operator": "increase"}]})["actions"][0]
        self.assertEqual(row["expectedMatches"], 1)
    def test_expected_mismatch(self):
        row = analyze([result()], {"hatch": [{"stat": "🥚 Hatches", "operator": "increase"}]})["actions"][0]
        self.assertEqual(row["expectedMatches"], 0)
    def test_multiple_actions(self):
        self.assertEqual(len(analyze([result(), result(action="inventory")])["actions"]), 2)
    def test_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "log.txt"
            p.write_text("LYCOLES_V82_RESULT " + json.dumps(result(changes=[hatch_change()]), ensure_ascii=False), encoding="utf-8")
            found, warnings = parse_logs([p], PLACE)
            self.assertEqual(len(found), 1)
            self.assertEqual(warnings, [])
    def test_bad_json_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "log.txt"
            p.write_text("LYCOLES_V82_RESULT {broken", encoding="utf-8")
            self.assertEqual(len(parse_logs([p], PLACE)[1]), 1)
    def test_wrong_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "log.txt"
            p.write_text("LYCOLES_V82_RESULT " + json.dumps(result()), encoding="utf-8")
            self.assertEqual(len(parse_logs([p], 1)[0]), 0)
    def test_expected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "approved.json"
            p.write_text(json.dumps({"placeId": PLACE, "contracts": [{"id": "hatch", "approved": True, "expectedSignals": [{"stat": "🥚 Hatches", "operator": "increase"}]}]}), encoding="utf-8")
            self.assertEqual(load_expected(p, PLACE)["hatch"][0]["operator"], "increase")
    def test_expected_bad_operator(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "approved.json"
            p.write_text(json.dumps({"placeId": PLACE, "contracts": [{"id": "hatch", "approved": True, "expectedSignals": [{"stat": "x", "operator": "unknown"}]}]}), encoding="utf-8")
            with self.assertRaises(ValueError): load_expected(p, PLACE)


    def test_capture_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "log.txt"
            row = result()
            row.update({"captureId": "session-1", "index": 1})
            line = "LYCOLES_V82_RESULT " + json.dumps(row)
            p.write_text(line + "\n" + line, encoding="utf-8")
            found, warnings = parse_logs([p], PLACE)
            self.assertEqual(len(found), 1)
            self.assertEqual(warnings, [])
    def test_capture_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "log.txt"
            a = result()
            a.update({"captureId": "session-1", "index": 1})
            b = dict(a)
            b["requested"] = False
            p.write_text("LYCOLES_V82_RESULT " + json.dumps(a) + "\nLYCOLES_V82_RESULT " + json.dumps(b), encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_logs([p], PLACE)
    def test_capture_count(self):
        a = result()
        a["captureId"] = "session-1"
        b = result()
        b["captureId"] = "session-2"
        self.assertEqual(analyze([a, b])["actions"][0]["independentCaptures"], 2)

if __name__ == "__main__":
    unittest.main()
