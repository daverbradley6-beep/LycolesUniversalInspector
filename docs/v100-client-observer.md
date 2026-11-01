# Lycoles v100 — Client-only observer compiler

This release refocuses Lycoles on *client-visible inspection of existing Roblox experiences*, without requiring game ownership or Roblox Studio. It compiles a strictly validated JSON observation report into a **read-only Luau LocalScript** with a closeable GUI. It does not automatically discover arbitrary server mechanics, bypass game protections, or perform gameplay actions.

## Generate and audit

```powershell
py -m unittest discover -s tests -p test_client_observer_compiler_v100.py -v
py tools/client_observer_compiler_v100.py --report examples/v100-client-observations.json --output build/release-v100
py tools/client_observer_compiler_v100.py --output build/release-v100 --audit-only
```

Output: `LycolesObserverV100.client.lua`, `observations-v100.json`, `manifest-v100.json`. The example uses **illustrative paths**, not verified Bubble Gum Simulator INFINITY object names. The generated script is a Roblox LocalScript; executing it in a game you do not own may require a third-party executor and may violate the game's rules. This release neither provides nor tests an executor loader.

The script looks up allowlisted roots (`PlayerGui`, `Workspace`, `ReplicatedStorage`, `Players`) and displays selected read-only properties (`Name`, `ClassName`, `Visible`, `Text`, `Value`, `Enabled`). Missing paths show `not found`; unreadable properties show `unavailable`. It refreshes once per second and stops when closed. It does not call remotes, automate input, modify game objects or attempt stealth.

The Python compiler includes input validation, deterministic output and a SHA-256 manifest audit. A GitHub Actions matrix is configured for Python 3.10–3.13. Tests have not been independently confirmed in-game. The next priority is an actual inspector-export adapter to convert verified client-visible object paths into this v100 schema, followed by runtime testing of GUI display and missing-object handling.
