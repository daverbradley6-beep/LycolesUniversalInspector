import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "lycoles_generation_service.py"
SPEC = importlib.util.spec_from_file_location("lycoles_generation_service", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_parts(directory, request=None, scan_id="provider_scan_001"):
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
    two = dict(
        scan,
        partIndex=2,
        objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 2}],
        interactionHistoryChunk=[
            {
                "featureCandidate": "pets",
                "path": "Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
                "controlType": "ProximityPrompt.Triggered",
                "evidenceLevel": "temporal-state-change-observed",
                "outcomeVerified": False,
                "stateChanges": [{"key": "leaderstats.🥚 Hatches", "before": 285, "after": 286}],
            }
        ],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")


class ProviderSelectionTests(unittest.TestCase):
    def test_openai_provider_without_key_falls_back_deterministic(self):
        old_provider = os.environ.get("LYCOLES_LLM_PROVIDER")
        old_key = os.environ.get("LYCOLES_OPENAI_API_KEY")
        old_openai_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["LYCOLES_LLM_PROVIDER"] = "openai"
            os.environ.pop("LYCOLES_OPENAI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            provider, info = MODULE._provider_from_environment()
            self.assertIsInstance(provider, MODULE.DeterministicLLMProvider)
            self.assertEqual(info.provider, "openai-compatible")
            self.assertFalse(info.enabled)
            self.assertIn("missing", info.reason)
        finally:
            if old_provider is None:
                os.environ.pop("LYCOLES_LLM_PROVIDER", None)
            else:
                os.environ["LYCOLES_LLM_PROVIDER"] = old_provider
            if old_key is None:
                os.environ.pop("LYCOLES_OPENAI_API_KEY", None)
            else:
                os.environ["LYCOLES_OPENAI_API_KEY"] = old_key
            if old_openai_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_openai_key

    def test_job_result_exposes_provider_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            old_provider = os.environ.get("LYCOLES_LLM_PROVIDER")
            try:
                os.environ["LYCOLES_LLM_PROVIDER"] = "deterministic"
                service = MODULE.LycolesGenerationService(output_root=root / "jobs")
                request = MODULE.GenerationRequest(
                    evidence_kind="parts_dir",
                    evidence_path=parts,
                    requested_capability="Automatically hatch the selected egg",
                )
                result = service.run_sync(request)
                self.assertIn("provider", result)
                self.assertEqual(result["provider"]["name"], "deterministic")
                self.assertFalse(result["provider"]["enabled"])
                self.assertFalse(result["provider"]["aiInferencePerformed"])
            finally:
                if old_provider is None:
                    os.environ.pop("LYCOLES_LLM_PROVIDER", None)
                else:
                    os.environ["LYCOLES_LLM_PROVIDER"] = old_provider


if __name__ == "__main__":
    unittest.main()
