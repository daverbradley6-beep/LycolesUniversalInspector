# Runtime test instructions (Milestone 3)

Target place ID: `292439477`

## 1) Load inspector
- Execute `LycolesUniversalInspector.lua` in executor.
- Confirm UI opens and version shows v30.6.62.

## 2) Start targeted capture
- Click `TARGET: ...` to choose preset.
- Click `CAPTURE: START`.
- Perform normal gameplay for 2-4 minutes.
- Click `CAPTURE: STOP`.

## 3) Export targeted evidence
- Use `Copy` to copy live observation export JSON.
- Confirm `targetedCaptureSession` exists and includes requestProgress/samples.

## 4) Validate movement overlay
- Use generated `MovementTelemetryOverlay.lua` module.
- Instantiate module and call `Start()`.
- Confirm speed/position/state update, respawn handling, and clean `Stop()` cleanup.

## 5) Record results
- Mark stage 6 runtime-tested only if executed successfully in Roblox.
- Mark stage 7 gameplay-verified only with observed intended outcomes.
