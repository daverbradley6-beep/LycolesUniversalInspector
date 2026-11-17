import pathlib
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "LycolesUniversalInspector.lua"
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
LUAU_BIN = ROOT / "build" / "luau-0.744" / "luau"


def extract_block(start_token: str, end_token: str) -> str:
    start = SOURCE_TEXT.find(start_token)
    end = SOURCE_TEXT.find(end_token)
    if start < 0 or end < 0 or end <= start:
        raise AssertionError(f"missing marker block: {start_token}..{end_token}")
    return SOURCE_TEXT[start:end + len(end_token)]


def run_luau(script: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as tmp:
        tmp.write(script)
        path = pathlib.Path(tmp.name)
    try:
        proc = subprocess.run(
            [str(LUAU_BIN), str(path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"luau runtime failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return proc.stdout.strip()
    finally:
        path.unlink(missing_ok=True)


@unittest.skipUnless(LUAU_BIN.is_file(), "luau runtime binary unavailable")
class InspectorRuntimeDiagnosticsTests(unittest.TestCase):
    def test_runtime_diagnostics_collect_stage_and_failure_entries(self):
        diagnostics_block = extract_block("-- RUNTIME_DIAGNOSTICS_BEGIN", "-- RUNTIME_DIAGNOSTICS_END")
        harness = textwrap.dedent(
            f"""
            local __env = {{}}
            function getgenv()
                return __env
            end
            {diagnostics_block}
            pushRuntimeStage("gui-created", "panel")
            pushRuntimeFailure("collecting", "scan exploded")
            local payload = getgenv().LycolesInspectorDiagnostics()
            print(payload.lastStage, payload.lastFailure.stage, tostring(#payload.stages), tostring(#payload.failures))
            """
        )
        out = run_luau(harness)
        parts = out.split()
        self.assertGreaterEqual(len(parts), 4)
        self.assertEqual(parts[0], "gui-created")
        self.assertEqual(parts[1], "collecting")
        self.assertEqual(parts[2], "2")
        self.assertEqual(parts[3], "1")

    def test_runtime_diagnostics_stage_history_is_bounded(self):
        diagnostics_block = extract_block("-- RUNTIME_DIAGNOSTICS_BEGIN", "-- RUNTIME_DIAGNOSTICS_END")
        harness = textwrap.dedent(
            f"""
            local __env = {{}}
            function getgenv()
                return __env
            end
            {diagnostics_block}
            for i=1,140 do
                pushRuntimeStage("s-" .. tostring(i), "")
            end
            local payload = getgenv().LycolesInspectorDiagnostics()
            print(tostring(#payload.stages), payload.stages[1].stage, payload.stages[#payload.stages].stage)
            """
        )
        out = run_luau(harness)
        parts = out.split()
        self.assertEqual(parts[0], "120")
        self.assertEqual(parts[1], "s-21")
        self.assertEqual(parts[2], "s-140")


class InspectorBootOrderingTests(unittest.TestCase):
    def test_workflow_helpers_declared_before_scan_context_helpers(self):
        decl = SOURCE_TEXT.find("local WORKFLOW_HELPERS = {}")
        helper = SOURCE_TEXT.find("-- SCAN_CONTEXT_HELPERS_BEGIN")
        self.assertGreaterEqual(decl, 0)
        self.assertGreaterEqual(helper, 0)
        self.assertLess(decl, helper)
        self.assertEqual(SOURCE_TEXT.count("local WORKFLOW_HELPERS = {}"), 1)


if __name__ == "__main__":
    unittest.main()
