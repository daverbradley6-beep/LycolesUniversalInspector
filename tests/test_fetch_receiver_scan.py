import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCHER = load_module(ROOT / "tools" / "fetch_receiver_scan.py", "fetch_receiver_scan")
COMPILER = load_module(ROOT / "tools" / "compile_scan.py", "compile_receiver_scan")


class ReceiverServer:
    def __init__(self, *, incomplete=False, mismatch=False, redirect=False,
                 object_count_mismatch=False, malformed_length=False, transient=False,
                 duplicate_object=False):
        base = {
            "scanId": "receiverscan01",
            "placeId": 3623096087,
            "partCount": 2,
            "version": "30.1.0",
            "gameName": "Synthetic Receiver Game",
            "objects": [],
        }
        self.parts = {
            1: dict(base, partIndex=1, scanStats={"recorded": 2, "complete": True},
                    featureEvidence={"rebirth": {}},
                    objects=[{"path": "Workspace.A", "class": "Part", "scanOrdinal": 1}]),
            2: dict(base, partIndex=2,
                    interactionHistoryChunk=[{"featureCandidate": "rebirth",
                                              "evidenceLevel": "interaction-observed",
                                              "outcomeVerified": False}],
                    objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 1}]),
        }
        if mismatch:
            self.parts[2]["scanId"] = "wrongscan01"
        if duplicate_object:
            self.parts[2]["objects"][0]["path"] = "Workspace.A"
        self.metadata = {
            "scanId": "receiverscan01",
            "placeId": 3623096087,
            "version": "30.1.0",
            "gameName": "Synthetic Receiver Game",
            "partCount": 2,
            "receivedAt": "2026-11-02T15:00:00Z",
        }
        if object_count_mismatch:
            self.parts[1]["scanStats"]["recorded"] = 3
        self.incomplete = incomplete
        self.redirect = redirect
        self.malformed_length = malformed_length
        self.transient = transient
        self.transient_failures = 0
        self.paths = []
        self.server = None
        self.thread = None

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.paths.append(self.path)
                if owner.redirect and self.path.endswith("/metadata"):
                    self.send_response(302)
                    self.send_header("Location", self.server.base_url + "/capture")
                    self.end_headers()
                    return
                if owner.transient and self.path.endswith("/part-2") and owner.transient_failures == 0:
                    owner.transient_failures += 1
                    self.send_response(503)
                    self.end_headers()
                    return
                prefix = "/reports/read-secret/receiverscan01/"
                if self.path == prefix + "metadata":
                    payload = {"metadata": owner.metadata}
                elif self.path.startswith(prefix + "part-"):
                    index = int(self.path.rsplit("-", 1)[1])
                    if owner.incomplete and index == 2:
                        self.send_response(404)
                        self.end_headers()
                        return
                    payload = owner.parts[index]
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                length = "not-a-number" if owner.malformed_length else str(len(body))
                self.send_header("Content-Length", length)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ReceiverImportTests(unittest.TestCase):
    def test_complete_scan_imports_and_compiles(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            result = FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                        "receiverscan01", output, allow_http=True)
            plan = COMPILER.compile_scan(output)
            self.assertEqual(result["scanId"], "receiverscan01")
            self.assertEqual(result["partCount"], 2)
            self.assertEqual(result["objectCount"], 2)
            self.assertFalse(result["localPayloadEquivalent"])
            self.assertEqual(plan["integrity"]["objects"], 2)
            release = pathlib.Path(temp) / "release"
            release_run = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_release.py"), str(output),
                 "--output", str(release)], text=True, capture_output=True, timeout=30)
            self.assertEqual(release_run.returncode, 0, release_run.stderr)
            self.assertTrue((release / "release-manifest.json").is_file())
            self.assertEqual(len(list(output.glob("part-*.json"))), 2)
            manifest = json.loads((output / "receiver-manifest.json").read_text())
            self.assertEqual(manifest["scanId"], "receiverscan01")
            self.assertEqual(manifest["receiverIntegrity"]["integrityStatus"],
                             "verified-after-retrieval")
            self.assertFalse(any(path.endswith("/integrity") for path in receiver.paths))
            self.assertNotIn("read-secret", json.dumps(manifest))

    def test_transient_part_failure_is_retried(self):
        with ReceiverServer(transient=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            result = FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                        "receiverscan01", output, allow_http=True)
            self.assertEqual(result["objectCount"], 2)
            self.assertEqual(receiver.transient_failures, 1)
            self.assertEqual(sum(path.endswith("/part-2") for path in receiver.paths), 2)

    def test_missing_part_fails_without_publishing_directory(self):
        with ReceiverServer(incomplete=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "unexpected HTTP status 404"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_part_identity_mismatch_fails_without_publishing_directory(self):
        with ReceiverServer(mismatch=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "part identity mismatch"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_duplicate_object_identity_fails_without_publication(self):
        with ReceiverServer(duplicate_object=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "duplicate receiver object identity"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_redirect_is_not_followed_with_read_key(self):
        with ReceiverServer(redirect=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "unexpected HTTP status 302"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(any(path == "/capture" for path in receiver.paths))
            self.assertFalse(output.exists())

    def test_downloaded_object_count_must_match_scan_metadata(self):
        with ReceiverServer(object_count_mismatch=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "Object count mismatch"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_malformed_content_length_is_rejected(self):
        with ReceiverServer(malformed_length=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "invalid receiver content length"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_cli_requires_environment_read_key_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            environment = os.environ.copy()
            environment.pop("LYCOLES_READ_KEY", None)
            run = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "fetch_receiver_scan.py"),
                 "https://receiver.invalid", "receiverscan01", "--output",
                 str(pathlib.Path(temp) / "scan")],
                text=True, capture_output=True, env=environment, timeout=10)
            self.assertEqual(run.returncode, 2)
            self.assertIn("LYCOLES_READ_KEY is required", run.stderr)

    def test_http_requires_explicit_test_override(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "HTTPS receiver endpoint required"):
                FETCHER.fetch_scan("http://127.0.0.1:1", "read-secret", "receiverscan01",
                                   pathlib.Path(temp) / "scan")

    def test_existing_output_is_rejected_before_network_access(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "output path already exists"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertEqual(receiver.paths, [])


if __name__ == "__main__":
    unittest.main()
