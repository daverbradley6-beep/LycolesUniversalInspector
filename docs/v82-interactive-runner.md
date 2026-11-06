# v82 — GUI contract availability testing

v82 generates a visible, place-guarded Roblox panel for manually approved GUI contracts. The panel resolves each exact GUI path and checks that the target and its ancestors are available. It deliberately does **not** call `GuiButton:Activate()`: Roblox exposes the `Activated` event but no public method that safely simulates a user activation. Each test therefore emits a structured `LYCOLES_V82_RESULT` with `requested: false` and an explicit unsupported-activation reason.

## Generate

```powershell
py tools/interactive_runner_v82.py --place-id 85896571713843 --contracts approved.json --output build/release-v82
py -m unittest discover -s tests -p "test_interactive_runner_v82.py" -v
```

Run `build/release-v82/interactive-runner-v82.luau` in the matching Roblox place and use the panel to diagnose missing, hidden, disabled, or stale GUI paths. Perform real interactions through the game's normal UI and use the later passive recorder workflow when before/after evidence is required.

## Limitations

- Only explicitly approved GUI button contracts are accepted. No keyboard injection, remote invocation, bypass, or automatic action loop is generated.
- v82 is an availability and contract diagnostic, not an action executor; it cannot produce successful activation evidence.
- UI paths are exact and may become stale when a dynamic GUI is rebuilt.
- Python regression tests validate generated source contracts, not Roblox runtime behavior.
