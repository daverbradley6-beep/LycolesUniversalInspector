# Lycoles v72 — paginated universal GUI discovery

v72 fixes the 500-control cap and duplicate-path ambiguity observed in the Bubble Gum Simulator INFINITY v71 export.

## Generate

```powershell
py tools/gui_discovery_v72.py --place-id 85896571713843 --output build/release-v72
```

Execute `build/release-v72/gui-discovery-v72.luau` in the target Roblox game. Open the relevant in-game menu, click **Scan**, then **Export all**. Copy the complete console output (beginning with `LYCOLES_V72_BEGIN` and ending with `LYCOLES_V72_END`) to `gui-v72.txt`.

## Import

```powershell
py tools/gui_discovery_v72.py --place-id 85896571713843 --gui-log gui-v72.txt --output build/release-v72
```

Outputs:

- `gui-import-v72.json`: completeness, missing record indices, missing pages, duplicate-path counts, individual controls
- `gui-candidates-v72.json`: **unverified** local GUI action candidates, without fabricated outcome contracts
- `gui-discovery-v72.luau`: read-only inspector

The importer tolerates truncated exports and marks `complete=false` while retaining recovered records. Use `--strict` to reject incomplete logs. Multiple sessions are supported; the latest complete matching-place session is preferred.

## Improvements

- Up to 20,000 controls (configurable via `--limit`) rather than the v71 cap of 500
- Search and pagination in the inspector
- Ancestor-aware effective visibility
- Duplicate-path detection
- `uniquePath` metadata with sibling ordinals to distinguish same-named objects
- Partial export recovery and explicit missing-record reports
- Conservative provenance: **zero verified actions** until actual outcomes are measured

## Test

```powershell
py -m py_compile tools/gui_discovery_v72.py
py -m unittest discover -s tests -p "test_gui_discovery_v72.py" -v
```

**Limitations:** This is a read-only discovery tool, not a gameplay automation system. `uniquePath` is evidence metadata and is not yet consumed by the v70 runner. The game may dynamically rebuild its GUI. A discovered button is not proof that activating it causes a gameplay action. Exporting thousands of records may produce large logs; console truncation is detected during import.
