# Lycoles Universal Inspector v61 — Live action trace collector

v61 closes a key integration gap: the v60 replay engine can now consume traces exported by a generated client-side recorder rather than relying exclusively on hand-written test data.

## Included

- `tools/live_trace_collector_v61.py` generates a place-locked Luau GUI from an explicitly approved v58 action contract.
- Uses standard Roblox Tool activation, reads a numeric `leaderstats` metric before and after each action, records timestamps, and checks a configured expected delta.
- Provides stop control, bounded attempts, cooldowns, per-attempt feedback, JSON trace export in the GUI, and a 10,000-event cap.
- Trace schema is `60.trace`, compatible with `tools/verification_replay_v60.py`.
- Adds eight offline unit tests, a consolidated v61 PowerShell runner, and CI test integration.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v61.ps1 -ActionSpec .\approved-actions-v58.json
```

The generated recorder is `build/release-v61/live-trace-collector-v61.luau`. Run it only in an authorized test place. Export the JSON from its GUI, save as `action-trace-v60.json`, then use the v60 replay command with the corresponding discovery receipt and approved contract.

## Important limitations

- This records **client-visible correlation**, not proof that an action caused a server-authoritative result.
- Does not intercept remote traffic, invoke arbitrary remotes, bypass anti-cheat, or discover secret game mechanics.
- Requires an explicitly approved action contract and currently supports Tool activation only.
- The source and tests have been uploaded, but full Python regression and live Roblox execution were not independently run in this environment.
