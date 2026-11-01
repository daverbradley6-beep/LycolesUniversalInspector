# Lycoles v95 — Secure Studio Compiler

Version 95 extends the v94 Roblox Studio action compiler with **deny-by-default user authorization**. It generates two scripts for Roblox experiences that you own or are explicitly authorized to develop: a client GUI and a server-side allowlisted action handler. The server checks the requesting player's Roblox UserId before executing any action. The client also hides its GUI from unauthorized users, but the server-side check is authoritative.

## Generate

Edit `examples/v95-authorized-studio-actions.json` with your actual Roblox place ID, your Roblox numeric UserId(s), and the names of existing game objects. The included numeric IDs and place ID are placeholders.

```powershell
py tools/secure_action_compiler_v95.py --spec examples/v95-authorized-studio-actions.json --output build/release-v95
```

The tool generates `LycolesActionsV95.server.lua`, `LycolesActionsV95.client.lua`, `actions-v95.json`, and `manifest-v95.json`. It also runs a reproducibility/integrity audit automatically.

Install the server script in `ServerScriptService` and the client script in `StarterPlayer/StarterPlayerScripts` using Roblox Studio in an experience you control.

## Audit only

```powershell
py tools/secure_action_compiler_v95.py --output build/release-v95 --audit-only
```

## Tests

```powershell
py -m unittest discover -s tests -p test_secure_action_compiler_v95.py -v
py -m unittest discover -s tests -p test_authorized_action_compiler_v94.py -v
```

GitHub Actions runs both suites and the compile/audit smoke test on Python 3.10–3.13. Offline tests and integrity audits do not establish in-game correctness. v95 supports the three v94 action types and does not automatically derive executable gameplay actions from observations of unrelated games. It does not provide executor scripts, stealth bypasses, or unauthorized remote invocation.
