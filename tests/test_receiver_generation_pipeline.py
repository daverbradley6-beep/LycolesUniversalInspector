import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "receiver_generation_pipeline.py"
SPEC = importlib.util.spec_from_file_location("receiver_generation_pipeline", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_parts(directory, event=None, request=None, scan_id="receiver_pipeline_scan"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
    scan_stats = {"recorded": 2, "complete": True}
    one = dict(
        scan,
        partIndex=1,
        scanStats=scan_stats,
        featureEvidence={"pets": {}},
        featureRequest=request,
        objects=[
            {
                "path": "Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
                "class": "ProximityPrompt",
                "scanOrdinal": 1,
                "interaction": {
                    "actionText": "Hatch",
                    "objectText": "Rainbow Egg",
                    "holdDuration": 0,
                    "maxActivationDistance": 10,
                },
            }
        ],
    )
    interaction = event or {
        "featureCandidate": "pets",
        "path": "Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
        "controlType": "ProximityPrompt.Triggered",
        "evidenceLevel": "temporal-state-change-observed",
        "outcomeVerified": False,
        "stateChanges": [{"key": "leaderstats.🥚 Hatches", "before": 1, "after": 2}],
    }
    two = dict(
        scan,
        partIndex=2,
        objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 2}],
        interactionHistoryChunk=[interaction],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")


class ReceiverGenerationPipelineTests(unittest.TestCase):
    def test_generate_from_parts_runs_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Automatically hatch the selected egg",
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertIn(result["generationStatus"], ("generated", "generated-with-blockers"))
            generated_result = pathlib.Path(result["delivery"]["generatedResultPath"])
            self.assertTrue(generated_result.is_file())

    def test_generate_from_receiver_requires_read_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            previous = MODULE.os.environ.get("LYCOLES_READ_KEY")
            try:
                if "LYCOLES_READ_KEY" in MODULE.os.environ:
                    del MODULE.os.environ["LYCOLES_READ_KEY"]
                with self.assertRaisesRegex(ValueError, "LYCOLES_READ_KEY"):
                    MODULE.generate_from_receiver(
                        receiver_endpoint="https://example.com",
                        scan_id="scan123456",
                        output_root=root,
                    )
            finally:
                if previous is not None:
                    MODULE.os.environ["LYCOLES_READ_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
