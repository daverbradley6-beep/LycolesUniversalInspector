# v48 — Passive state-change correlation

The v48 observer takes 16 read-only samples over approximately 30 seconds, observing client-visible ValueBase values, GUI text, and object presence. This is intended to discover candidate state changes that static paths cannot reveal.

Run `powershell -ExecutionPolicy Bypass -File .\tools\run_v48.ps1`. Execute `build/passive-observer-v48.luau` in the matching Roblox place. Use the game normally while the sampler runs. Save the final JSON between `LYCOLES_V48_BEGIN` and `LYCOLES_V48_END` as `receipt-v48.json`. Then run `powershell -ExecutionPolicy Bypass -File .\tools\run_v48.ps1 -Receipt .\receipt-v48.json` to create `build/state-changes-v48.json`.

Important limitations: values are truncated to 120 characters, only evidence paths are observed, no actions are invoked, observations are not authenticated, and state changes alone do not establish cause, server effects, or functional gameplay automation.
