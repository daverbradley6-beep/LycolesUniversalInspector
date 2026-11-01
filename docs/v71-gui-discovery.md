# Lycoles v71: UI discovery and candidate generation

v70's `UI control unavailable` on the example Hatch button is expected because its path was a placeholder. v71 scans actual local `PlayerGui` TextButtons and ImageButtons, displays their names, and exports their paths for use in *candidate* contracts. It never invokes remotes or assumes an action works.

## Generate and run discovery

```powershell
py tools/gui_discovery_v71.py --place-id 85896571713843 --output build/release-v71
```

Run `build/release-v71/gui-discovery-v71.luau` in Potassium in the target game. Click **Scan** after opening the relevant in-game menu. Use **Export** and save the complete `LYCOLES_V71_GUI_BEGIN` through `LYCOLES_V71_GUI_END` console output to `gui-v71.txt`.

## Import and inspect candidates

```powershell
py tools/gui_discovery_v71.py --place-id 85896571713843 --gui-log gui-v71.txt --output build/release-v71
```

The generated `gui-candidates-v71.json` lists discovered paths and observed visibility/active states. These are not ready-to-run v70 contracts: `outcome` is deliberately null until a real, independently measurable outcome is specified.

To use v70, select a candidate, verify its path, supply an outcome with an actual leaderstat and timeout, and convert it to the `70.contracts` schema documented in `docs/v70-action-contracts.md`. The client may render controls dynamically or use nonstandard click handling, so activation and server-side effects remain game-specific.

## Test

```powershell
py -m unittest discover -s tests -p "test_gui_discovery_v71.py" -v
```

The script scans up to 500 local controls, excludes its own GUI, and exports one complete snapshot. It is read-only and cannot discover hidden server action signatures.
