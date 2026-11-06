"""Regression coverage for inspector Luau compilation/register-pressure limits."""

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "LycolesUniversalInspector.lua"
COMPILE_DEFAULTS = (
    ROOT / "build" / "luau-0.744" / "luau-compile",
    Path("/tmp/luau-0.744/luau-compile"),
)
AST_DEFAULTS = (
    ROOT / "build" / "luau-0.744" / "luau-ast",
    Path("/tmp/luau-0.744/luau-ast"),
)
LUAU_COMPILE = (
    Path(os.environ["LUAU_COMPILE_BIN"])
    if os.environ.get("LUAU_COMPILE_BIN")
    else next((path for path in COMPILE_DEFAULTS if path.is_file()), COMPILE_DEFAULTS[0])
)
LUAU_AST = (
    Path(os.environ["LUAU_AST_BIN"])
    if os.environ.get("LUAU_AST_BIN")
    else next((path for path in AST_DEFAULTS if path.is_file()), AST_DEFAULTS[0])
)
POTASSIUM_LOCAL_LIMIT = 200
ROOT_LOCAL_PRESSURE_BUDGET = 170


def _local_declaration_count(stat: dict) -> int:
    stat_type = stat.get("type")
    if stat_type == "AstStatLocal":
        return len(stat.get("vars") or [])
    if stat_type == "AstStatLocalFunction":
        return 1
    return 0


def _root_local_pressure(ast_output: str) -> int:
    data = json.loads(ast_output)
    active = 0
    maximum = 0
    for stat in data["root"]["body"]:
        active += _local_declaration_count(stat)
        maximum = max(maximum, active)
        if stat.get("type") == "AstStatBlock":
            scoped = active + sum(
                _local_declaration_count(child) for child in stat.get("body") or []
            )
            maximum = max(maximum, scoped)
    return maximum


@unittest.skipUnless(LUAU_COMPILE.is_file(), "official Luau compiler not installed")
class InspectorCompilerLimitTests(unittest.TestCase):
    def test_inspector_compiles_without_register_overflow_in_all_modes(self):
        for optimization in range(3):
            for debug in range(3):
                with self.subTest(optimization=optimization, debug=debug):
                    completed = subprocess.run(
                        [
                            str(LUAU_COMPILE),
                            "--null",
                            f"-O{optimization}",
                            f"-g{debug}",
                            str(SCRIPT),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    stderr = completed.stderr or ""
                    self.assertEqual(completed.returncode, 0, stderr)
                    self.assertNotIn("Out of local registers", stderr)
                    self.assertNotIn(f"exceeded limit {POTASSIUM_LOCAL_LIMIT}", stderr)

    @unittest.skipUnless(LUAU_AST.is_file(), "official Luau AST tool not installed")
    def test_root_local_pressure_stays_below_potassium_safety_budget(self):
        completed = subprocess.run(
            [str(LUAU_AST), str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        pressure = _root_local_pressure(completed.stdout)
        self.assertLessEqual(
            pressure,
            ROOT_LOCAL_PRESSURE_BUDGET,
            f"root local pressure {pressure} exceeds Potassium safety budget "
            f"{ROOT_LOCAL_PRESSURE_BUDGET}",
        )


if __name__ == "__main__":
    unittest.main()
