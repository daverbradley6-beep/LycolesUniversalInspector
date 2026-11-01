# Lycoles v70 — explicit action contracts

v70 introduces a **contract-based compiler**. It does not infer callable actions from passive discovery. You supply a local Roblox GUI control path and a measurable leaderstat outcome. The compiler validates the contract and emits a movable/minimisable GUI. Each generated action requires a user click; it reports observed success only after the stat condition changes within the timeout.

## Generate

```powershell
py tools/action_contract_compiler_v70.py --contracts examples/v70-contract-example.json --place-id 85896571713843 --output build/release-v70
```

Run `build/release-v70/contract-runner-v70.luau` in the target game. The example paths are **placeholders** and will not work until replaced with real paths confirmed from the game. In this version paths are relative to `Players.LocalPlayer.PlayerGui`.

## Contract format

- `schemaVersion`: `70.contracts`
- `placeId`: Roblox Place ID, checked during generation and at runtime
- `contracts`: 1–60 explicit actions, each with a unique identifier
- `action.type`: only `local_gui_activate`
- `action.className`: `TextButton` or `ImageButton`
- `action.path`: exact child names beneath PlayerGui
- `outcome.type`: only `leaderstat`
- `outcome.operator`: `changed`, `increased`, `decreased`, or `equals`
- `outcome.target`: string for `equals`; otherwise null
- `outcome.timeoutSeconds`: 0.5–30

The script checks that the stat exists before attempting the action, activates only the explicitly named UI control, and waits for the observable condition. A timeout is a failed verification, not evidence that a remote call is broken. A positive stat change is evidence of the observed condition, not proof of unique causation.

## Test

```powershell
py -m py_compile tools/action_contract_compiler_v70.py
py -m unittest discover -s tests -p "test_action_contract_compiler_v70.py" -v
```

The CI workflow is `.github/workflows/v70-contracts.yml`. Static Python tests do not substitute for Roblox runtime testing. This release does not implement remote invocation, anti-ban bypass, server authority, or universal action inference.
