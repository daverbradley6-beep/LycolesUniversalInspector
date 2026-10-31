# Lycoles v37 — receiver-indexed observation bridge

This update adds an **offline, read-only** alternative to v36's full-snapshot importer.

## New components
- `tools/receiver_adapter_v37.py`: validates part indices, scan identity, object classes, preserves observation order and duplicate paths.
- `tools/match_receiver_features_v37.py`: exact source-path evidence matching with collision counts and missing paths.
- `tests/test_v37_receiver.py`: seven regression cases.
- `tools/run_v37.ps1`: regression tests, feature analysis, receiver normalization and matching.

## Input
Provide a JSON object containing `scanId`, positive integer `placeId`, `expectedParts` and `parts`. Each part has `partIndex` (1-based) and `objects` list. The receiver service's `get_scan_parts` results can be assembled into this format. **This release does not automatically download the service data.** Example:

```json
{
  "scanId": "example-scan",
  "placeId": 3623096087,
  "expectedParts": 2,
  "parts": [
    {"partIndex": 1, "scanStats": {"recorded": 1500}, "objects": []},
    {"partIndex": 2, "objects": [{"path": "Workspace.Example", "class": "Part"}]}
  ]
}
```

## Run
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v37.ps1 -ReceiverBundle .\receiver-bundle.json
```

The report explicitly distinguishes indexed record count from source-reported observation count, and **never** marks dynamic observation coverage, runtime behavior or server-side outcomes as verified. It does not produce gameplay automation or bypass anti-cheat. The original v36 full-snapshot workflow remains unchanged.
