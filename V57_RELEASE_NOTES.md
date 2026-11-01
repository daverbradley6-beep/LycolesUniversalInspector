# Lycoles Universal Inspector v57 — Gameplay Contracts

v57 shifts development from passive inspection to **explicit gameplay action execution and verification**.

## What was implemented

- A declarative action contract validator with strict schema, place ID, unique action IDs, supported operations, expected metric and timeout.
- A Luau action runner that can equip and activate a named Roblox Tool in an owner-authorized test place, then wait for a numeric leaderstats delta.
- Status messages distinguish unsupported prerequisites, activation failure, observed outcome and unverified outcome.
- A discovery-to-proposal tool that extracts client-visible Tool candidates from v54 receipts, but never automatically approves them.
- A one-command runner, unit tests and CI integration.
- No guessed RemoteEvent or RemoteFunction calls, exploit hooks, anti-cheat evasion, or claims of universal gameplay functionality.

## Commands

Offline regression suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v57.ps1
```

Generate disabled gameplay candidates from a v54 receipt:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v57.ps1 -DiscoveryReceipt .\receipt-v54.txt
```

Compile explicitly approved test-place contracts:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v57.ps1 -ActionSpec .\path\to\authorized-contract.json
```

The example file `examples/v57-authorized-test-place.json` is **disabled** (`ownerAuthorized=false`) and uses a placeholder place ID. It must not be used as proof of authorization.

## Verification limitations

The tool runner uses standard Roblox client Tool APIs, but server-side outcomes are not guaranteed. A metric increase is an observed correlation, not necessarily causation. A live test in a place whose developer has authorized the workflow is necessary before claiming the action works. All new tests are committed but the full Python suite has not been independently executed in this environment.
