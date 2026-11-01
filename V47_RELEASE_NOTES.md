# v47 — Generated working diagnostic dashboard

v47 compiles the discovered feature families into a runnable game-specific Luau GUI. Each feature button executes a client-visible path inspection and displays the number found. The **Inspect all systems** button checks every family. The GUI can be closed and rerun without stacking duplicate instances.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v47.ps1
```

Execute `build/feature-dashboard-v47.luau` in the matching Roblox place. To collect automatic snapshots, execute `build/auto-probe-v46.luau` separately. The generated GUI contains actual functional diagnostics, **not** unverified gameplay automation. Game-specific functions still require mechanic-level evidence and server-side outcome validation.
