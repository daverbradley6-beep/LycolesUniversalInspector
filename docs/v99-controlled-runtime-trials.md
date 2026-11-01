# Lycoles v99 — Controlled Runtime Trial Evaluation

v99 introduces a reusable evaluation layer for **actual recorded trials** from authorized Roblox Studio tests. The tool does not execute Roblox code: it consumes JSONL observations recorded by the developer and applies independent-session, matched negative-control, and Wilson 95% lower-bound confidence gates.

## Smoke test

```powershell
py -m unittest discover -s tests -p test_runtime_trial_evaluator_v99.py -v
py tools/runtime_trial_evaluator_v99.py --trial-log examples/v99-trials.jsonl --output build/v99-evaluation.json
```

The included data is **synthetic** and must not be represented as actual in-game validation. It contains two independent example sessions with 10 action trials and 10 negative-control trials each.

## Data format

Each line is a JSON object with `schemaVersion: "99.trial"`, numeric `placeId` and `userId`, `sessionId`, `actionId`, `stat`, nonnegative integer `index`, `kind` (`action` or `control`), `expected` (`increase`, `decrease`, `equal`), and numeric `before` and `after`. Each session/index pair must be unique. Use separate sessions and controls for each tested action/stat/outcome group.

The evaluator defaults to at least two independent sessions, three action trials and three control trials per session, zero control contamination, and a Wilson 95% lower bound of at least 0.5 for the expected action outcome. These are *screening criteria*, not proof of causality. A group passing all criteria is labelled `review_candidate`, not `verifiedInGame`.

## Limitations

The tool does not verify that trials were actually run in Roblox, that the action caused the result, or that a script works in a third-party game. In-game verification requires an authenticated, authorized runtime harness and a trusted capture process. v99 is an offline statistical review tool that can support that future workflow.
