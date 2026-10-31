# Lycoles v36 — verified multipart scan integration

v36 adds two new offline Python modules and a Windows runner.

- `tools/scan_adapter_v36.py` runs the existing `compile_scan.py` integrity validator before exporting real client-visible object records from numbered JSON parts. It preserves `scanOrdinal` and original object counts.
- `tools/match_scan_features_v36.py` matches v32 feature paths against the validated scan, **without silently collapsing duplicate object paths**. Missing, ambiguous and uniquely observed paths are distinguished.
- `tools/run_v36.ps1` runs the repository regression suite and then the source-analysis, lexical-audit, multipart-adaptation and matching pipeline.
- 13 new local unit tests cover both modules.

Run from the repository root with a complete multipart export in `scan-parts` and readable scripts in `examples`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v36.ps1 -ScanParts .\scan-parts
```

Reports include `build/scan-objects-v36.json` and `build/feature-match-v36.json`.

**Important limits:** the multipart compiler rejects missing parts and incomplete scans. The matching report is static evidence only: path presence and source corroboration do not prove Roblox gameplay functionality. No server-side behavior or anti-cheat evasion is generated. The main Roblox inspector remains v30.0.0.

Testing: the two new modules passed 13/13 local unit tests before upload. The full repository suite and live Roblox runtime have not been executed here.
