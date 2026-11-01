# v51 — Automatic evidence-to-code compilation

v51 automatically converts observed local-player paths into runnable **read-only** GUI action buttons, without requiring the user to author v50 action contracts. It ranks eligible paths by observed visibility and state transitions, produces a contract and audit report, and uses the v50 action compiler to emit Luau.

Run `powershell -ExecutionPolicy Bypass -File .\tools\run_v51.ps1 -Receipt .\receipt-v48.json`.

Outputs: `build/auto-actions-v51.json`, `build/auto-actions-audit-v51.json`, and (if eligible paths exist) `build/auto-actions-v51.luau`. No output Luau is emitted if there are no eligible paths. Runtime may still report unsupported object classes or missing objects.

This does not discover or execute server gameplay actions, bypass protections, or guarantee arbitrary-game support. The receipt remains client-supplied and untrusted.
