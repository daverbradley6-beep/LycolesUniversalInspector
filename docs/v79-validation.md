# Lycoles v79 — independent-session validation

v79 reads v76/v78 event logs and produces review-only contract drafts. It requires three observations across two distinct capture IDs by default, detects inconsistent state changes, and flags changes observed after other inputs as possible confounders.

## Run

```powershell
py tools/action_validation_v79.py --place-id 85896571713843 --event-log events-v78.txt --output build/release-v79
py -m unittest discover -s tests -p "test_action_validation_v79.py" -v
```

Use repeated `--event-log` arguments to combine recordings from different sessions. Outputs: `validation-v79.json`, `contract-drafts-v79.json`, `parse-warnings-v79.json`.

The validator never executes actions, and `review_candidate` does not mean proven causality. Distinct capture IDs, non-overlapping observation windows and control trials are needed for stronger evidence. The parser retains valid Unicode; previously corrupted names cannot be reconstructed automatically.
