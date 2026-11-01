# Lycoles v103 — Inspection quality gate

v103 adds an independent offline quality gate for client-visible inspection reports from existing Roblox games. It accepts `observations`, `objects`, `instances`, `entries` or a bare list. It validates client-visible roots, normalizes `game.Workspace...` paths, recognizes a conservative set of object classes, removes duplicate paths and records rejection reasons.

## Local test results

13/13 unit tests passed in the development container using Python's standard-library unittest. This validates the standalone v103 quality module and test fixtures; it does **not** verify integration with all historical inspector formats, executor compatibility or Roblox gameplay. GitHub Actions is also configured for Python 3.10–3.13, but its result has not been independently confirmed.

## Usage

```powershell
py -m unittest discover -s tests -p test_inspection_quality_v103.py -v
py tools/inspection_quality_v103.py --inspection inspection.json --place-id 85896571713843 --output build/inspection-quality-v103.json
```

The report includes accepted/rejected counts, individual client-visible object paths, duplicate and unsupported-class counts, and a SHA-256 digest printed by the CLI. It deliberately records `canAutomate: false`, `gameplayFunctionsGenerated: 0`, and `verifiedInGame: false` because object visibility does not prove executable functionality. No game-side actions, remote invocation, bypasses or stealth mechanisms are generated.

## Next steps

Validate against genuine inspector export variants and integrate quality thresholds into the generation pipeline. Extend only where observed data supports it; do not invent gameplay capabilities.
