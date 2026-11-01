# v83 — Action result evidence analysis

v83 converts the structured `LYCOLES_V82_RESULT` output of the v82 interactive test GUI into a reviewable action report. It counts activation requests, errors, leaderstat changes and optionally matches changes against explicitly specified expected outcomes. **An activation request is never considered proof of gameplay success.**

## Usage

1. Use the v82 test GUI to click approved actions manually.
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

v82 logs contain no unique run ID, so the analyser does not claim session independence or causal verification. The results are observational only, and the v82 test GUI does not prove whether `GuiButton:Activate()` works for a specific game. The v83 analyser does not execute any game actions, bypass security or generate remote calls. Run the included tests and verify behavior in the live Roblox client before relying on a generated script.
