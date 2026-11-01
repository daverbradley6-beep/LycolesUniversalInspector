# Lycoles Universal Inspector v58 — Bounded gameplay workflows

This release focuses on the gap between discovering a mechanic and implementing a usable, testable action.

## Added
- v58 explicit action contracts extending v57 with `repeatCount` (1–20) and `cooldownSeconds` (0.2–10).
- Generated Luau runner using normal `Tool:Activate()` with optional equip, bounded repetitions, cancellation, progress and error handling.
- Per-attempt expected leaderstats delta observation; aborts on missing/replaced metric, activation failure or timeout.
- Single-action concurrency guard and stop control.
- Regression tests for schema validation, mutation safety, generated controls and release output.
- Consolidated `run_v58.ps1` and CI test integration.

## Build
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v58.ps1
```
With an explicitly authorized v58 contract:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v58.ps1 -ActionSpec .\authorized-v58.json
```

Generated files: `build/release-v58/gameplay-runner-v58.luau` and `gameplay-manifest-v58.json`.

## Important limitations
- Requires a developer-approved contract for the target place; automatic discovery generates only disabled proposals.
- A value change after activation is observational, not proof of causality or server acceptance.
- Supports Roblox Tool activation only, not arbitrary game actions.
- Does not generate remote invocations or anti-cheat bypasses.
- Source, tests and CI were committed; complete regression and live Roblox tests have **not** been independently executed in this environment.
