# Lycoles v102 — Client-visible capability catalog

v102 extends the non-owned-game inspection workflow by classifying **observable object classes** rather than merely listing instance names. It identifies UI labels, buttons, text inputs, value objects, proximity prompts, click detectors, tools and ScreenGuis. These are descriptive **capabilities**, not proof that a game mechanic can be automated.

## Pipeline

1. `client/client_observation_collector_v101.lua` now includes `className` and `name` in each exported observation (in addition to its v100-compatible fields).
2. `tools/capability_catalog_v102.py` accepts the exported `observations` list, as well as `objects`, `instances`, `entries`, or a bare list.
3. It validates client-visible paths, selects a safe read-only property for each recognized class, compiles the v100 observer GUI, audits its SHA-256 manifest, and writes `capabilities-v102.json`.
4. Unknown classes, inaccessible roots, and unsupported paths are rejected and counted rather than guessed.

## Offline smoke test

```powershell
py -m unittest discover -s tests -p test_capability_catalog_v102.py -v
py tools/capability_catalog_v102.py --inspection examples/v102-client-inventory.json --place-id 85896571713843 --output build/release-v102
py tools/client_observer_compiler_v100.py --output build/release-v102 --audit-only
```

The sample inventory is **illustrative**, not verified against Bubble Gum Simulator INFINITY. The collector is a read-only LocalScript; standard Roblox clients do not permit arbitrary injection into third-party games. No exploit loader, server remote calls, or anti-cheat bypass is included. A classified `TextButton` is an observable button, **not an automatically working gameplay function**. The generated GUI requires runtime testing separately.

GitHub Actions is configured for Python 3.10–3.13, including v100, v101, and v102 tests. Offline test success does not prove compatibility with arbitrary games.
