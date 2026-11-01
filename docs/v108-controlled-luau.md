# v108 controlled Luau execution

v108 executes the actual deterministic Luau emitted by the v107 integrated pipeline inside the official Luau CLI. Roblox services and instances are strict local stubs built from a bounded `107.hierarchy-fixture`; no Roblox game, account, Studio project, network access, private source, or server script is used.

## Reproduce

Install the pinned official Ubuntu release. The installer limits the download to 10 MB, requires the exact four expected executables, rejects unsafe archive paths and stale targets, and verifies both the release archive SHA-256 and every executable SHA-256 before making files executable.

```bash
python tools/install_luau_v108.py --output build/luau-0.745
export LUAU_BIN="$PWD/build/luau-0.745/luau"
python -m unittest tests.test_controlled_luau_v108 -v
```

Run a plan and synthetic hierarchy directly:

```bash
python tools/controlled_luau_v108.py \
  --feature-plan build/v107/feature-plan.json \
  --hierarchy path/to/107.hierarchy-fixture.json \
  --runtime-place-id 123456 \
  --luau "$LUAU_BIN" \
  --output build/v108-controlled-execution.json
```

## Simulated Roblox boundary

The stubs implement only the APIs required by the current generated observer: service lookup, instance creation and parenting, child lookup, property reads/writes, property-change and button signals, destruction, UI value constructors, and bounded task scheduling. Unknown API members and services raise runtime errors instead of silently succeeding. Scheduled background tasks are counted but not executed, preventing the generated auto-refresh loop from running indefinitely.

The harness drives the generated refresh, text filter, auto-refresh toggle, and unload controls. It records per-feature values and failure messages, compares them with the independent v107 resolver model, and reports source, fixture, runtime archive, and runtime executable hashes. Printable Unicode instance names, labels, and string values are emitted as canonical UTF-8 byte escapes and reconstructed independently by artifact verification. Missing and explicit `nil` properties both fail closed; numeric values are compared by scalar value rather than display formatting, and integer fixtures are limited to Luau's exact IEEE-754 range.

Execution is constrained to a temporary directory with an empty inherited `PATH`, closed standard input, a wall timeout of at most five seconds, two CPU seconds, 256 MB address space, 1 MB file limit, 32 open files, a 2 MB total source limit after stub injection, and a 1 MB captured-output limit.

## Verification claims

- `luauExecuted: true` means the official Luau VM ran the instrumented generated source.
- `generatedBodyExecuted: true` means the generated place guard admitted the simulated runtime.
- `simulationPassed: true` means the runtime, plan, and fixture place identities agree; resolution agreed with the independent model; all tested GUI interactions succeeded; exactly one bounded background task was scheduled; and no unsupported stub API was used.
- `readOnly: true` and `simulatedEnvironment: true` are always retained.
- `robloxRuntimeVerified`, `liveGameVerified`, and `gameplayVerified` are always `false`.

The harness changes only the canonical place-guard line so an early return can emit a deterministic mismatch transcript; the exact generated source and instrumented source have separate SHA-256 values. Passing this harness does not prove Roblox engine behavior, current target-game structure, server authority, gameplay causality, action semantics, or live-game success.
