# Lycoles v39 — Game-first discovery

v38 successfully processed the receiver fixture, but its nine source-derived feature candidates came from unrelated cashier/hairdresser examples. v39 introduces an independent **game-first** discovery pass.

## New functionality
- Extract structural system hypotheses from receiver-indexed object paths and classes, rather than borrowing feature names from unrelated example scripts.
- Categorize observed paths into training, pets, trading, economy, progression, combat, movement, interface and world families.
- Report distinct paths, observation counts, classes, source roots, and path collisions; never treat keyword matches as proof of working gameplay functions.
- Generate a **read-only Luau diagnostic GUI** that checks whether selected observed paths currently exist in the client. It does not invoke remotes or perform gameplay actions.
- Include 11 targeted regression tests, a Windows runner, and a GitHub Actions workflow that exercises the sanitized 360-record Muscle Legends fixture.

## Run on Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v39.ps1
```

The default receiver fixture is `examples/muscle-legends-receiver-v15-sanitized.json`, already committed to the repository. Override with `-ReceiverBundle .\receiver-bundle.json` to use a local inspection.

Outputs:
- `build/game-discovery-v39.json`
- `build/diagnostic-v39.luau`
- `build/receiver-summary-v38.json`

## Verification boundaries

Repository files have been uploaded, but GitHub Actions results and a full local checkout test must be checked before claiming that all tests passed. No in-game behavior has been verified. Dynamic observations do not establish complete game coverage. A read-only diagnostic is not automatic gameplay script generation.
