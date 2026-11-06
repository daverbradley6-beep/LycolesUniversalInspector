import importlib.util
import json
import pathlib
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_MANIFEST = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"
SOURCE = ROOT / "tools" / "lycoles_generation_service.py"
SPEC = importlib.util.spec_from_file_location("lycoles_generation_service", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_parts(directory, event=None, request=None, scan_id="service_scan_001"):
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
        "stateChanges": [{"key": "leaderstats.🥚 Hatches", "before": 285, "after": 286}],
    }
    two = dict(
        scan,
        partIndex=2,
        objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 2}],
        interactionHistoryChunk=[interaction],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")


class LycolesGenerationServiceTests(unittest.TestCase):
    def test_manifest_only_job_is_blocked_but_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = MODULE.LycolesGenerationService(output_root=pathlib.Path(tmp) / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="manifest",
                evidence_path=FIXTURE_MANIFEST,
                requested_capability="Auto hatch eggs",
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["generationStatus"], "blocked")
            self.assertEqual(result["analysis"]["mode"], "manifest-only")
            self.assertIn("full_multipart_report_unavailable", result["analysis"]["explicitBlockers"])
            self.assertIsNone(result["delivery"]["generatedResultPath"])
            self.assertFalse(result["claims"]["runtimeVerified"])

    def test_parts_job_generates_display_only_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            self.assertIn(result["generationStatus"], ("generated", "generated-with-blockers"))
            generated_result_path = pathlib.Path(result["delivery"]["generatedResultPath"])
            self.assertTrue(generated_result_path.is_file())

            generated = json.loads(generated_result_path.read_text(encoding="utf-8"))
            self.assertEqual(generated["schemaVersion"], "113.generated-result.1")
            self.assertEqual(generated["placeId"], 3623096087)
            self.assertFalse(generated["runtimeVerified"])
            self.assertFalse(generated["gameplayVerified"])
            self.assertFalse(generated["executionAuthorized"])

    def test_async_submission_exposes_job_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            job_id = service.submit(request)

            snapshot = None
            deadline = time.time() + 15
            while time.time() < deadline:
                snapshot = service.get_job(job_id)
                if snapshot and snapshot["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.05)

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["status"], "succeeded")
            self.assertIsInstance(snapshot["result"], dict)
            self.assertEqual(snapshot["result"]["jobId"], job_id)


if __name__ == "__main__":
    unittest.main()
