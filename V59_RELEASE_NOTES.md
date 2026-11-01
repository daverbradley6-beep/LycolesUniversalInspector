# Lycoles Universal Inspector v59 — Evidence-gated gameplay planning

## Goal

v59 connects previously separate discovery, contract validation, and gameplay workflow generation. It no longer compiles a gameplay runner solely because a contract exists: the tool must also appear in the place-matched v54 discovery evidence.

## Added

- `tools/gameplay_planner_v59.py`: analyzes a v54 receipt, proposes candidate Tool actions, validates explicit v58 authorization and matches tool names.
- Builds `gameplay-plan-v59.json` with candidates, executable-contract matches, unsupported contracts, evidence summary and SHA-256 fingerprint.
- Emits `gameplay-runner-v59.luau` **only** when at least one authorized contract has matching discovery evidence. The runner is built from v58's bounded Tool workflow engine.
- New `tests/test_v59_planner.py` checks candidate-only behavior, authorization, matching, missing tools, place mismatch and generated output.
- `tools/run_v59.ps1` chains the previous offline suites and v59 planning.
- CI runs the v59 tests on pushes.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v59.ps1
```

With a v54 receipt:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v59.ps1 -DiscoveryReceipt .\receipt-v54.txt
```

With a developer-authorized v58 action contract and v54 receipt:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v59.ps1 -DiscoveryReceipt .\receipt-v54.txt -ActionSpec .\approved-actions-v58.json
```

## Validation boundaries

This release is **not** a general-purpose Roblox exploit or anti-cheat bypass generator. Presence of a Tool and an approved contract is insufficient to prove server-side action success. Generated actions must be verified in an authorized live environment. No live Roblox tests or full repository Python test run were completed during this release; committed tests and CI configuration are available for verification.
