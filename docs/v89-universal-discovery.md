# v89 — Universal Evidence-to-Action Discovery

v89 discovers candidate inputs and observable outcomes from v87 event logs for any place ID. It groups keyboard and GUI inputs, detects numeric increases/decreases and string/boolean changes, requires repeated independent capture sessions and negative controls, and writes review-only contracts with stable IDs and a SHA-256 manifest.

Run:

```powershell
py tools/universal_discovery_v89.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v89
```

Outputs: `discovery-v89.json`, `contracts-for-review-v89.json`, `manifest-v89.json`.

Run regression tests:

```powershell
py -m unittest discover -s tests -p test_universal_discovery_v89.py -v
```

Supply original raw `LYCOLES_V87_EVENT` logs, not a summary JSON. A review candidate is not causal proof or an executable action. No input injection or game remotes are used.
