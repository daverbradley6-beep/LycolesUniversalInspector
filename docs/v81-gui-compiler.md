# v81 — Explicitly approved GUI contract compiler

v81 converts **manually approved** GUI action drafts into local-only Luau functions. No actions run automatically. It does not invoke game remotes or bypass security controls. It does not establish that a requested activation has the intended gameplay outcome.

Start with an action draft from v80, manually review the GUI path, assign a unique alphanumeric `id`, and set `approved: true`. For v81, `input` must be `["gui", <path>]` where path is an array of `{name,className,ordinal}` segments (or a JSON-encoded string containing that array). The final segment must be a TextButton or ImageButton.

Example contract file:

```json
{
  "placeId": 85896571713843,
  "contracts": [
    {
      "id": "hatch",
      "approved": true,
      "executionEnabled": false,
      "input": ["gui", [
        {"name": "ScreenGui", "className": "ScreenGui", "ordinal": 1},
        {"name": "HUD", "className": "Frame", "ordinal": 1},
        {"name": "LootPoolViewer", "className": "Frame", "ordinal": 1},
        {"name": "Keybinds", "className": "Frame", "ordinal": 1},
        {"name": "1", "className": "Frame", "ordinal": 1},
        {"name": "Button", "className": "ImageButton", "ordinal": 1}
      ]]
    }
  ]
}
```

```powershell
py tools/gui_contract_compiler_v81.py --place-id 85896571713843 --contracts approved.json --output build/release-v81
py -m unittest discover -s tests -p "test_gui_contract_compiler_v81.py" -v
```

The generated `approved-gui-v81.luau` defines an `actions` table but intentionally does not invoke any action. The generated functions return whether a local GUI activation was requested, **not** whether gameplay succeeded. Local GUI availability, Roblox executor compatibility, and actual outcomes must be tested in the client. This is not universal script generation.
