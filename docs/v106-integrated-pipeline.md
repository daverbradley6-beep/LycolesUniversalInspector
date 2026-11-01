# v106 integrated client observation release

This release connects the existing v104 inspection normalizer, v106 evidence-gated feature planner, Luau GUI generator, and independent artifact verifier.

## Generate

```bash
python tools/integrated_pipeline_v106.py --inspection inspection.json --place-id 85896571713843 --output build/v106
python tools/integrated_pipeline_v106.py --output build/v106 --verify-only
```

Outputs:
- `inspection-report.json` — normalized v104 inspection data
- `feature-plan.json` — supported read-only controls and unsupported observations
- `LycolesFunctionalObserver.client.lua` — generated Luau GUI with live refresh callbacks
- `manifest.json` — deterministic artifact hashes and verification claims

## Behavior

The GUI has one working refresh button per supported observation, a refresh-all button, and an unload button. It resolves client-visible object paths, catches property read errors, rejects mismatched Place IDs, and replaces a previous instance of itself. It never treats an observed instance as proof of server-side gameplay authority.

The generator only emits read-only property controls for explicitly supported classes. ProximityPrompt and other unimplemented actions are reported as unsupported rather than given empty GUI controls. This is deliberate: a UI control without an implementation is a release defect.

## Test

```bash
python -m unittest discover -s tests -p 'test_integrated_pipeline_v106.py' -v
```

The dedicated CI workflow runs the suite on Python 3.10–3.13. The tests cover full generation, reproducibility, tamper detection, unsupported classification, place mismatch, invalid feature kinds, verification-claim tampering, and missing artifacts.

## Limits

No Roblox runtime test, third-party executor test, or gameplay verification is implied by Python unit tests. The generated code requires an environment permitting client-side GUI creation. Client-visible properties may not reflect authoritative server state. This release does not provide remote invocation, anti-cheat evasion, or server-authoritative gameplay manipulation.

## Next integration target

Introduce a registry of explicitly implemented client-local actions with per-action runtime evidence, and test generated Luau against a Luau parser and a controlled Roblox test environment.
