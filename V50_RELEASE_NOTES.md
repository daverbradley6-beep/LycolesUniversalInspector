# v50 — Authorized local action compiler

This is the first v50 compiler for **executable action controls** rather than read-only evidence buttons. It accepts a strictly validated, explicit contract and generates a Luau GUI with working action handlers for: reading visible values, setting local GUI text, and toggling local GUI visibility.

The supplied Muscle Legends example contains **illustrative, unverified paths**; missing paths are reported as unavailable, not silently considered working.

Run: `powershell -ExecutionPolicy Bypass -File .\tools\run_v50.ps1`

Output: `build/authorized-actions-v50.luau`

The compiler deliberately does not synthesize arbitrary gameplay mechanics, invoke remotes, bypass game protections, or claim server-side outcomes. Actual gameplay function generation requires explicit authorized interfaces and live outcome tests.
