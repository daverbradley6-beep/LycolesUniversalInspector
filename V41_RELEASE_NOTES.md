# Lycoles v41 — Evidence-gated game-first feature specifications

This update turns v39's structural hypotheses into explicit, machine-readable **read-only feature specifications** and a generated diagnostic GUI with a working check button for each discovered family. It does **not** fabricate gameplay automation from object names.

## New files
- `tools/feature_spec_v41.py`: generates `feature-spec-v41.json` and `feature-inspector-v41.luau`.
- `tests/test_v41_feature_spec.py`: 12 unit tests for spec validation, deduplication, Luau serialization, and fail-closed behavior.
- `tools/run_v41.ps1`: end-to-end local runner.
- Existing CI workflow extended to run v41 tests and real-fixture generation.

## Run
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v41.ps1
```

Uses the sanitized Muscle Legends inspection fixture in `examples/` by default. The output GUI includes a button for each discovered structural family; clicking it counts currently visible object paths. No RemoteEvents are invoked and no game state is changed.

## Verification limitations
GitHub upload is verified separately. Passing v41 tests, GitHub Actions, and Roblox runtime behavior must be confirmed before claiming success. The tool's current feature output is **read-only diagnostics**, not verified training, trading, or other gameplay implementations.
