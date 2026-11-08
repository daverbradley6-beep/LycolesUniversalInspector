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



def make_live_observation_export(path, baseline_scan_id="receiver_pipeline_scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": baseline_scan_id,
        "baselineScanId": baseline_scan_id,
        "integrity": {
            "scanComplete": True,
            "placeId": 3623096087,
            "scanId": "live-observation-receiver-1",
            "baselineScanId": baseline_scan_id,
            "parts": 2,
            "interactionEvents": 7,
        },
        "sourceDiagnostics": {
            "scanMode": "dynamic-observations",
            "requiresFullObjectRescan": False,
            "baselineScanId": baseline_scan_id,
        },
        "sourceProvenance": {
            "schemaVersion": "30.2.source-provenance.1",
            "inputMode": "local-multipart",
            "scanId": "live-observation-receiver-1",
            "placeId": 3623096087,
            "partCount": 2,
            "receiverStoredPayloadDigestsVerified": False,
            "receiverStoredPayloadDigestsRevalidatedThisRun": False,
            "receiverAcknowledgementDigestEquivalent": False,
            "receiverIntegrityVerified": False,
            "resumeCheckpointAuthenticated": False,
            "receiverResponseAuthenticityVerified": False,
            "localPayloadEquivalent": False,
            "sourceAuthenticityVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "replayable": False,
            "gameplayVerified": False,
            "actionOutcomesVerified": False,
        },
        "features": [
            {
                "feature": "combat",
                "interactionEvents": 7,
                "observedEvents": 7,
                "observationCoverage": 1.0,
                "timingDistribution": {"before": 2, "during": 2, "after": 3},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


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

            readiness = json.loads(pathlib.Path(result["evidence"]["generationReadinessPath"]).read_text(encoding="utf-8"))
            self.assertEqual(readiness["request"]["request"],
                             "Automatically hatch the selected egg")
            self.assertNotEqual(readiness["request"]["status"], "no-capability-requested")


    def test_generate_from_parts_accepts_live_observation_overlay_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track observed reload behavior")
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay)

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Track observed reload behavior",
                observation_paths=[overlay],
            )
            self.assertEqual(result["status"], "succeeded")
            release_manifest = json.loads(
                pathlib.Path(result["evidence"]["releaseManifestPath"]).read_text(encoding="utf-8")
            )
            self.assertEqual(release_manifest["evidenceOverlayProvenance"]["overlayCount"], 1)
            overlay_provenance = json.loads(
                (pathlib.Path(result["outputDir"]) / "evidence-overlay-provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(overlay_provenance["overlays"][0]["scanId"], "live-observation-receiver-1")

    def test_summarize_generation_result_flags_observational_only_when_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically shoot and reload")

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Automatically shoot and reload",
            )
            summary = MODULE.summarize_generation_result(result)
            self.assertTrue(summary["generatedResultAvailable"])
            self.assertIsInstance(summary["implementedCapabilities"], list)
            self.assertIn("requested capability is not implementation-ready", summary["observationalOnly"])
            self.assertIn("no request-aligned execution-ready workflow candidates", summary["observationalOnly"])

    def test_resolve_parts_dir_for_scan_id_prefers_exact_manifest_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            extracted = root / "extracted"
            scan_dir = extracted / "arsenal_case"
            scan_dir.mkdir(parents=True)
            manifest = {
                "scanId": "DBFC72C6-749B-4F95-BBA2-433B8B61745C",
                "placeId": 286090429,
                "partCount": 2,
                "gameName": "Arsenal",
            }
            (scan_dir / "sample_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            resolved = MODULE._resolve_parts_dir_for_scan_id(
                extracted, "DBFC72C6-749B-4F95-BBA2-433B8B61745C")
            self.assertEqual(resolved, scan_dir.resolve())

    def test_exercise_live_reports_requested_baseline_when_parts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            result = MODULE.run_live_evidence_exercise(
                output_root=root / "out",
                requested_capability_arsenal="Automatically shoot and reload in Arsenal",
                requested_capability_phantom="Automatically shoot and reload in Phantom Forces",
                observation_paths=[],
                extracted_root=root / "missing-extracted",
                arsenal_baseline_scan_id="DBFC72C6-749B-4F95-BBA2-433B8B61745C",
                phantom_baseline_scan_id="6D3741EF-9569-4F40-B38A-E4FD2AE0A063",
            )
            scenarios = {item["name"]: item for item in result["scenarios"]}
            self.assertEqual(scenarios["arsenal"]["status"], "blocked")
            self.assertEqual(scenarios["arsenal"]["requestedBaselineScanId"],
                             "DBFC72C6-749B-4F95-BBA2-433B8B61745C")
            self.assertEqual(scenarios["phantom-forces"]["status"], "blocked")
            self.assertEqual(scenarios["phantom-forces"]["requestedBaselineScanId"],
                             "6D3741EF-9569-4F40-B38A-E4FD2AE0A063")

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


    def test_generate_from_receiver_forwards_legacy_page_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            previous = MODULE.os.environ.get("LYCOLES_READ_KEY")
            original_fetch = MODULE.FETCH.fetch_scan
            original_generate = MODULE.generate_from_parts
            captured = {}

            def fake_fetch(endpoint, read_key, scan_id, output, **kwargs):
                output_path = pathlib.Path(output)
                output_path.mkdir(parents=True, exist_ok=True)
                captured["kwargs"] = kwargs
                return {
                    "schemaVersion": "30.2.receiver-import-legacy-reports.1",
                    "scanId": scan_id,
                    "placeId": 3623096087,
                    "partCount": 2,
                    "objectCount": 2,
                    "featureCount": 0,
                    "output": str(output_path),
                }

            def fake_generate_from_parts(**_kwargs):
                return {"status": "succeeded", "claims": {"runtimeVerified": False}}

            try:
                MODULE.os.environ["LYCOLES_READ_KEY"] = "read-secret"
                MODULE.FETCH.fetch_scan = fake_fetch
                MODULE.generate_from_parts = fake_generate_from_parts
                result = MODULE.generate_from_receiver(
                    receiver_endpoint="https://example.com",
                    scan_id="scan123456",
                    output_root=root,
                    allow_legacy_report_index=True,
                    max_legacy_report_pages=1234,
                )
                self.assertEqual(result["fetch"]["scanId"], "scan123456")
                self.assertEqual(captured["kwargs"]["max_legacy_report_pages"], 1234)
                self.assertTrue(captured["kwargs"]["allow_legacy_report_index"])
            finally:
                MODULE.FETCH.fetch_scan = original_fetch
                MODULE.generate_from_parts = original_generate
                if previous is None:
                    MODULE.os.environ.pop("LYCOLES_READ_KEY", None)
                else:
                    MODULE.os.environ["LYCOLES_READ_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
