# Lycoles Universal Inspector v54

## Changes
- Bounded, incremental breadth-first discovery across ten Roblox client-visible services, with per-service budgets so Workspace cannot monopolize the scan.
- Sibling-aware path segments (`JSON-quoted name#ordinal@ClassName`) to distinguish repeated names under the same parent. Ordinals are snapshot-relative and may change when siblings are inserted or removed.
- Up to 300 priority objects re-sampled per observation to capture changes despite incremental discovery.
- High-signal classes include ValueBase, GuiButton, Tool, ProximityPrompt and remote metadata. **No remotes are called**.
- Bounded per-sample batch streaming with explicit sample/batch indices, completeness validation, change-only priority updates, and legacy receipt parsing compatibility.
- Offline analyzer accepts v53 and v54 receipts. Legacy duplicate names are flagged as ambiguous rather than claimed as stable unique identities.
- Generated read-only evidence dashboard (when a receipt is provided), explicitly separating observed objects from verified actions.
- New offline tests, PowerShell runner and CI coverage.

## Build once

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v54.ps1
```

This runs previous offline suites plus v54 tests and writes `build/release-v54/balanced-discovery-v54.luau`.

For analysis of an existing v53 receipt:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v54.ps1 -DiscoveryReceipt .\receipt-v53.json
```

For the final v54 live test, run the generated Luau in the matching place and save **all** console lines from `LYCOLES_V54_BATCH_STREAM_BEGIN` through `LYCOLES_V54_BATCH_STREAM_END`. Each sample contains indexed `LYCOLES_V54_BATCH_BEGIN`, `LYCOLES_V54_BATCH`, and `LYCOLES_V54_BATCH_END` records. Analysis:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v54.ps1 -DiscoveryReceipt .\receipt-v54.txt
```

## Evidence boundary

This is read-only client observation, not automatic gameplay automation. Arbitrary Roblox games cannot be guaranteed to expose all mechanics client-side; server-side mechanics and authorization cannot be established from instance names. No anti-cheat evasion or ban bypass is implemented. Offline tests do not constitute live gameplay verification.
