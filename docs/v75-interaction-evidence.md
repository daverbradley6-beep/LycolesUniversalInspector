# Lycoles v75 — passive interaction evidence and outcome proposals

v75 observes player-initiated GUI activations and records leaderstats before and after a short delay. It never clicks buttons automatically and does not invoke game remotes. Evidence is used to propose **unverified** v73 outcome mappings.

## Generate and run

```powershell
py tools/interaction_evidence_v75.py --place-id 85896571713843 --output build/release-v75
```

Execute `build/release-v75/interaction-recorder-v75.luau` in Potassium while in Bubble Gum Simulator INFINITY. Interact normally with the target in-game buttons several times. Use **Refresh controls** if the game opens a menu after the recorder starts. Copy the `LYCOLES_V75_EVENT` console lines into `events-v75.txt`. Each event includes its capture ID, the uniquely identified button and leaderstats snapshots.

## Correlate with v74

After generating `build/release-v74/gui-candidates-v74.json`:

```powershell
py tools/interaction_evidence_v75.py --place-id 85896571713843 --event-log events-v75.txt --candidates build/release-v74/gui-candidates-v74.json --output build/release-v75
```

Outputs:

- `proposals-v75.json`: matched controls, evidence counts, outcome proposals and rejection diagnostics
- `review-outcomes-v75.json`: v73-compatible mapping template, **not automatically verified**
- `interaction-recorder-v75.luau`: passive recorder

Review and correct `review-outcomes-v75.json` before supplying it to v73:

```powershell
py tools/contract_pipeline_v73.py --candidates build/release-v74/gui-candidates-v74.json --outcomes build/release-v75/review-outcomes-v75.json --place-id 85896571713843 --output build/release-v73
```

## Tests

```powershell
py -m py_compile tools/interaction_evidence_v75.py
py -m unittest discover -s tests -p "test_interaction_evidence_v75.py" -v
```

## Verification limits

- Leaderstats are only a subset of game state. A click may change something else or may not change any stat.
- The recorder samples before user input and after an observation delay. Other simultaneous gameplay can change the same stat; repeated observations do not prove causation.
- Some controls may use input handlers other than `Activated`; they will not be captured.
- Dynamic GUI rebuilds may change sibling ordinals, and the v74 scan and v75 observation must refer to matching controls.
- Only controls with one unambiguous matching candidate and one consistent measurable stat are proposed.
- **No universal automatic script generation or anti-ban bypass is claimed.**
