# Lycoles Universal Inspector v60 — Verification replay and guarded release

## Summary
v60 introduces an offline gameplay-observation replay engine and a release gate. This is a material step beyond generating an action GUI: candidate actions are only packaged in the gameplay runner when they match discovery evidence, have an explicitly approved contract, and pass a supplied outcome trace.

## Implemented
- `tools/verification_replay_v60.py`: strict trace schema, place matching, monotonic timestamps, bounded event count, numeric metric checks, per-attempt delta and timeout checks.
- Per-action outcomes: `observational_pass`, `not_verified`, and attempt-level statuses including `timed_out`, `failed`, `incomplete` and `invalid_trace`.
- Release filtering: only discovery-matched actions with all expected outcomes observed are included in the generated v59 gameplay runner.
- Reports: `verification-v60.json`, `release-manifest-v60.json` and a fingerprint.
- Synthetic fixtures, ten regression tests, consolidated PowerShell runner and GitHub Actions smoke-test step.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v60.ps1
```

For an authorized place with real evidence and trace:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v60.ps1 -DiscoveryReceipt .\receipt-v54.json -ActionSpec .\approved-v58.json -ActionTrace .\action-trace-v60.json
```

The synthetic fixtures use place ID 123 and **are not proof of any real Roblox game functionality**.

## Limitations and verification status
- Offline trace data is untrusted and cannot prove causality or server acceptance. The manifest explicitly marks server outcomes as unverified.
- The action engine still supports standard Roblox Tool activation only.
- The trace replay is an offline verification model, not a live event collector; supplying a fabricated trace could produce an observational pass. Do not treat that as live verification.
- No live Roblox execution or full Python regression run was completed by the author during this release. CI steps were committed, not independently observed as passing.
