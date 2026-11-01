# Lycoles v73 — v72 GUI evidence to executable local contracts

v73 connects v72 candidate catalogs to a local GUI action runner. The compiler **does not infer outcomes**, invoke remotes, or verify action contracts simply because a control exists.

## Workflow

First collect v72 GUI evidence and generate `build/release-v72/gui-candidates-v72.json`. Open that file and find a candidate ID with a relevant local button. Edit a copy of `examples/v73-outcomes.json` to supply an independently measurable leaderstat outcome for each selected candidate. The example intentionally starts with **zero** outcome mappings, because the correct stat and button cannot be assumed across games.

Example outcome entry (only after verifying the stat name):

```json
"ui_123": {
  "type": "leaderstat",
  "stat": "Hatches",
  "operator": "increased",
  "target": null,
  "timeoutSeconds": 5
}
```

Then run:

```powershell
py tools/contract_pipeline_v73.py --candidates build/release-v72/gui-candidates-v72.json --outcomes examples/v73-outcomes.json --place-id 85896571713843 --output build/release-v73
```

With at least one valid outcome mapping, the compiler produces `build/release-v73/contract-runner-v73.luau` and `contracts-v73.json`. Without any mappings, it writes the contract report only and does not produce a runner.

## Improvements

- Resolves v72 `uniquePath` metadata using name, class and sibling ordinal instead of ambiguous `FindFirstChild` paths
- Rejects ambiguous paths when ordinal metadata is absent
- Validates outcome operators, stat names, timeout ranges and place IDs
- Checks ancestor visibility and button active state before activation
- Executes only when the user clicks a generated button
- Reports observed stat changes or specific errors
- Retains source-completeness provenance and explicitly marks action verification as false

## Tests

```powershell
py -m unittest discover -s tests -p "test_contract_pipeline_v73.py" -v
```

**Limitations:** A client-side `GuiButton:Activate()` call may not replicate a human click in all games or executors. A leaderstat change following activation does not establish unique causation. The source of a candidate can be incomplete, and sibling ordinals can change as a dynamic GUI is rebuilt. No universal gameplay action generation is claimed.
