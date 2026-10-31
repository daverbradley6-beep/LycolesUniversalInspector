# Lycoles v38 — receiver batch assembly and evidence planner

v38 extends v37 with a standalone, fail-closed receiver batch assembler and source-feature diagnostic planner. The existing v36/v37 workflows are preserved.

## Capabilities
- Combine JSON responses from the connected Inspector `get_scan_parts` interface into a single bundle.
- Reject missing parts, mixed scan IDs, conflicting duplicate parts, invalid object classes, and oversized inputs.
- Preserve duplicate object paths; report indexed records separately from source-reported observation counts.
- Produce a read-only feature evidence plan from the v32 source-intelligence report.
- Never label observed paths as verified gameplay functionality.

## Usage

Save the full JSON object returned from each `get_scan_parts` batch as a separate local file, for example `batch1.json`, `batch2.json`, `batch3.json`. **The connector does not automatically write these files to the user's computer.**

```powershell
py tools/receiver_pipeline_v38.py assemble batch1.json batch2.json batch3.json --place-id 3623096087 --output receiver-bundle.json
powershell -ExecutionPolicy Bypass -File .\tools\run_v38.ps1 -ReceiverBundle .\receiver-bundle.json
```

Output: `build/receiver-summary-v38.json` and `build/feature-plan-v38.json`.

## Verification

Eleven offline unit tests were executed against a development copy of the implementation and passed. A complete GitHub-checkout regression run, a real receiver-bundle end-to-end test, and in-game functional verification have **not** been performed. The connected service's indexed data can be incomplete even when every indexed part is present.

No anti-cheat bypasses, remote manipulation, or server-side gameplay automation are provided.
