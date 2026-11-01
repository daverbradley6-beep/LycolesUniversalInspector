import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("universal_release_v63", ROOT / "tools/universal_release_v63.py")
v63 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v63)

def receipt():
    lines = ["LYCOLES_V54_BATCH_STREAM_BEGIN 85896571713843 2"]
    for i in (1, 2):
        entries = [{"path": "Players/local/leaderstats/Bubbles", "className": "IntValue",
                    "value": str(i), "root": "Players"},
                   {"path": "Players/local/Backpack/BubbleWand", "className": "Tool", "root": "Players"},
                   {"path": "ReplicatedStorage/Remotes/Unknown", "className": "RemoteEvent",
                    "root": "ReplicatedStorage"}]
        lines += [f"LYCOLES_V54_BATCH_BEGIN {i} 1",
                  f"LYCOLES_V54_BATCH {i}/1/1 " + json.dumps({"index": i, "entries": entries}),
                  f"LYCOLES_V54_BATCH_END {i}"]
    lines.append("LYCOLES_V54_BATCH_STREAM_END")
    return "\n".join(lines)

class V63Tests(unittest.TestCase):
    def test_release_contains_read_only_gui(self):
        result = v63.make_release(receipt(), 85896571713843)
        self.assertEqual(result["manifest"]["automaticallyExecutableActions"], 0)
        self.assertTrue(result["manifest"]["sourceComplete"])
        self.assertIn("string.find", result["luau"])
        self.assertIn("game.PlaceId~=85896571713843", result["luau"])
        self.assertNotIn("FireServer(", result["luau"])
        self.assertNotIn("InvokeServer(", result["luau"])
        self.assertTrue(any(x["state"] == "needs_authorized_contract" for x in result["backlog"]))

    def test_wrong_place_rejected(self):
        with self.assertRaises(ValueError):
            v63.make_release(receipt(), 123)

    def test_partial_source_explicit(self):
        r = v63.make_release(receipt().replace("LYCOLES_V54_BATCH_STREAM_END", ""), 85896571713843)
        self.assertFalse(r["manifest"]["sourceComplete"])

    def test_output_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = v63.build(receipt(), 85896571713843, pathlib.Path(tmp))
            self.assertEqual(manifest["includedInGui"], 3)
            for name in ("release-manifest-v63.json", "capability-catalog-v63.json",
                         "verification-backlog-v63.json", "evidence-browser-v63.luau"):
                self.assertTrue((pathlib.Path(tmp) / name).is_file())

    def test_cap_validation(self):
        with self.assertRaises(ValueError):
            v63.make_release(receipt(), 85896571713843, 301)

if __name__ == "__main__":
    unittest.main()
