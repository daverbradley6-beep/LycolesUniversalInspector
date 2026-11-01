# Lycoles v92 — Universal Diagnostic Builder

v92 takes raw v87 evidence logs, applies v91 temporal overlap quarantine, and produces a read-only Luau diagnostics panel plus an implementation backlog for review candidates. It does not create or execute gameplay actions.

## Generate

```powershell
py tools/diagnostic_builder_v92.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v92
```

Artifacts: `review-v92.json`, `implementation-backlog-v92.json`, `diagnostics-v92.luau`, `manifest-v92.json`.

The generated Luau panel can be opened in the target place to inspect discovered candidate relationships, without interacting with the game or invoking remotes. It guards against the wrong place ID and has a Close button.

## Regression tests

```powershell
py -m unittest discover -s tests -p test_diagnostic_builder_v92.py -v
py -m unittest discover -s tests -p test_temporal_attribution_v91.py -v
py -m unittest discover -s tests -p test_evidence_release_v90.py -v
```

GitHub Actions runs the suites on Python 3.10–3.13. Offline test success is not Roblox gameplay verification. Generated implementation backlog entries are unapproved and execution-disabled until an authorized, game-specific action adapter is developed and tested.
