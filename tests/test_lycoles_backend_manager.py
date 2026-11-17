import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "lycoles_backend_manager.py"
SPEC = importlib.util.spec_from_file_location("lycoles_backend_manager", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BackendManagerTests(unittest.TestCase):
    def _config(self, root: pathlib.Path):
        return MODULE.BackendConfig(
            host="127.0.0.1",
            port=8787,
            output_root=root / "jobs",
            runtime_dir=root / "runtime",
            startup_timeout=3.0,
            health_timeout=0.5,
            poll_interval=0.05,
            max_restarts=2,
            restart_window_seconds=30.0,
            restart_backoff_seconds=0.1,
            restart_backoff_max_seconds=0.5,
        )

    def test_setup_check_reports_required_files_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(pathlib.Path(tmp))
            result = MODULE._setup_check(config)
            self.assertEqual(result["schemaVersion"], "30.6.backend-manager-setup-check.1")
            self.assertTrue(result["requiredFiles"]["serviceScriptExists"])
            self.assertTrue(result["requiredFiles"]["inspectorScriptExists"])
            self.assertEqual(result["defaults"]["paidLlmEnabledDefault"], "false")
            self.assertEqual(result["defaults"]["providerDefault"], "deterministic")

    def test_service_command_uses_generation_service_serve_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(pathlib.Path(tmp))
            command = MODULE._service_command(config)
            self.assertIn("lycoles_generation_service.py", " ".join(command))
            self.assertIn("serve", command)
            self.assertIn("--port", command)
            self.assertIn("8787", command)

    def test_health_probe_reports_healthy_when_endpoints_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(pathlib.Path(tmp))

            responses = [
                (200, {"status": "ok"}),
                (200, {"provider": {"name": "deterministic", "enabled": False}}),
            ]

            def fake_json_request(*_args, **_kwargs):
                return responses.pop(0)

            with mock.patch.object(MODULE, "_json_request", side_effect=fake_json_request):
                payload = MODULE._health_probe(config)

            self.assertTrue(payload["reachable"])
            self.assertTrue(payload["healthy"])
            self.assertEqual(payload["contractStatusCode"], 200)
            self.assertEqual(payload["healthStatusCode"], 200)

    def test_smoke_session_lifecycle_completes_with_mocked_http_responses(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(pathlib.Path(tmp))

            responses = [
                (201, {
                    "session": {"sessionId": "session-1"},
                    "recommendations": {"items": [{"id": "recommendation_movement"}]},
                }),
                (202, {"jobId": "job-1", "status": "queued"}),
                (200, {"jobId": "job-1", "status": "running"}),
                (200, {"jobId": "job-1", "status": "completed"}),
                (200, {"script": "print('ok')", "provider": "deterministic", "versionId": "v1"}),
            ]

            def fake_json_request(*_args, **_kwargs):
                return responses.pop(0)

            with mock.patch.object(MODULE, "_json_request", side_effect=fake_json_request), \
                    mock.patch.object(MODULE.time, "sleep", return_value=None):
                result = MODULE._smoke_session_lifecycle(config, timeout_seconds=2.0)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["jobId"], "job-1")
            self.assertEqual(result["sessionId"], "session-1")

    def test_start_dry_run_returns_supervisor_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(pathlib.Path(tmp))
            with mock.patch.object(MODULE, "_status", return_value={
                "supervisor": {"running": False},
                "health": {"healthy": False},
            }):
                payload = MODULE._start(config, dry_run=True)
            self.assertEqual(payload["result"], "dry-run")
            self.assertIn("_supervise", payload["command"])


if __name__ == "__main__":
    unittest.main()
