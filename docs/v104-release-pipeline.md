# Lycoles v104 — Reproducible client observation releases

v104 unifies offline inspection validation, duplicate/conflicting-class detection, read-only Luau observer GUI generation, deterministic JSON output and SHA-256 integrity auditing.

## Run

```powershell
py -m unittest discover -s tests -p test_release_pipeline_v104.py -v
py tools/release_pipeline_v104.py --inspection examples/v102-client-inventory.json --place-id 85896571713843 --output build/release-v104
py tools/release_pipeline_v104.py --audit-only --output build/release-v104
```

The build produces `report-v104.json`, `LycolesObserverV104.client.lua` and `manifest-v104.json`. It supports `observations`, `objects`, `instances`, `entries` and bare arrays. Output is limited to 150 observations; inspection input is limited to 50,000 records. It rejects non-client-visible roots, unsupported classes, conflicting class evidence and malformed paths. It requires a matching Place ID when supplied in the input.

**Scope:** This is a read-only client observation generator, not automatic gameplay automation. No server requests, exploit injection, anti-cheat bypass or input automation are generated. The sample inventory is illustrative, not confirmed in-game. Executing LocalScripts in a third-party Roblox game is not supported by the standard client.

The v104 algorithm was exercised locally with 22 passing tests before repository upload; the final GitHub-hosted file and its workflow have not independently been executed in this session. The GitHub workflow tests Python 3.10–3.13.
