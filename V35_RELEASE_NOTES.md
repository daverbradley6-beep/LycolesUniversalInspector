# Lycoles v35 — Inspection evidence bridge

## What changed

The new `tools/inspection_bridge_v35.py` links v32 source-feature hypotheses to explicitly supplied, client-visible Roblox object records. It also accepts an optional v34 lexical corroboration report.

The bridge:
- validates numeric `placeId` and nonempty `scanId`;
- normalizes a bounded `objects` / `instances` list with `path`, `name`, and optional `className`;
- distinguishes exact-path matches, partial matches, unresolved paths, and no dependencies;
- treats name-only matches as hints, not proof of object identity;
- reports missing dependencies and ambiguous names;
- produces v33-compatible **unreviewed** diagnostic proposals for exact observed paths;
- never executes third-party scripts or calls Roblox remotes.

## Windows usage

Run from the latest repository root after putting readable source scripts in `examples`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v35.ps1 -Inspection examples\v35_inspection_format.json
```

**Important:** The example inspection file is synthetic and not a real Muscle Legends scan. Replace it with a compatible export containing actual observed paths and the correct game place ID and scan ID.

Output includes `build/inspection-bridge-v35.json` and `build/inspection-proposals-v35.json`. All proposals have `reviewed:false`. After manually validating paths and actions, reviewed v33 specifications can be used with the existing diagnostic GUI generator.

## Test commands

```powershell
py -m unittest discover -s tests -p "test_v35*.py"
py -m unittest discover -s tests -p "test_v3*.py"
```

## Limitations

This is not a universal gameplay script generator. The bridge expects a normalized inspection format, not arbitrary raw multipart inspector reports. An exact object path in an inspection does not establish that a feature works or that the server accepts an action. The v35 local prototype passed 16 regression tests; the committed repository test suite requires a fresh execution. The in-game inspector remains v30.0.0.
