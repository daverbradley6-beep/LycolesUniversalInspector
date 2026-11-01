# Lycoles v91 — Temporal attribution and overlap quarantine

v91 analyses raw v87 keyboard/GUI event logs, quarantines observations where the same stat transition appears in overlapping observation windows, and reruns v90's strict cross-capture negative-control validation on the remaining evidence.

## Why

In the Bubble Gum Simulator INFINITY second capture, the stat transition from 26 to 27 was associated with W, A and E during overlapping observation windows. v90 correctly withheld a review candidate because the W control was contaminated. v91 does not guess which key caused the transition: it quarantines every event sharing that transition in overlapping windows, then checks the remaining observations.

## Usage

```powershell
py tools/temporal_attribution_v91.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v91
```

Output files: `review-v91.json`, `contracts-for-review-v91.json`, `manifest-v91.json`.

## Tests

```powershell
py -m unittest discover -s tests -p test_temporal_attribution_v91.py -v
py -m unittest discover -s tests -p test_evidence_release_v90.py -v
```

The release includes overlap diagnostics, excluded-event counts, and SHA-256 output hashes. Missing or invalid timing results in quarantine rather than inferred causality. All generated contracts remain disabled and unapproved. No automatic gameplay input, remotes, or anti-ban bypasses are implemented. Passing offline tests does not establish Roblox in-game verification.
