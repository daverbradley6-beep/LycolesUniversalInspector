# Lycoles v98 — Independent Release Verification

v98 adds an independent offline verifier for the v97 evidence-release artifacts. It checks SHA-256 integrity, the expected file set, cross-document place IDs, review-only status, candidate references, and whether a generated action has been silently inserted into a proposal. It also provides a deterministic build comparison helper.

## Run

```powershell
py tools/universal_pipeline_v97.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v97
py tools/release_verifier_v98.py --directory build/release-v97 --report build/release-v97/verification-v98.json
py -m unittest discover -s tests -p test_release_verifier_v98.py -v
```

A passing result verifies artifact consistency only; it does not establish that any Roblox gameplay action is functional. The generated proposals are intentionally not executable without explicit developer review and a supported Studio implementation. CI is configured for Python 3.10–3.13. Test success and in-game functionality must be checked independently.
