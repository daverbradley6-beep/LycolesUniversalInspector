# v49 — Evidence-ranked feature synthesis

This release adds a deterministic offline compiler which converts v48 passive observations into a feature-candidate catalog. Each family is classified as **change-observed**, **presence-only**, or **no-evidence**. Every candidate retains its supporting paths and requires controlled, authorized action/outcome validation before it can be treated as a verified mechanic.

Run `powershell -ExecutionPolicy Bypass -File .\tools\run_v49.ps1`. To compile candidates from a v48 receipt, run `powershell -ExecutionPolicy Bypass -File .\tools\run_v49.ps1 -Receipt .\receipt-v48.json`.

The resulting `build/feature-candidates-v49.json` is not a gameplay script and does not approve or invoke server remotes. The client receipt remains untrusted.
