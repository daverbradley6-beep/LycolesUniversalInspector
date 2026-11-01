# Lycoles Universal Inspector v44 — Adaptive live evidence
This release adds a bounded read-only multi-snapshot client probe, strict offline receipt validation, and temporal evidence classification.

## Run
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v44.ps1
```
Execute `build/adaptive-probe-v44.luau` in the matching Roblox place. Click the GUI to capture up to eight snapshots at least three seconds apart. Change normal gameplay states between captures (e.g. open/close menus, equip a pet, visit training areas). Each click prints a complete receipt between `LYCOLES_V44_RECEIPT_BEGIN` and `LYCOLES_V44_RECEIPT_END`; copy the **last JSON object only** into `client-receipt-v44.json`.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v44.ps1 -Receipt .\client-receipt-v44.json
```
Read `build/adaptive-report-v44.json`.

## Limits
Only client-visible instance presence is checked; no RemoteEvent invocation, gameplay action, anti-cheat bypass, server outcome verification, or automatic gameplay script approval is performed. Dynamic streaming, source paths containing literal dots, and client/server visibility differences can yield false negatives. Receipts are client-submitted and unauthenticated. Eight samples maximum per run; each snapshot is rate-limited to one per three seconds. The Python analyzer permits up to 32 snapshots for offline comparison.
