# Lycoles Universal Inspector v53 — Live Discovery

This release responds to the first successful live v48 receipt: 16 samples, 69 historical paths, 13 consistently visible, 56 never visible, and no observed transitions. The v48 inventory was insufficient for broad feature discovery.

## Build and test

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v53.ps1
```

The runner executes the existing v52 pipeline, v53 regression tests, and generates `build/release-v53/live-discovery-v53.luau`.

Execute that generated Luau script **only in the matching Roblox place**. It performs bounded, read-only breadth-first discovery across ten supported client-visible roots, with a maximum of 2,500 instances per sample, depth eight, and 11 samples over 30 seconds. It does not call remotes, trigger gameplay actions, or bypass security mechanisms.

Save the JSON between `LYCOLES_V53_BEGIN` and `LYCOLES_V53_END` as `receipt-v53.json`.

To analyze:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v53.ps1 -DiscoveryReceipt .\receipt-v53.json
```

The output is `build/release-v53/live-discovery-analysis-v53.json`, containing each observed path, class, presence frequency, and state-transition count.

## Important limitations

The receipt is untrusted client-side evidence, not server confirmation. The script does not prove that any inferred gameplay action is possible or permitted. Inventory truncation is reported; paths are encoded with JSON-quoted name segments so instance names containing dots are not ambiguous. Observed state changes do not establish causality.

The release is an architectural advance toward game-independent inspection, not proof of automatic working scripts for arbitrary games.
