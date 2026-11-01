# v106 integrated client observation release

This release connects the existing v104 inspection normalizer, v106 evidence-gated feature planner, Luau GUI generator, and independent artifact verifier.

## Generate

```bash
python tools/integrated_pipeline_v106.py --inspection inspection.json --place-id 85896571713843 --output build/v106
python tools/integrated_pipeline_v106.py --output build/v106 --verify-only
```

Outputs:
- `inspection-report.json` — normalized v104 inspection data
- `feature-plan.json` — supported read-only controls with terminal class identity, plus unsupported observations
- `LycolesFunctionalObserver.client.lua` — generated Luau GUI with class-aware terminal lookup and live refresh callbacks
- `quality-report.json` and `inspection-diagnostics.json` — deterministic coverage and mapping diagnostics
- `manifest.json` — deterministic artifact hashes and verification claims

## Behavior

The GUI has one working refresh button per supported observation, refresh-all, text filtering, optional two-second auto-refresh, and unload controls. It resolves intermediate client-visible path segments by name and requires both the observed name and `ClassName` for the terminal object. It catches property read errors, rejects mismatched Place IDs, and replaces a previous instance of itself. It never treats an observed instance as proof of server-side gameplay authority.

The generator emits only class/property pairs from the explicit read-only registry, including text/value objects, GUI visibility, `ProximityPrompt.Enabled`, `ClickDetector.Name`, `Tool.Name`, and `ScreenGui.Enabled`. Unknown or mismatched contracts are reported as unsupported rather than receiving empty or misleading controls.

## Test

```bash
python -B -m unittest tests.test_integrated_pipeline_v106 -v
npm ci --ignore-scripts
npm run test:luau
```

The Python tests cover full generation, reproducibility, tamper detection, class/property contract validation, class-aware lookup, unsupported classification, place mismatch, verification claims, diagnostics, and missing artifacts. The Node suite parses representative generated v54/v82/v104/v106 Luau with the bundled WebAssembly grammar.

## Limits

Parser checks establish syntax but do not execute Roblox APIs. Intermediate path segments remain name-based because normalized v104 paths do not preserve class or sibling ordinal identity; repeated same-name/same-class instances remain ambiguous. No Roblox runtime test, third-party executor test, or gameplay verification is implied. Client-visible properties may not reflect authoritative server state. This release does not provide remote invocation, anti-cheat evasion, or server-authoritative gameplay manipulation.

## Next integration target

Preserve richer class/ordinal identity across every path segment and add controlled Roblox runtime validation for explicitly implemented client-local reads.
