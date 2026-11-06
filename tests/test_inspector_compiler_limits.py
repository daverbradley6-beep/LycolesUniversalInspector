"""Regression coverage for inspector Luau compilation/register-pressure limits."""

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "LycolesUniversalInspector.lua"
DEFAULTS = (
    ROOT / "build" / "luau-0.744" / "luau-compile",
    Path("/tmp/luau-0.744/luau-compile"),
)
LUAU_COMPILE = (
    Path(os.environ["LUAU_COMPILE_BIN"])
    if os.environ.get("LUAU_COMPILE_BIN")
    else next((path for path in DEFAULTS if path.is_file()), DEFAULTS[0])
)


@unittest.skipUnless(LUAU_COMPILE.is_file(), "official Luau compiler not installed")
class InspectorCompilerLimitTests(unittest.TestCase):
    def test_inspector_compiles_without_register_overflow(self):
        completed = subprocess.run(
            [str(LUAU_COMPILE), str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = completed.stderr or ""
        self.assertEqual(completed.returncode, 0, stderr)
        self.assertNotIn("Out of local registers", stderr)
        self.assertNotIn("exceeded limit 200", stderr)

    def test_inspector_bytecode_register_index_stays_below_executor_limit(self):
        completed = subprocess.run(
            [str(LUAU_COMPILE), str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        stderr = completed.stderr or ""
        self.assertEqual(completed.returncode, 0, stderr)
        registers = [int(match.group(1)) for match in re.finditer(r"\bR(\d+)\b", completed.stdout or "")]
        self.assertTrue(registers, "expected Luau disassembly register references")
        # Potassium reported local-register overflow above 200; keep a buffer below that threshold.
        self.assertLessEqual(max(registers), 199)


if __name__ == "__main__":
    unittest.main()
