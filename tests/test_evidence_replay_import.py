import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "evidence_replay_import.py"
SPEC = importlib.util.spec_from_file_location("evidence_replay_import", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _part_payload(scan_id, place_id, part_count, part_index, objects, *, with_stats=False):
    payload = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "partIndex": part_index,
        "version": "30.6",
        "objects": objects,
    }
    if with_stats:
        payload["scanStats"] = {"recorded": len(objects), "complete": True}
    return payload


def _raw_json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _observation_payload(*, place_id, baseline_scan_id, scan_id):
    return {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "sourceDiagnostics": {
            "scanMode": "dynamic-observations",
            "baselineScanId": baseline_scan_id,
        },
        "integrity": {
            "scanComplete": True,
            "placeId": place_id,
            "scanId": scan_id,
            "baselineScanId": baseline_scan_id,
            "parts": 1,
            "interactionEvents": 2,
        },
        "features": [{"feature": "shops", "interactionEvents": 2}],
    }


class EvidenceReplayImportTests(unittest.TestCase):
    def test_zip_reconstruction_manifest_match_and_observation_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan_id = "144CF595-C681-4A72-9E20-8759A7B3619B"
            place_id = 85896571713843
            part_count = 3

            part1 = _part_payload(scan_id, place_id, part_count, 1, [{"path": "Workspace.A", "class": "Part"}], with_stats=True)
            part2 = _part_payload(scan_id, place_id, part_count, 2, [{"path": "Workspace.B", "class": "Part"}])
            part3 = _part_payload(scan_id, place_id, part_count, 3, [{"path": "Workspace.C", "class": "Part"}])
            raw1, raw2, raw3 = _raw_json(part1), _raw_json(part2), _raw_json(part3)

            manifest = {
                "scanId": scan_id,
                "placeId": place_id,
                "partCount": part_count,
                "expectedParts": part_count,
                "partContentDigests": [
                    {"partIndex": 1, "sha256": hashlib.sha256(raw1).hexdigest()},
                    {"partIndex": 2, "sha256": hashlib.sha256(raw2).hexdigest()},
                    {"partIndex": 3, "sha256": hashlib.sha256(raw3).hexdigest()},
                ],
            }
            raw_manifest = _raw_json(manifest)

            zip_one = root / "baseline-1.zip"
            with zipfile.ZipFile(zip_one, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("part-0001.json", raw1)
                archive.writestr("part-0002.json", raw2)
                archive.writestr("manifest.json", raw_manifest)

            zip_two = root / "baseline-2.zip"
            with zipfile.ZipFile(zip_two, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("part-0003.json", raw3)

            observation_path = root / "observation.json"
            observation_scan_id = "live-observation-16FF57E3-5660-4C8A-A594-124AAE0511D0"
            observation_path.write_bytes(_raw_json(_observation_payload(
                place_id=place_id,
                baseline_scan_id=scan_id,
                scan_id=observation_scan_id,
            )))

            replay_dir = root / "replay"
            result = MODULE.import_replay_package(
                baseline_inputs=[zip_one, zip_two],
                observation_inputs=[observation_path],
                output_dir=replay_dir,
                expected_place_id=place_id,
                expected_baseline_scan_id=scan_id,
                expected_observation_scan_ids=[observation_scan_id],
            )

            self.assertEqual(result["baseline"]["mode"], "multipart")
            self.assertEqual(result["baseline"]["scanId"], scan_id)
            self.assertEqual(result["baseline"]["placeId"], place_id)
            self.assertEqual(result["baseline"]["partCount"], part_count)
            self.assertEqual(len(result["baseline"]["partDigests"]), part_count)
            self.assertEqual(len(result["observations"]), 1)

            loaded = MODULE.load_replay_package(replay_dir)
            self.assertEqual(loaded["baseline"]["mode"], "multipart")
            self.assertTrue(pathlib.Path(loaded["baseline"]["partsDir"]).is_dir())
            self.assertEqual(len(loaded["observations"]), 1)

    def test_scan_identity_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan_id = "baseline-scan-a"
            place_id = 85896571713843
            payload = _part_payload(scan_id, place_id, 1, 1, [{"path": "Workspace.A", "class": "Part"}], with_stats=True)
            parts_dir = root / "parts"
            parts_dir.mkdir()
            (parts_dir / "part-0001.json").write_bytes(_raw_json(payload))

            with self.assertRaisesRegex(ValueError, "baseline scanId mismatch"):
                MODULE.import_replay_package(
                    baseline_inputs=[parts_dir],
                    observation_inputs=[],
                    output_dir=root / "replay",
                    expected_place_id=place_id,
                    expected_baseline_scan_id="different-scan",
                )

    def test_replay_reimport_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan_id = "33E9EFC5-AAA5-4093-A65A-791C765CDDD7"
            place_id = 85896571713843
            part_count = 2
            parts_dir = root / "parts"
            parts_dir.mkdir()
            (parts_dir / "part-0001.json").write_bytes(_raw_json(_part_payload(
                scan_id, place_id, part_count, 1,
                [{"path": "Workspace.One", "class": "Part"}],
                with_stats=True,
            )))
            (parts_dir / "part-0002.json").write_bytes(_raw_json(_part_payload(
                scan_id, place_id, part_count, 2,
                [{"path": "Workspace.Two", "class": "Part"}],
            )))

            observation_path = root / "obs.json"
            obs_scan_id = "live-observation-73131FB0-AE39-4FD4-8EEB-8189EB05EA80"
            observation_path.write_bytes(_raw_json(_observation_payload(
                place_id=place_id,
                baseline_scan_id=scan_id,
                scan_id=obs_scan_id,
            )))

            replay_one = root / "replay-one"
            one = MODULE.import_replay_package(
                baseline_inputs=[parts_dir],
                observation_inputs=[observation_path],
                output_dir=replay_one,
                expected_place_id=place_id,
                expected_baseline_scan_id=scan_id,
                expected_observation_scan_ids=[obs_scan_id],
            )

            replay_two = root / "replay-two"
            two = MODULE.import_replay_package(
                baseline_inputs=[replay_one],
                observation_inputs=[],
                output_dir=replay_two,
                expected_place_id=place_id,
                expected_baseline_scan_id=scan_id,
                expected_observation_scan_ids=[obs_scan_id],
            )

            self.assertEqual(one["baseline"]["scanId"], two["baseline"]["scanId"])
            self.assertEqual(one["baseline"]["partDigests"], two["baseline"]["partDigests"])
            self.assertEqual(
                sorted(item["scanId"] for item in one["observations"]),
                sorted(item["scanId"] for item in two["observations"]),
            )


if __name__ == "__main__":
    unittest.main()
