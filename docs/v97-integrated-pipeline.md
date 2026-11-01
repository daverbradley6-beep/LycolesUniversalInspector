# Lycoles v97 — Integrated evidence release pipeline

Version 97 coordinates v87 evidence ingestion, v91 temporal conflict quarantine, review-candidate selection, deterministic staging, SHA-256 auditing and optional v96 developer-approved compilation into v95 Roblox Studio client/server scripts.

## Existing Bubble Gum Simulator INFINITY evidence

```powershell
py tools/universal_pipeline_v97.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v97
```

Output: `review-v97.json`, `proposal-v97.json`, `plan-v97.json`, `manifest-v97.json`. The proposal is unapproved by default and never contains an invented implementation. If there are no eligible candidates, the pipeline still produces diagnostics but no executable action.

## Authorized game-owner compilation

Only if your review has eligible candidates and you have an explicitly approved v96 mapping with matching evidence and an implementation in a game you control:

```powershell
py tools/universal_pipeline_v97.py --place-id 123456 --event-log session1.txt --event-log session2.txt --mapping approved-v96-mapping.json --output build/release-v97
```

The compiled client/server scripts are written to `build/release-v97/approved-studio/`. They must be installed and tested in Roblox Studio in an authorized experience. The compiler does not automatically discover a server API from a third-party game.

## Tests

```powershell
py -m unittest discover -s tests -p test_universal_pipeline_v97.py -v
py -m unittest discover -s tests -p test_evidence_to_actions_v96.py -v
```

GitHub Actions is configured to test on Python 3.10–3.13. Offline passing tests and artifact auditing do not prove in-game functionality. No anti-ban, remote bypass, or third-party game execution is included.
