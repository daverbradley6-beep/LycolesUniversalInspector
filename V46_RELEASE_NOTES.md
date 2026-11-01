# v46 automatic collection and receipt import

## New workflow

1. Run `powershell -ExecutionPolicy Bypass -File .\tools\run_v46.ps1`.
2. Execute `build/auto-probe-v46.luau` in the matching Roblox place. It takes six read-only snapshots automatically, four seconds apart. Play normally during collection.
3. Copy the final console output containing the `LYCOLES_V44_RECEIPT_BEGIN` and `END` markers to `console.txt`. This is still a manual step because Roblox console access is not provided to the offline Python process.
4. Run `powershell -ExecutionPolicy Bypass -File .\tools\run_v46.ps1 -Console .\console.txt`.

The importer extracts the last complete v44 receipt from console text, validates it against the manifest, and writes `build/receipt-v46.json`, `build/adaptive-report-v44.json`, and `build/evidence-contracts-v45.json`.

No gameplay features are automatically implemented, no client receipt is authenticated, and no server-side outcomes are verified. This release reduces manual collection and processing but does not promise universal gameplay automation.
