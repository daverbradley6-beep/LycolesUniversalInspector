# v76 — passive keyboard and GUI evidence

## Why

In Bubble Gum Simulator INFINITY (place `85896571713843`), v75 recorded mouse activation of `LootPoolViewer/Keybinds/1/Button` and an increase in `🥚 Hatches`, but pressing **E** produced no v75 event. v76 records both keyboard and GUI activations.

## Generate

```powershell
py tools/input_evidence_v76.py --place-id 85896571713843 --output build/release-v76
```

Run `build/release-v76/input-recorder-v76.luau` in Potassium. Press **E** in the game, then click the hatch button. Look for `LYCOLES_V76_EVENT` records with `kind: "keyboard"` and `kind: "gui"`. Each includes before/after leaderstats, input details, and a capture ID. **Refresh GUI** reattaches button listeners when the game creates new menus. The keyboard listener remains active across refreshes.

## Analyze

Copy complete `LYCOLES_V76_EVENT` lines to `events-v76.txt`:

```powershell
py tools/input_evidence_v76.py --place-id 85896571713843 --event-log events-v76.txt --output build/release-v76
```

Read `build/release-v76/input-summary-v76.json`. Inputs are grouped by key plus `gameProcessed`, or by unique GUI path. A single consistent leaderstat change across two or more observations is reported as a **hypothesis**, not a proven mapping.

## Tests

```powershell
py -m py_compile tools/input_evidence_v76.py
py -m unittest discover -s tests -p "test_input_evidence_v76.py" -v
```

## Limits

- This is passive observation, not keyboard simulation or automated input.
- `gameProcessed` describes how Roblox classified the input; it does not identify the game's handler.
- Keyboard and GUI events within 0.25 seconds are cross-referenced by `linkedKeyboardIndex`, but may still describe the same action; the analyzer does not merge them or infer causality.
- Only leaderstats are observed. An unchanged stat does not mean no gameplay action occurred.
- GUI listeners require refreshing when new controls appear.
- Textbox-focused input is intentionally excluded.
- No game remotes, exploit bypasses, or automatic script execution are included.
