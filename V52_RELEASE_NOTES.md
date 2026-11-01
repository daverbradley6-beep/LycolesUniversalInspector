# v52 — Integrated offline release and smoke testing

One command executes the existing v51 pipeline, runs all versioned Python tests, and produces a unified v52 release directory with an automatic v46 sampler, a v47 diagnostic dashboard, and a v48 passive observer. A synthetic v48 receipt drives the v49 feature synthesis and v51 action compiler through the full offline integration path.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v52.ps1
```

Optional real receipt (JSON from the v48 passive observer):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v52.ps1 -Receipt .\receipt-v48.json
```

Synthetic artifacts live in `build/release-v52`. Real receipt artifacts, when provided, live in `build/release-v52-live`. The two directories are intentionally separated to prevent synthetic evidence being mistaken for live verification.

**Scope:** This build generates working diagnostic and local read-only actions where object classes and paths match. It does not establish gameplay mechanics or server-side outcomes in arbitrary Roblox games. Those require authorized game-specific interfaces and live integration tests.
