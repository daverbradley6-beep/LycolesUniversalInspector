# Lycoles v90 — Evidence release

v90 builds a deterministic, integrity-checked evidence release from raw v87 event logs. It is not a Roblox input injector, server-remote caller, anti-ban bypass, or a working arbitrary-game executor.

## Improvements

- Deduplicates events by capture ID and event index, rejecting conflicting duplicates.
- Validates event schema and place ID.
- Discovers keyboard and GUI input groups and stat changes without game-specific assumptions.
- Requires at least two independent captures with three observations per capture for each candidate and matched negative control.
- Rejects inconsistent candidate outcomes and contaminated negative controls.
- Requires candidate and negative-control captures to have identical capture ID sets.
- Writes review-only action contracts, input SHA-256 provenance, and integrity-checked release artifacts.
- Reports zero automated execution and never claims gameplay verification.

## Run

Use the original raw `LYCOLES_V87_EVENT` lines from two separate capture sessions:

```powershell
py tools/evidence_release_v90.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v90
```

For other Roblox games, change the place ID and provide that game's v87 event logs.

Outputs:

- `build/release-v90/review-v90.json`
- `build/release-v90/contracts-for-review-v90.json`
- `build/release-v90/manifest-v90.json`

## Test

```powershell
py -m unittest discover -s tests -p test_evidence_release_v90.py -v
```

GitHub Actions tests the same suite across Python 3.10, 3.11, 3.12, and 3.13. Running or passing offline tests does not verify the generated code in Roblox. A review candidate requires a separate, supported and authorized execution implementation before it can become an actual action.
