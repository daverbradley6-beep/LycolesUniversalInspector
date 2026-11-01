# Lycoles v101 — Client inspection collection and adapter

v101 creates a **read-only observation export path for non-owned Roblox experiences**. The new `client/client_observation_collector_v101.lua` is a bounded LocalScript that scans client-visible `PlayerGui`, `Workspace` and `ReplicatedStorage` descendants, prints a JSON report and performs no gameplay actions, server requests, input automation or bypasses. Roblox Studio is not required to build the offline compiler artifacts, but executing LocalScripts in someone else's experience is not supported by the normal Roblox client and may violate game rules. No executor loader is supplied.

`tools/inspection_adapter_v101.py` normalizes JSON arrays or objects with `observations`, `objects`, `instances`, or `entries` into the v100 observation schema, rejects unsupported paths and properties, and compiles the v100 read-only GUI with an integrity audit. Unknown fields are not interpreted as capabilities.

## Offline usage

```powershell
py -m unittest discover -s tests -p test_inspection_adapter_v101.py -v
py tools/inspection_adapter_v101.py --inspection inspection.json --place-id 85896571713843 --output build/release-v101
py tools/client_observer_compiler_v100.py --output build/release-v101 --audit-only
```

An accepted input object looks like `{"path":["PlayerGui","HUD","Coins"],"property":"Text","id":"Coins"}`. The example is illustrative, not a verified game path. The adapter requires at least one valid observation. A `game.Workspace.Folder.Part` dotted path is also accepted. If the property is absent, only `Name` is observed. The resulting GUI reads properties once per second and handles missing objects.

## Boundaries and validation

This is not automatic gameplay script creation yet. The scanner does not infer server-side mechanics or executable functions, and the adapter intentionally rejects unknown paths and properties. A passing static audit does not establish that a generated script runs inside a third-party game. GitHub Actions is configured for Python 3.10–3.13; live Roblox testing is not included.
