"""Actual Luau execution tests against bounded simulated Roblox APIs."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from artifact_contract_v107 import validate_source_semantics
from controlled_luau_v108 import (
    MAX_PROGRAM_BYTES,
    ControlledExecutionError,
    execute,
    run_bounded_program,
)
from feature_planner_v107 import plan
from install_luau_v108 import BINARIES, _extract
from integrated_pipeline_v107 import emit_luau
from path_identity_v107 import build
from release_pipeline_v104 import canonical

PLACE = 85896571713843
DEFAULT_LUAU = Path("/tmp/luau-0.744/luau")
LUAU = Path(os.environ.get("LUAU_BIN", DEFAULT_LUAU))


def node(name, class_name, *, properties=None, children=None):
    return {
        "name": name,
        "className": class_name,
        "properties": properties or {},
        "children": children or [],
    }


def hierarchy(*roots):
    return {"schemaVersion": "107.hierarchy-fixture", "placeId": PLACE, "roots": list(roots)}


def rich_plan(ordinal=2):
    return plan(build({"placeId": PLACE, "observations": [{
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Coins", "className": "IntValue", "ordinal": ordinal},
        ],
        "className": "IntValue",
    }]}, PLACE))


def string_plan():
    return plan(build({"placeId": PLACE, "observations": [{
        "path": ["Workspace", "Stats", "Message"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Message", "className": "StringValue", "ordinal": 1},
        ],
        "className": "StringValue",
    }]}, PLACE))


def legacy_plan():
    return plan(build({"placeId": PLACE, "objects": [{
        "path": ["Workspace", "Stats", "Coins"],
        "className": "IntValue",
    }]}, PLACE))


def workspace_with_coins(*coins):
    return node("Workspace", "Workspace", children=[
        node("Stats", "Folder", children=list(coins)),
    ])


class LuauInstallerV108Tests(unittest.TestCase):
    def test_archive_contract_extracts_only_expected_binaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in BINARIES:
                    output.writestr(name, b"binary")
            hashes = {name: hashlib.sha256(b"binary").hexdigest() for name in BINARIES}
            binary = _extract(archive, Path(tmp) / "runtime", hashes)
            self.assertEqual(binary.read_bytes(), b"binary")
            self.assertTrue(os.access(binary, os.X_OK))

    def test_archive_contract_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in (*BINARIES, "unexpected"):
                    output.writestr(name, b"binary")
            hashes = {name: hashlib.sha256(b"binary").hexdigest() for name in BINARIES}
            with self.assertRaises(ValueError):
                _extract(archive, Path(tmp) / "runtime", hashes)

    def test_archive_contract_rejects_unsafe_archive_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in BINARIES:
                    output.writestr(name, b"binary")
                output.writestr("../outside", b"binary")
            hashes = {name: hashlib.sha256(b"binary").hexdigest() for name in BINARIES}
            with self.assertRaises(ValueError):
                _extract(archive, Path(tmp) / "runtime", hashes)
            self.assertFalse((Path(tmp) / "outside").exists())

    def test_archive_contract_rejects_executable_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in BINARIES:
                    output.writestr(name, b"binary")
            hashes = {name: hashlib.sha256(b"other").hexdigest() for name in BINARIES}
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                _extract(archive, Path(tmp) / "runtime", hashes)

    def test_archive_contract_rejects_stale_target_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in BINARIES:
                    output.writestr(name, b"binary")
            runtime = Path(tmp) / "runtime"
            runtime.mkdir()
            (runtime / "stale").write_bytes(b"stale")
            hashes = {name: hashlib.sha256(b"binary").hexdigest() for name in BINARIES}
            with self.assertRaisesRegex(ValueError, "unsafe"):
                _extract(archive, runtime, hashes)

    def test_archive_contract_rejects_existing_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "luau.zip"
            with ZipFile(archive, "w") as output:
                for name in BINARIES:
                    output.writestr(name, b"binary")
            runtime = Path(tmp) / "runtime"
            runtime.mkdir()
            (runtime / "luau").symlink_to(Path(tmp) / "outside")
            hashes = {name: hashlib.sha256(b"binary").hexdigest() for name in BINARIES}
            with self.assertRaisesRegex(ValueError, "unsafe"):
                _extract(archive, runtime, hashes)

    def test_workflow_actions_are_pinned_to_full_commit_shas(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "v108-controlled-luau.yml"
        ).read_text(encoding="utf-8")
        references = [
            line.split("@", 1)[1].split()[0]
            for line in workflow.splitlines()
            if "uses: actions/" in line
        ]
        self.assertEqual(len(references), 3)
        self.assertTrue(all(
            len(reference) == 40
            and all(character in "0123456789abcdef" for character in reference)
            for reference in references
        ))


@unittest.skipUnless(LUAU.is_file(), "official Luau runtime not installed")
class ControlledLuauV108Tests(unittest.TestCase):
    def test_actual_generated_luau_resolves_class_qualified_ordinal(self):
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 10}),
            node("Coins", "StringValue", properties={"Value": "ignored"}),
            node("Coins", "IntValue", properties={"Value": 20}),
        ))
        result = execute(rich_plan(), fixture, PLACE, LUAU)
        self.assertTrue(result["luauExecuted"])
        self.assertTrue(result["readOnly"])
        self.assertTrue(result["simulatedEnvironment"])
        self.assertFalse(result["robloxRuntimeVerified"])
        self.assertFalse(result["gameplayVerified"])
        self.assertEqual(result["features"][0]["status"], "resolved")
        self.assertEqual(result["features"][0]["observedValue"], "20")
        self.assertTrue(result["modelAgreement"])

    def test_generated_ui_signals_filter_toggle_and_unload_execute(self):
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 7}),
        ))
        result = execute(rich_plan(1), fixture, PLACE, LUAU)
        self.assertEqual(result["interactions"], {
            "autoRefreshToggled": True,
            "filterApplied": True,
            "refreshActivated": True,
            "unloadDestroyedGui": True,
        })
        self.assertEqual(result["scheduledTasks"], 1)
        self.assertEqual(result["unsupportedApiUsages"], [])

    def test_identity_mismatch_and_missing_property_fail_closed(self):
        missing_ordinal = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
        ))
        result = execute(rich_plan(2), missing_ordinal, PLACE, LUAU)
        self.assertEqual(result["features"][0]["status"], "identity_mismatch")
        missing_property = hierarchy(workspace_with_coins(node("Coins", "IntValue")))
        result = execute(rich_plan(1), missing_property, PLACE, LUAU)
        self.assertEqual(result["features"][0]["status"], "property_unavailable")

    def test_explicit_nil_property_fails_closed_and_agrees_with_model(self):
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": None}),
        ))
        result = execute(rich_plan(1), fixture, PLACE, LUAU)
        self.assertEqual(result["features"][0]["status"], "property_unavailable")
        self.assertTrue(result["features"][0]["modelAgreement"])
        self.assertTrue(result["simulationPassed"])

    def test_integral_number_value_agrees_with_luau_rendering(self):
        feature_plan = plan(build({"placeId": PLACE, "observations": [{
            "path": ["Workspace", "Stats", "Rate"],
            "pathIdentity": [
                {"name": "Workspace", "className": "Workspace", "ordinal": 1},
                {"name": "Stats", "className": "Folder", "ordinal": 1},
                {"name": "Rate", "className": "NumberValue", "ordinal": 1},
            ],
            "className": "NumberValue",
        }]}, PLACE))
        fixture = hierarchy(node("Workspace", "Workspace", children=[
            node("Stats", "Folder", children=[
                node("Rate", "NumberValue", properties={"Value": 1.0}),
            ]),
        ]))
        result = execute(feature_plan, fixture, PLACE, LUAU)
        self.assertEqual(result["features"][0]["observedValue"], "1")
        self.assertTrue(result["features"][0]["modelAgreement"])

    def test_execution_report_is_deterministic(self):
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 7}),
        ))
        self.assertEqual(
            execute(rich_plan(1), fixture, PLACE, LUAU),
            execute(rich_plan(1), fixture, PLACE, LUAU),
        )

    def test_unicode_paths_labels_and_values_execute(self):
        feature_plan = plan(build({"placeId": PLACE, "observations": [{
            "path": ["Workspace", "Stäts🚀", "硬幣"],
            "pathIdentity": [
                {"name": "Workspace", "className": "Workspace", "ordinal": 1},
                {"name": "Stäts🚀", "className": "Folder", "ordinal": 1},
                {"name": "硬幣", "className": "StringValue", "ordinal": 1},
            ],
            "className": "StringValue",
        }]}, PLACE))
        fixture = hierarchy(node("Workspace", "Workspace", children=[
            node("Stäts🚀", "Folder", children=[
                node("硬幣", "StringValue", properties={"Value": "café🚀"}),
            ]),
        ]))
        self.assertTrue(validate_source_semantics(emit_luau(feature_plan), feature_plan)["ok"])
        result = execute(feature_plan, fixture, PLACE, LUAU)
        self.assertEqual(result["features"][0]["observedValue"], "café🚀")
        self.assertTrue(result["simulationPassed"])

    def test_error_message_strings_remain_resolved_values(self):
        values = (
            "missing object or identity mismatch",
            "missing identity segment",
            "missing or ambiguous legacy path segment",
            "property unavailable",
            "unsupported path resolution",
        )
        for value in values:
            with self.subTest(value=value):
                fixture = hierarchy(node("Workspace", "Workspace", children=[
                    node("Stats", "Folder", children=[
                        node("Message", "StringValue", properties={"Value": value}),
                    ]),
                ]))
                result = execute(string_plan(), fixture, PLACE, LUAU)
                self.assertEqual(result["features"][0]["status"], "resolved")
                self.assertEqual(result["features"][0]["observedValue"], value)
                self.assertTrue(result["features"][0]["modelAgreement"])
                self.assertTrue(result["simulationPassed"])

    def test_legacy_ambiguity_executes_and_fails_closed(self):
        fixture = hierarchy(node("Workspace", "Workspace", children=[
            node("Stats", "Folder", children=[node("Coins", "IntValue", properties={"Value": 1})]),
            node("Stats", "Configuration", children=[node("Coins", "IntValue", properties={"Value": 2})]),
        ]))
        result = execute(legacy_plan(), fixture, PLACE, LUAU)
        self.assertEqual(result["features"][0]["status"], "legacy_resolution_failed")
        self.assertEqual(result["features"][0]["modelStatus"], "legacy_ambiguity")
        self.assertTrue(result["modelAgreement"])

    def test_place_mismatch_is_not_reported_as_execution_success(self):
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
        ))
        result = execute(rich_plan(1), fixture, PLACE + 1, LUAU)
        self.assertTrue(result["luauExecuted"])
        self.assertFalse(result["generatedBodyExecuted"])
        self.assertFalse(result["simulationPassed"])
        self.assertEqual(result["features"][0]["status"], "place_mismatch")
        self.assertTrue(result["modelAgreement"])

    def test_cli_returns_failure_when_simulation_does_not_pass(self):
        feature_plan = rich_plan(1)
        fixture = hierarchy(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
        ))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "feature-plan.json"
            hierarchy_path = root / "hierarchy.json"
            output_path = root / "execution.json"
            plan_path.write_bytes(canonical(feature_plan))
            hierarchy_path.write_bytes(canonical(fixture))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "controlled_luau_v108.py"),
                    "--feature-plan", str(plan_path),
                    "--hierarchy", str(hierarchy_path),
                    "--runtime-place-id", str(PLACE + 1),
                    "--luau", str(LUAU),
                    "--output", str(output_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            summary = json.loads(completed.stdout)
            self.assertFalse(summary["ok"])
            self.assertFalse(summary["simulationPassed"])
            self.assertFalse(json.loads(output_path.read_text())["simulationPassed"])

    def test_empty_plan_cannot_pass_with_mismatched_fixture_place(self):
        feature_plan = plan(build({"placeId": PLACE, "observations": []}, PLACE))
        fixture = hierarchy(node("Workspace", "Workspace"))
        fixture["placeId"] = PLACE + 1
        result = execute(feature_plan, fixture, PLACE, LUAU)
        self.assertEqual(result["features"], [])
        self.assertTrue(result["generatedBodyExecuted"])
        self.assertFalse(result["fixturePlaceMatches"])
        self.assertFalse(result["simulationPassed"])

    def test_unknown_stub_api_is_rejected_at_runtime(self):
        with self.assertRaisesRegex(ControlledExecutionError, "unsupported API"):
            run_bounded_program("print(game:UnsupportedCall())", LUAU, include_stubs=True)

    def test_execution_timeout_is_enforced(self):
        with self.assertRaisesRegex(ControlledExecutionError, "timeout"):
            run_bounded_program("while true do end", LUAU, timeout_seconds=0.1)

    def test_execution_output_limit_is_enforced(self):
        with self.assertRaisesRegex(ControlledExecutionError, "output limit"):
            run_bounded_program("while true do print(string.rep('x', 4096)) end", LUAU)

    def test_stub_injection_counts_toward_source_limit(self):
        with self.assertRaisesRegex(ValueError, "oversized"):
            run_bounded_program(" " * MAX_PROGRAM_BYTES, LUAU, include_stubs=True)

    def test_untrusted_runtime_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "luau"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)
            with self.assertRaisesRegex(ControlledExecutionError, "untrusted"):
                run_bounded_program("print('unreachable')", binary)


if __name__ == "__main__":
    unittest.main()
