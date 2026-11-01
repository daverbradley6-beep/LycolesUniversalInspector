# Lycoles v94 — Authorized Studio Action Compiler

Version 94 adds a real Luau code-generation backend for Roblox experiences you own or are authorized to develop. Unlike the read-only v92 diagnostic GUI, it generates client buttons and server-validated action handlers. It is not an executor script and cannot be dropped into an arbitrary third-party experience.

## Compile

```powershell
py tools/authorized_action_compiler_v94.py --spec examples/v94-studio-actions.json --output build/release-v94
```

The output contains `LycolesActions.server.lua`, `LycolesActions.client.lua`, `actions-v94.json`, and `manifest-v94.json`. Install the server script in `ServerScriptService` and the client script in `StarterPlayer/StarterPlayerScripts` in Roblox Studio for your own experience. The sample place ID and stat/part names are illustrative: replace them with your own game's real place ID and objects.

Supported action types: `increment_stat` (existing IntValue in player leaderstats), `set_attribute` (player attribute), and `teleport_to_part` (existing BasePart). Each action has a server-enforced cooldown and an allowlisted handler; unknown action IDs and arbitrary client arguments are rejected. The generated server owns state changes; clients can only request a named action.

## Test

```powershell
py -m unittest discover -s tests -p test_authorized_action_compiler_v94.py -v
```

A GitHub Actions workflow runs these tests and compiles the example spec. This verifies compiler behavior offline, not in-game functionality. The generated actions must be validated in an authorized Roblox Studio test environment before production use. This compiler does not generate anti-ban bypasses, exploit remote calls, or game-specific actions from passive observations alone.
