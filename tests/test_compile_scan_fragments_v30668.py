import importlib.util
import json
import pathlib
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "compile_scan.py"
spec = importlib.util.spec_from_file_location("compiler_fragments_v30668", SOURCE)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


class CompileScanFragmentReconstructionTests(unittest.TestCase):
    def _write_parts(self, folder: pathlib.Path, parts: list[dict]) -> None:
        for index, payload in enumerate(parts, 1):
            (folder / f"{index}.json").write_text(json.dumps(payload, ensure_ascii=False))

    def test_summary_hex_fragments_reconstruct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)
            base = {
                "scanId": "hexsum001",
                "placeId": 3623096087,
                "partCount": 4,
                "version": "30.6.68",
                "objects": [],
            }
            payload = {
                "schemaVersion": "31.0.targeted-evidence-session.1",
                "sessionId": "hex-summary-session",
                "samples": {
                    "cameraSamples": [{"kind": "camera", "note": "🔥" * 60}],
                    "timelineEvents": [{"kind": "timeline", "step": 7}],
                },
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            hex_payload = encoded.encode("utf-8").hex()
            split = max(2, len(hex_payload) // 2)
            chunk_key = "targetedCaptureSessionSummaryChunkedFragments"
            metadata = dict(
                base,
                partIndex=1,
                scanStats={"recorded": 2, "complete": True},
                diagnostics={"complete": True, "rootAccountingValid": True},
                featureEvidence={"rebirth": {}},
                interactionDiagnostics={
                    "historyTotal": 0,
                    "targetedCaptureSessionSummary": {},
                    "targetedCaptureSessionSummaryExportMode": "separate-bounded-parts",
                    "targetedCaptureSessionSummaryChunkSchema": "30.6.interaction-diagnostics-fragment-chunk.2",
                    "targetedCaptureSessionSummaryChunkKind": "json-fragment",
                    "targetedCaptureSessionSummaryChunkEncoding": "hex-utf8-json",
                    "targetedCaptureSessionSummaryChunkKey": chunk_key,
                    "targetedCaptureSessionSummaryEncodedLength": len(encoded),
                    "chunkedInteractionDiagnosticSummaryFields": [
                        {
                            "field": "targetedCaptureSessionSummary",
                            "chunkKey": chunk_key,
                            "chunkKind": "json-fragment",
                            "chunkEncoding": "hex-utf8-json",
                            "encodedLength": len(encoded),
                            "fragmentCount": 2,
                        }
                    ],
                },
            )
            chunk_one = dict(
                base,
                partIndex=2,
                interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=1,
                interactionDiagnosticsChunk=[
                    {
                        "schemaVersion": "30.6.interaction-diagnostics-fragment-chunk.2",
                        "fragmentEncoding": "hex-utf8-json",
                        "fragmentIndex": 1,
                        "fragmentCount": 2,
                        "fragmentHex": hex_payload[:split],
                        "fragmentHexLength": len(hex_payload[:split]),
                    }
                ],
            )
            chunk_two = dict(
                base,
                partIndex=3,
                interactionDiagnosticsChunkKey=chunk_key,
                interactionDiagnosticsChunkStart=2,
                interactionDiagnosticsChunk=[
                    {
                        "schemaVersion": "30.6.interaction-diagnostics-fragment-chunk.2",
                        "fragmentEncoding": "hex-utf8-json",
                        "fragmentIndex": 2,
                        "fragmentCount": 2,
                        "fragmentHex": hex_payload[split:],
                        "fragmentHexLength": len(hex_payload[split:]),
                    }
                ],
            )
            objects = dict(
                base,
                partIndex=4,
                objects=[
                    {"path": "Workspace.A", "class": "Part", "scanOrdinal": 1},
                    {"path": "Workspace.B", "class": "Part", "scanOrdinal": 1},
                ],
            )
            self._write_parts(path, [metadata, chunk_one, chunk_two, objects])
            plan = compiler.compile_scan(path)
            rebuilt = (plan.get("interactionDiagnostics") or {}).get("targetedCaptureSessionSummary") or {}
            self.assertEqual(rebuilt.get("sessionId"), "hex-summary-session")

    def test_history_fragments_reconstruct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)
            base = {
                "scanId": "hexhist001",
                "placeId": 3623096087,
                "partCount": 4,
                "version": "30.6.68",
                "objects": [],
            }
            event = {
                "featureCandidate": "rebirth",
                "path": "LocalPlayer.PlayerGui.ScreenGui.Quests.Frame.Main.Prizes.Tabs.Playtime.Button",
                "sample": "🔥" * 900,
            }
            encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            hex_payload = encoded.encode("utf-8").hex()
            split = max(2, len(hex_payload) // 2)
            metadata = dict(
                base,
                partIndex=1,
                scanStats={"recorded": 2, "complete": True},
                diagnostics={"complete": True, "rootAccountingValid": True},
                featureEvidence={"rebirth": {}},
                interactionDiagnostics={"historyTotal": 1, "recentInteractions": []},
            )
            history_one = dict(
                base,
                partIndex=2,
                interactionHistoryChunk=[
                    {
                        "schemaVersion": "30.6.interaction-history-fragment.1",
                        "recordId": "history:1",
                        "fragmentEncoding": "hex-utf8-json",
                        "fragmentIndex": 1,
                        "fragmentCount": 2,
                        "encodedLength": len(encoded),
                        "fragmentHex": hex_payload[:split],
                        "fragmentHexLength": len(hex_payload[:split]),
                    }
                ],
            )
            history_two = dict(
                base,
                partIndex=3,
                interactionHistoryChunk=[
                    {
                        "schemaVersion": "30.6.interaction-history-fragment.1",
                        "recordId": "history:1",
                        "fragmentEncoding": "hex-utf8-json",
                        "fragmentIndex": 2,
                        "fragmentCount": 2,
                        "encodedLength": len(encoded),
                        "fragmentHex": hex_payload[split:],
                        "fragmentHexLength": len(hex_payload[split:]),
                    }
                ],
            )
            objects = dict(
                base,
                partIndex=4,
                objects=[
                    {"path": "Workspace.A", "class": "Part", "scanOrdinal": 1},
                    {"path": "Workspace.B", "class": "Part", "scanOrdinal": 1},
                ],
            )
            self._write_parts(path, [metadata, history_one, history_two, objects])
            plan = compiler.compile_scan(path)
            history = plan.get("observedInteractionHistory") or []
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].get("sample"), "🔥" * 900)
            self.assertEqual((plan.get("integrity") or {}).get("interactionEvents"), 1)

    def test_history_fragments_missing_piece_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)
            base = {
                "scanId": "hexhist002",
                "placeId": 3623096087,
                "partCount": 3,
                "version": "30.6.68",
                "objects": [],
            }
            event = {"featureCandidate": "rebirth", "sample": "abc" * 200}
            encoded = json.dumps(event, sort_keys=True, separators=(",", ":"))
            hex_payload = encoded.encode("utf-8").hex()
            metadata = dict(
                base,
                partIndex=1,
                scanStats={"recorded": 2, "complete": True},
                diagnostics={"complete": True, "rootAccountingValid": True},
                featureEvidence={"rebirth": {}},
                interactionDiagnostics={"historyTotal": 1, "recentInteractions": []},
            )
            history_one = dict(
                base,
                partIndex=2,
                interactionHistoryChunk=[
                    {
                        "schemaVersion": "30.6.interaction-history-fragment.1",
                        "recordId": "history:1",
                        "fragmentEncoding": "hex-utf8-json",
                        "fragmentIndex": 1,
                        "fragmentCount": 2,
                        "encodedLength": len(encoded),
                        "fragmentHex": hex_payload,
                        "fragmentHexLength": len(hex_payload),
                    }
                ],
            )
            objects = dict(
                base,
                partIndex=3,
                objects=[
                    {"path": "Workspace.A", "class": "Part", "scanOrdinal": 1},
                    {"path": "Workspace.B", "class": "Part", "scanOrdinal": 1},
                ],
            )
            self._write_parts(path, [metadata, history_one, objects])
            with self.assertRaisesRegex(ValueError, "Missing history fragments"):
                compiler.compile_scan(path)


if __name__ == "__main__":
    unittest.main()
