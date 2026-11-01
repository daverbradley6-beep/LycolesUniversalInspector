"""Regression checks for compact v54 generation and batch receipt parsing."""
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("balanced_discovery_v54", ROOT / "tools" / "balanced_discovery_v54.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CompactV54Tests(unittest.TestCase):
    def test_generated_source_has_bounded_export_and_progress(self):
        src = mod.generate(85896571713843)
        self.assertIn("MAX_BATCH_CHARS=6500", src)
        self.assertIn("MAX_DECORATIVE=100", src)
        self.assertIn("LYCOLES_V54_PROGRESS", src)
        self.assertIn("LYCOLES_V54_BATCH_STREAM_END", src)
        self.assertIn("lastPriorityValues[path]", src)
        self.assertNotIn("PLACE_ID", src)

    def test_complete_compact_batch_roundtrip(self):
        lines = ["LYCOLES_V54_BATCH_STREAM_BEGIN 85896571713843 2"]
        for i in (1, 2):
            lines.append(f"LYCOLES_V54_BATCH_BEGIN {i} 1")
            lines.append(f"LYCOLES_V54_BATCH {i}/1/1 " + json.dumps({
                "index": i, "entries": [{"root": "Players", "path": "Players/test",
                                          "className": "IntValue", "priority": True, "value": str(i)}]}))
            lines.append(f"LYCOLES_V54_BATCH_END {i}")
        lines.append("LYCOLES_V54_BATCH_STREAM_END")
        receipt = mod.parse_receipt("\n".join(lines))
        self.assertEqual(receipt["placeId"], 85896571713843)
        self.assertEqual(len(receipt["observations"]), 2)
        self.assertEqual(receipt["observations"][1]["entries"][0]["value"], "2")

    def test_reject_truncated_receipt(self):
        with self.assertRaises(ValueError):
            mod.parse_receipt("LYCOLES_V54_BATCH_STREAM_BEGIN 85896571713843 2\nLYCOLES_V54_BATCH_BEGIN 1 1")


if __name__ == "__main__":
    unittest.main()
