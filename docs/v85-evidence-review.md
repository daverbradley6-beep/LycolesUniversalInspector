# v85 — Evidence-to-contract review bridge

This version converts v83 result summaries plus an existing GUI-path catalog into a review worksheet, reducing manual contract transcription. It never infers a missing path or approves an action automatically.

## Run

```powershell
py tools/evidence_to_contracts_v85.py --place-id 85896571713843 --review build/release-v83/action-results-v83.json --catalog approved.json --output build/release-v85
py -m unittest discover -s tests -p "test_evidence_to_contracts_v85.py" -v
```

The generated `contracts-for-review-v85.json` has `approved: false` and `executionEnabled: false` on every candidate. Review each GUI path and expected signal before explicitly approving any contract. The existing v84 release builder accepts approved GUI contracts, but cannot validate real in-game activation on its own.

The v83 review must match the catalog's action IDs. Unknown IDs and non-GUI actions are reported as skipped. v85 is a review bridge, not universal game script generation. No remotes, bypasses, or automatic gameplay execution are added.
