# Lycoles Universal Inspector v56

v56 extends the evidence-to-interface pipeline with a consolidated quality-gated release compiler.

## Changes
- Fixed a critical v54 traversal defect: Roblox services at the DataModel root have no Parent; they now enter the scan.
- Replaced v55's fragile path regular expression with a JSON string decoder, correctly handling quoted names containing slashes, dots and escaped quotes.
- Added v56 feature grouping, receipt quality summary, deterministic manifest fingerprint, static audit and four release artifacts.
- Added fixture-based compilation tests and CI integration.
- The generated GUI contains functional **inspection controls**, not verified gameplay-action controls.

## Run
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v56.ps1
```
If a v54 receipt is available:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v56.ps1 -DiscoveryReceipt .\receipt-v54.txt
```
Output: `build/release-v56/universal-evidence-explorer-v56.luau`, `feature-bundle-v56.json`, `quality-report-v56.json`, and `static-audit-v56.json`.

## Validation status
The source changes and tests are committed. The complete v56 test suite has not been run in a local checkout by the author; the user's PowerShell runner and GitHub CI are the authoritative checks. Three isolated JSON-quoted path parsing edge cases were exercised locally. No Roblox live test or server-side action validation has occurred.

## Fundamental boundary
Read-only client discovery cannot automatically infer authorized server-side gameplay semantics in arbitrary Roblox games. Feature names and observed values do not prove a gameplay action works. The compiler does not implement server-side operations or anti-cheat circumvention.
