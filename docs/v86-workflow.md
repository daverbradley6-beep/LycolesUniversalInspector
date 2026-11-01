# v86 — Single-command pipeline

v86 coordinates the existing v82 GUI tester generator, v83 result analyzer, v85 evidence-to-contract review builder, and v84 release compiler. It reports missing prerequisites before starting and stops on the first failed stage.

Run from the repository root:

```powershell
py tools/workflow_v86.py --place-id 85896571713843 --contracts approved.json --result-log results-v82.txt --output build/release-v86
```

To inspect the command plan without running the pipeline:

```powershell
py tools/workflow_v86.py --place-id 85896571713843 --contracts approved.json --result-log results-v82.txt --dry-run
```

**Prerequisite:** save actual v82 console lines beginning with `LYCOLES_V82_RESULT` to `results-v82.txt`. An unsuccessful GUI activation is evidence of a failed request, not successful gameplay.

Outputs: `v82/interactive-runner-v82.luau`, `v83/action-results-v83.json`, `v85/contracts-for-review-v85.json`, and `v84/interactive-runner-v84.luau`.

This pipeline does not inject user input, call game remotes, or verify gameplay. The invalid `GuiButton:Activate()` method was removed from the older generators; actual interaction must occur through the game's normal UI. The generated scripts are manual observation tools, not universal automatic gameplay scripts.
