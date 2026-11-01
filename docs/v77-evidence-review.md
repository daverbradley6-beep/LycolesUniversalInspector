# v77: Multi-signal evidence review and draft action contracts

v77 builds on v76. It analyzes v76 and compatible v77 input logs, detects consistent changes in numeric stats, booleans, strings, and nested state objects, and creates **non-executable** review drafts. It does not claim that a correlated input caused a change, and does not bypass any game's security mechanisms.

## Usage

```powershell
py tools/evidence_review_v77.py --place-id 85896571713843 --event-log events-v76.txt --output build/release-v77
py -m unittest discover -s tests -p 'test_evidence_review_v77.py' -v
```

Outputs: `evidence-review-v77.json` and `contract-drafts-v77.json`. Default minimum is 3 observations. No game-specific paths are hardcoded into the analyzer. The analyzer retains Unicode stat names when the input log is correctly encoded; already corrupted text requires re-exporting the original log. It does not fabricate unobserved UI or inventory state; nested signals are supported when future recorder versions supply them.

## Limitations

- All proposals are explicitly unverified and execution is disabled.
- Repeated events from one capture can be confounded by ongoing background changes; independent sessions and negative controls remain necessary.
- GUI and keyboard records are separate until independently shown equivalent.
- Roblox gameplay runtime testing requires running the recorder in a game; Python tests cannot substitute for this.
