# Lycoles Universal Inspector v55 — evidence-to-interface compiler

## Scope

This release converts a **v54 live receipt** into an auditable, searchable **read-only GUI**. It is the first dedicated v54-to-interface stage; it does not claim to produce verified gameplay automation.

- Validates place ID, receipt schema, observed paths and action permissions.
- Classifies evidence into Training, Progress, Pets, World, Interface and Other.
- Generates up to 120 inspection controls from discovered high-signal instances.
- Resolves sibling-aware JSON-quoted instance paths at click time, including names with dots, quotes and slashes.
- Shows current client-visible scalar values for supported Roblox instances.
- Refuses to compile contracts that falsely mark gameplay actions as verified.
- Keeps remote invocation, anti-cheat bypass and gameplay mutation disabled.
- Adds v55 unit tests, consolidated PowerShell runner and CI test step.

## Commands

Build and run regression tests (no receipt required):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v55.ps1
```

Build and compile a v54 live receipt:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v55.ps1 -DiscoveryReceipt .\receipt-v54.txt
```

Outputs: `build/release-v55/feature-contract-v55.json`, `evidence-analysis-v55.json`, and `evidence-explorer-v55.luau`.

## Limits

v53 receipts can be analysed, but their legacy paths cannot be safely converted to v55 controls because duplicate sibling identity was lost. A v54 receipt is required for the GUI. Sibling ordinals can drift when instances are added or removed. No server-side gameplay effects or game-specific actions are verified by the scanner. Offline unit tests are not live Roblox validation.
