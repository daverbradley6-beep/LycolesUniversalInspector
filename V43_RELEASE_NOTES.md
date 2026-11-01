# Lycoles v43 — Client diagnostic receipt round-trip

v43 introduces the first explicit **offline → in-game diagnostic → offline evidence correlation** workflow. It does not claim to generate verified gameplay automation.

## New components
- `tools/receipt_collector_v43.py`: generates `build/receipt-collector-v43.luau`, a read-only button that checks paths in the live client and prints a JSON receipt between clear console markers.
- `tools/receipt_verifier_v43.py`: validates that a receipt matches the exact scan, place, source fingerprint, and path inventory in `build/generation-manifest-v42.json`. Rejects duplicates, unknown paths, nonboolean results and mismatched identities.
- `tests/test_v43_receipts.py`: 15 tests.
- `tools/run_v43.ps1`: regression and generation pipeline, with optional receipt verification.
- GitHub Actions: v43 tests and generator step.

## Run on Windows
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v43.ps1
```

Open `build/receipt-collector-v43.luau` in your authorized Roblox testing environment, run it, click the diagnostic button, and copy the JSON line printed between `LYCOLES_V43_RECEIPT_BEGIN` and `LYCOLES_V43_RECEIPT_END` into `client-receipt.json`.

Then run:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v43.ps1 -Receipt .\client-receipt.json
```

The resulting `build/receipt-verification-v43.json` reports per-feature path existence and missing observations. **A client-provided receipt is not authenticated, and object presence is not proof of gameplay behavior or server outcomes.**

## Verification status
Files uploaded and retrieved from GitHub. Passing local/CI tests and live Roblox execution must be confirmed separately.
