# Lycoles v87 — passive, dynamic GUI and keyboard evidence capture

v87 replaces the broken attempt to call `GuiButton:Activate()` with a passive recorder for actual player actions. It uses the supported `GuiButton.Activated` event and `UserInputService.InputBegan` event, tracks buttons added while the recorder is running, and records leaderstat changes after an observation delay.

Generate the Luau recorder:

```powershell
py tools/passive_recorder_v87.py --place-id 85896571713843 --output build/release-v87
```

Run `build/release-v87/passive-recorder-v87.luau` in the game. Use the game's actual E key or Hatch button. Copy lines starting with `LYCOLES_V87_EVENT` into `results-v87.txt`, then analyze:

```powershell
py tools/passive_recorder_v87.py --place-id 85896571713843 --event-log results-v87.txt --output build/release-v87
```

The review file is `build/release-v87/evidence-review-v87.json`. It groups keyboard and GUI inputs, counts independent captures, and reports observed leaderstat directions. These are correlations, not proof of causality. This tool does not synthesize keypresses, click buttons, call remotes, or automatically execute gameplay actions. The recorder's GUI is excluded from discovery. Test in Roblox before treating any generated code as functional.
