import pathlib
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "LycolesUniversalInspector.lua"
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
LUAU_BIN = ROOT / "build" / "luau-0.744" / "luau"


def extract_scan_context_helpers() -> str:
    start_token = "-- SCAN_CONTEXT_HELPERS_BEGIN"
    end_token = "-- SCAN_CONTEXT_HELPERS_END"
    start = SOURCE_TEXT.find(start_token)
    end = SOURCE_TEXT.find(end_token)
    if start < 0 or end < 0 or end <= start:
        raise AssertionError("scan context helper markers missing")
    return SOURCE_TEXT[start:end + len(end_token)]


def run_luau_harness(body: str) -> str:
    helpers = extract_scan_context_helpers()
    harness = textwrap.dedent(
        f"""
        local WORKFLOW_HELPERS = {{}}
        local guidCounter = 0
        local HttpService = {{
            GenerateGUID = function(_)
                guidCounter = guidCounter + 1
                return "guid-" .. tostring(guidCounter)
            end
        }}
        {helpers}
        {body}
        """
    )
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as tmp:
        tmp.write(harness)
        tmp_path = pathlib.Path(tmp.name)
    try:
        proc = subprocess.run(
            [str(LUAU_BIN), str(tmp_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"luau harness failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return proc.stdout.strip()
    finally:
        tmp_path.unlink(missing_ok=True)


@unittest.skipUnless(LUAU_BIN.is_file(), "luau runtime binary unavailable")
class InspectorScanContextRuntimeTests(unittest.TestCase):
    def test_initial_scan_context_is_generated_and_reused(self):
        out = run_luau_harness(
            """
            local report = {}
            local scanA, generatedA, reasonA = WORKFLOW_HELPERS.ensureReportScanContext(report)
            local scanB, generatedB, reasonB = WORKFLOW_HELPERS.ensureReportScanContext(report)
            print(scanA, tostring(generatedA), reasonA, scanB, tostring(generatedB), reasonB, report.scanId)
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 7)
        self.assertEqual(parts[0], "guid-1")
        self.assertEqual(parts[1], "true")
        self.assertEqual(parts[2], "generated")
        self.assertEqual(parts[3], "guid-1")
        self.assertEqual(parts[4], "false")
        self.assertEqual(parts[5], "existing")
        self.assertEqual(parts[6], "guid-1")

    def test_manifest_context_handles_missing_optional_scan(self):
        out = run_luau_harness(
            """
            local context = WORKFLOW_HELPERS.manifestExportContext(nil)
            print(context.kind, context.scanId, tostring(context.missingScanId), context.diagnostic)
            """
        )
        parts = out.split()
        self.assertEqual(parts[0], "manifest")
        self.assertEqual(parts[1], "none")
        self.assertEqual(parts[2], "true")
        self.assertEqual(parts[3], "scan-context-uninitialized")

    def test_manifest_context_matches_report_scan_id(self):
        out = run_luau_harness(
            """
            local report = {scanId = "scan-abc"}
            local context = WORKFLOW_HELPERS.manifestExportContext(report)
            print(context.kind, context.scanId, tostring(context.missingScanId))
            """
        )
        parts = out.split()
        self.assertEqual(parts[0], "manifest")
        self.assertEqual(parts[1], "scan-abc")
        self.assertEqual(parts[2], "false")

    def test_regression_path_no_nil_index_on_scan_context(self):
        out = run_luau_harness(
            """
            local ok, err = pcall(function()
                local report = {}
                local scanId = WORKFLOW_HELPERS.ensureReportScanContext(report)
                local context = WORKFLOW_HELPERS.manifestExportContext(report)
                if context.scanId ~= scanId then
                    error("context-mismatch")
                end
            end)
            print(tostring(ok), tostring(err))
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 1)
        self.assertEqual(parts[0], "true")


if __name__ == "__main__":
    unittest.main()
