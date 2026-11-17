# v83 — Action result evidence analysis

v83 converts structured `LYCOLES_V82_RESULT` records into a reviewable compatibility report. Current v82 output is fail-closed and records unsupported activation attempts as failures; the analyzer also retains compatibility with older result logs that recorded activation requests and leaderstat changes. **Neither a request nor an observed change is proof of gameplay success.**

## Usage

1. Use the v82 diagnostic panel to evaluate approved GUI contract paths; current output records unsupported activation failures.
2. Save full `LYCOLES_V82_RESULT` lines to `results-v82.txt`.
3. Run:

```powershell
py tools/action_result_analyzer_v83.py --place-id 85896571713843 --result-log results-v82.txt --contracts approved.json --output build/release-v83
py -m unittest discover -s tests -p "test_action_result_analyzer_v83.py" -v
```

Add `--result-log` again for additional logs. `--contracts` is optional. To match expected outcomes, add an explicit `expectedSignals` array to an approved contract:

```json
"expectedSignals": [{"stat": "🥚 Hatches", "operator": "increase"}]
```

Output files: `action-results-v83.json` and `parse-warnings-v83.json`.

## Important limitations

The updated v82 runner includes a capture ID and attempt index. v83 deduplicates matching attempts, rejects conflicting duplicates, and counts distinct captures. Older v82 logs without IDs remain supported but cannot be deduplicated across copies. Current v82 records availability failures because it does not call the nonexistent public `GuiButton:Activate()` method. Historical requested-action records remain observational; neither distinct captures nor matching expected changes prove causality. The v83 analyzer never executes game actions, bypasses security, or generates remote calls.
