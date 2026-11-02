import hashlib
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
                 duplicate_object=False, digest_mismatch=False, missing_digest=False,
                 fail_part=None):
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
            self.parts[2]["objects"][0]["class"] = "Folder"
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
        self.digest_mismatch = digest_mismatch
        self.missing_digest = missing_digest
        self.transient = transient
        self.fail_part = fail_part
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
                if owner.fail_part is not None and self.path.endswith(
                        f"/part-{owner.fail_part}"):
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
                if "/part-" in self.path and not owner.missing_digest:
                    digest = hashlib.sha256(body).hexdigest()
                    if owner.digest_mismatch and self.path.endswith("/part-2"):
                        digest = "0" * 64
                    self.send_header("X-Lycoles-Content-SHA256", digest)
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
            provenance = json.loads((release / "source-provenance.json").read_text())
            self.assertEqual(provenance["inputMode"], "receiver-import")
            self.assertTrue(provenance["receiverStoredPayloadDigestsVerified"])
            self.assertFalse(provenance["receiverResponseAuthenticityVerified"])
            self.assertFalse(provenance["localPayloadEquivalent"])
            release_manifest = json.loads((release / "release-manifest.json").read_text())
            self.assertEqual(release_manifest["sourceProvenance"], provenance)
            generated = (release / "LycolesGeneratedUtility.lua").read_text()
            self.assertIn("Receiver payload digests: verified", generated)
            self.assertIn("Response authenticity: unverified", generated)
            self.assertEqual(len(list(output.glob("part-*.json"))), 2)
            manifest = json.loads((output / "receiver-manifest.json").read_text())
            self.assertEqual(manifest["scanId"], "receiverscan01")
            self.assertEqual(manifest["receiverIntegrity"]["integrityStatus"],
                             "verified-after-retrieval")
            for entry in manifest["receiverPartContentDigests"]:
                part_path = output / f"part-{entry['partIndex']:04d}.json"
                self.assertEqual(hashlib.sha256(part_path.read_bytes()).hexdigest(),
                                 entry["sha256"])
            self.assertFalse(any(path.endswith("/integrity") for path in receiver.paths))
            self.assertNotIn("read-secret", json.dumps(manifest))

    def test_forged_receiver_authenticity_claim_blocks_compilation(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                               "receiverscan01", output, allow_http=True)
            manifest_path = output / "receiver-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["receiverResponseAuthenticityVerified"] = True
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "receiver provenance"):
                COMPILER.compile_scan(output)

    def test_imported_part_tampering_blocks_compilation(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                               "receiverscan01", output, allow_http=True)
            part = output / "part-0001.json"
            part.write_bytes(part.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "receiver provenance digest"):
                COMPILER.compile_scan(output)

    def test_persisted_part_digest_mismatch_fails_atomically(self):
        with ReceiverServer(digest_mismatch=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "receiver content digest mismatch"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_missing_persisted_part_digest_fails_atomically(self):
        with ReceiverServer(missing_digest=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "content digest is missing"):
                FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                   "receiverscan01", output, allow_http=True)
            self.assertFalse(output.exists())

    def test_matching_acknowledgement_digests_are_preserved(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            acknowledgements = []
            for index, part in receiver.parts.items():
                raw = json.dumps(part).encode("utf-8")
                acknowledgements.append({"partIndex": index,
                                         "sha256": hashlib.sha256(raw).hexdigest()})
            local_manifest = pathlib.Path(temp) / "local-manifest.json"
            local_manifest.write_text(json.dumps({
                "scanId": "receiverscan01", "placeId": 3623096087, "partCount": 2,
                "reportTransport": {"acknowledgedPartDigests": acknowledgements},
            }))
            output = pathlib.Path(temp) / "scan"
            result = FETCHER.fetch_scan(
                receiver.server.base_url, "read-secret", "receiverscan01", output,
                local_manifest=local_manifest, allow_http=True)
            self.assertTrue(result["receiverAcknowledgementDigestEquivalent"])
            self.assertFalse(result["localPayloadEquivalent"])
            imported = json.loads((output / "receiver-manifest.json").read_text())
            self.assertTrue(imported["receiverAcknowledgementDigestEquivalent"])
            plan = COMPILER.compile_scan(output)
            self.assertTrue(plan["sourceProvenance"]["receiverAcknowledgementDigestEquivalent"])
            generator = load_module(ROOT / "tools" / "generate_script.py", "generator_ack")
            self.assertIn("Inspector ACK digest equivalence: verified",
                          generator.render(plan))

    def test_conflicting_acknowledgement_digest_fails_atomically(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            local_manifest = pathlib.Path(temp) / "local-manifest.json"
            local_manifest.write_text(json.dumps({
                "scanId": "receiverscan01", "placeId": 3623096087, "partCount": 2,
                "reportTransport": {"acknowledgedPartDigests": [
                    {"partIndex": 1, "sha256": "0" * 64},
                ]},
            }))
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "does not match local acknowledgement"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    local_manifest=local_manifest, allow_http=True)
            self.assertFalse(output.exists())

    def test_transient_part_failure_is_retried(self):
        with ReceiverServer(transient=True) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            result = FETCHER.fetch_scan(receiver.server.base_url, "read-secret",
                                        "receiverscan01", output, allow_http=True)
            self.assertEqual(result["objectCount"], 2)
            self.assertEqual(receiver.transient_failures, 1)
            self.assertEqual(sum(path.endswith("/part-2") for path in receiver.paths), 2)

    def test_resume_reuses_verified_parts_after_interruption(self):
        with ReceiverServer(fail_part=2) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            resume = pathlib.Path(temp) / "resume"
            with self.assertRaisesRegex(ValueError, "unexpected HTTP status 503"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=resume, allow_http=True)
            self.assertFalse(output.exists())
            self.assertTrue((resume / "part-0001.json").is_file())
            self.assertTrue((resume / "receiver-resume.json").is_file())
            self.assertNotIn("read-secret", (resume / "receiver-resume.json").read_text())
            first_part_requests = sum(path.endswith("/part-1") for path in receiver.paths)

            receiver.fail_part = None
            result = FETCHER.fetch_scan(
                receiver.server.base_url, "read-secret", "receiverscan01", output,
                resume=resume, allow_http=True)
            self.assertEqual(result["resumedPartCount"], 1)
            self.assertEqual(result["downloadedPartCount"], 1)
            self.assertFalse(result["resumeCheckpointAuthenticated"])
            self.assertFalse(result["receiverStoredPayloadDigestsRevalidatedThisRun"])
            self.assertEqual(sum(path.endswith("/part-1") for path in receiver.paths),
                             first_part_requests)
            self.assertTrue(output.is_dir())
            plan = COMPILER.compile_scan(output)
            provenance = plan["sourceProvenance"]
            self.assertEqual(provenance["inputMode"], "receiver-import")
            self.assertEqual(provenance["resumedPartCount"], 1)
            self.assertFalse(provenance["receiverStoredPayloadDigestsRevalidatedThisRun"])
            generator = load_module(ROOT / "tools" / "generate_script.py", "generator_resume")
            generated = generator.render(plan)
            self.assertIn("Receiver digests rechecked this run: no (cached checkpoint used)",
                          generated)

    def test_tampered_resume_part_fails_without_publication(self):
        with ReceiverServer(fail_part=2) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            resume = pathlib.Path(temp) / "resume"
            with self.assertRaisesRegex(ValueError, "unexpected HTTP status 503"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=resume, allow_http=True)
            cached_part = resume / "part-0001.json"
            cached_part.write_bytes(cached_part.read_bytes() + b" ")
            receiver.fail_part = None
            with self.assertRaisesRegex(ValueError, "resume part digest mismatch"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=resume, allow_http=True)
            self.assertFalse(output.exists())

    def test_resume_metadata_drift_fails_without_publication(self):
        with ReceiverServer(fail_part=2) as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            resume = pathlib.Path(temp) / "resume"
            with self.assertRaisesRegex(ValueError, "unexpected HTTP status 503"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=resume, allow_http=True)
            receiver.metadata["version"] = "changed-version"
            receiver.fail_part = None
            with self.assertRaisesRegex(ValueError, "resume checkpoint identity mismatch"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=resume, allow_http=True)
            self.assertFalse(output.exists())

    def test_resume_and_output_paths_must_not_overlap(self):
        with ReceiverServer() as receiver, tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "scan"
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                FETCHER.fetch_scan(
                    receiver.server.base_url, "read-secret", "receiverscan01", output,
                    resume=output, allow_http=True)
            self.assertFalse(output.exists())

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
