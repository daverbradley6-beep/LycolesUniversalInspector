# v82 — Interactive GUI action testing

v82 adds a visible local Roblox test panel for manually approved GUI action contracts. Each click requests a single local GUI button activation, snapshots leaderstats before and 1.5 seconds after, and prints `LYCOLES_V82_RESULT`. The result is **not** proof of causality or gameplay success.

## Generate

```powershell
py tools/interactive_runner_v82.py --place-id 85896571713843 --contracts approved.json --output build/release-v82
py -m unittest discover -s tests -p "test_interactive_runner_v82.py" -v
```

Run `build/release-v82/interactive-runner-v82.luau` in the Roblox client, then click **Test hatch**. The panel reports activation errors, missing or hidden controls, and observed leaderstat changes. Copy full `LYCOLES_V82_RESULT` console lines to review.

## Limitations

- Only explicitly approved GUI button contracts are supported. No keyboard injection, remotes, bypasses or automatic action loops.
- `GuiButton:Activate()` availability and effects depend on the Roblox runtime and the game's implementation.
- UI paths are exact and may become stale after UI changes. The target and ancestors must be visible and enabled.
- Python regression tests do not prove in-game activation.
