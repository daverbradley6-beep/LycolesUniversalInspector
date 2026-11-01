import importlib.util
import json
import pathlib
import unittest

root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v62", root / "tools/evidence_pipeline_v62.py")
v62 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v62)

def log(include_first=True, end=True):
    lines = ["LYCOLES_V54_BATCH_STREAM_BEGIN 85896571713843 2"]
    for i in (1, 2):
        if i == 1 and not include_first:
            continue
        lines += [f"LYCOLES_V54_BATCH_BEGIN {i} 1",
                  f"LYCOLES_V54_BATCH {i}/1/1 " + json.dumps({
                      "index": i, "entries": [{"root": "Players", "path": "Players/test/leaderstats/Bubbles",
                                               "className": "IntValue", "value": str(i)}]}),
                  f"LYCOLES_V54_BATCH_END {i}"]
    if end:
        lines.append("LYCOLES_V54_BATCH_STREAM_END")
    return "\n".join(lines)

class V62Tests(unittest.TestCase):
    def test_complete(self):
        r = v62.import_console(log())
        self.assertEqual(r["completeSamples"], 2)
        c = v62.catalog(r)
        self.assertTrue(c["sourceComplete"])
        self.assertTrue(c["capabilities"][0]["valueChanged"])
        self.assertFalse(c["capabilities"][0]["serverOutcomeVerified"])
        self.assertEqual(c["actionContractsGenerated"], 0)

    def test_partial(self):
        r = v62.import_console(log(include_first=False, end=False))
        self.assertEqual(r["completeSamples"], 1)
        self.assertFalse(v62.catalog(r)["sourceComplete"])

    def test_missing_batch(self):
        r = v62.import_console("LYCOLES_V54_BATCH_STREAM_BEGIN 123 2\nLYCOLES_V54_BATCH_BEGIN 1 2\nLYCOLES_V54_BATCH_END 1")
        self.assertEqual(r["missing"]["1"]["missingBatches"], [1, 2])

    def test_conflicting_duplicate(self):
        raw = log()
        line = next(x for x in raw.splitlines() if "LYCOLES_V54_BATCH 1/1/1 " in x)
        with self.assertRaises(ValueError):
            v62.import_console(raw + "\n" + line.replace('"value": "1"', '"value": "99"'))

    def test_malformed_batch_recovers(self):
        r = v62.import_console(log() + "\nLYCOLES_V54_BATCH 2/1/1 {not json}")
        self.assertEqual(r["completeSamples"], 2)
        self.assertTrue(r["warnings"])

if __name__ == "__main__":
    unittest.main()
