# Lycoles v40 — executable diagnostic correctness

v40 fixes a critical problem in the v39 diagnostic generator: Python JSON arrays such as `["Workspace.A"]` are not valid Luau table literals. v40 emits valid Luau tables such as `{"Workspace.A"}` and safely escapes path strings.

## Changes
- New `tools/diagnostic_generator_v40.py` converts v39 game-first evidence into a read-only Luau GUI.
- Caps generated paths, deduplicates entries, rejects invalid paths, and allows only known Roblox service roots.
- Adds a close button, scrolling list, and found/not-found labels.
- New `tests/test_v40_diagnostic.py` includes 11 regression cases for syntax, escaping, filtering, safety and UI behavior.
- New `tools/run_v40.ps1` executes v3x and v40 regression tests, validates the receiver fixture, discovers game systems and emits `build/diagnostic-v40.luau`.
- Extends the existing GitHub Actions workflow with v40 tests and diagnostic generation.

## Run
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v40.ps1
```

The bundled sanitized Muscle Legends fixture is used by default. The diagnostic only checks client-visible object existence; it does not invoke game remotes or verify gameplay functionality.

## Verification
Files were uploaded to GitHub. The tests and CI pipeline were configured, but no passing CI run or in-game execution has yet been confirmed. A full Roblox client execution test is still required.
