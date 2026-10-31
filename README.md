## v4.3.0 — Scan identity and payload tuning

- Distinguish objects sharing the same hierarchy path using scan-local occurrence suffixes; retain all objects instead of discarding path collisions.
- Count resolved path collisions in scan statistics.
- Reduce bounded sibling ValueBase snapshots from 20 to 8 related entries, reducing repeated JSON metadata without removing inspected objects.
- Preserve existing multipart JSON schema, acknowledgement and retry behavior.

**Receiver indexing limitation:** The deployed Cloudflare Worker/MCP index is a separate service. This client update does not change its indexing behavior or retroactively repair previous scan metadata. Detailed diagnostics already verified all 844 parts of the prior scan. No in-game benchmark has been performed for this release.

## v4.2.0 — Performance update

- Bounded concurrent upload workers (3 simultaneous requests) with per-part acknowledgement and retry.
- Per-scan cached sibling ValueBase context to avoid repeated parent enumeration.
- Adaptive scan yielding with a 12 ms processing budget rather than fixed 500-object yields.
- Slower background discovery polling (30 seconds) to reduce idle overhead.
- Per-root scan timings, scan duration and yield count in scan statistics.
- Upload completion reports elapsed upload time.
- Preserves v4.1 report JSON format and the existing Cloudflare Worker interface.

**Not included yet:** compressed report schema or true incremental full-snapshot reconstruction. Those require coordinated receiver changes. Client runtime performance has not been measured in Potassium; benchmark against v4.1 before treating this as a verified speedup.

# Lycoles Universal Inspector

Current release: **v4.1.0**  
Previous release: v4.0.0

## Release v4.1.0

This release strengthens read-only inspection metadata and scan diagnostics:

- Multi-label system classification. An object can be tagged for more than one system; tags are explicitly marked as name/path/parent inference.
- Parent and ancestor hierarchy context for cross-system dependency analysis.
- Bounded sibling ValueBase snapshots and semantic value roles (requirements, rewards, costs, multipliers, timing, quantities and stats).
- Better controller/service candidate metadata, explicitly heuristic and without reading script source.
- GUI control metadata for buttons and text boxes. Text entered into text boxes is never collected.
- Per-root coverage, per-class counts, ValueBase coverage, GUI control counts and script-candidate counts.
- Duplicate-root exclusion for LocalPlayer descendants already covered by dedicated PlayerGui and Character roots.
- A real scan-completeness calculation based on required-root success and object accounting. A scan can be complete for required client-visible roots while remaining explicitly limited to client-visible data.

## Installation

1. Run the script in the same supported client environment used for the existing Inspector.
2. Keep the receiver endpoint in the local `LycolesInspectorReceiver.txt` configuration file; never commit receiver secrets.
3. Run a scan and verify the root coverage and diagnostics fields in the uploaded report.

## Existing behaviour retained

- Multipart JSON uploads and verified acknowledgements.
- Bounded upload parts, retries and retry delays.
- Optional automatic uploads and dynamic discovery.
- Passive, opt-in manual interaction observation.
- Read-only inspection; no remote invocation, gameplay automation or script-source extraction.

## Interpretation limits

This tool inspects privacy-filtered, client-visible instances. It cannot inspect server-only state or implementation, prove server validation, establish remote argument contracts, or guarantee that client-visible values are authoritative. System tags, controller candidates and hierarchy-based relationships are evidence for further analysis, not confirmed gameplay rules.


## v8 offline capability compiler

Export all JSON parts of **one** scan into a folder, then run:

```sh
python3 tools/compile_scan.py ./scan-parts --output ./build
python3 -m unittest discover -s tests -v
```

The compiler writes `capability-plan.json` and `capability-plan.md`. It fails closed on missing parts, mixed scans, duplicate identities, incorrect object totals, or incomplete scans. It inventories candidate features automatically, but intentionally does **not** generate arbitrary server-dependent Roblox actions from passive evidence. The Cloudflare receiver in this repository must be deployed separately; the connected inspector backend may not be the same service.


## v9 deterministic Lua generation

After producing a complete `build/capability-plan.json` using the v8 compiler, run:

```sh
python3 tools/generate_script.py build/capability-plan.json --output build/generated
python3 -m unittest discover -s tests -v
```

Outputs: `LycolesGeneratedUtility.lua` and `release-manifest.json`. The generated Lua contains only safe client-side diagnostics and lists gameplay systems as unimplemented candidates. This is a working generation stage, **not** a system that can infer or implement arbitrary server-authoritative gameplay features from read-only scans.


## v10 one-command release build

Place all JSON parts for **one** scan in a directory and run:

```sh
python3 tools/build_release.py ./scan-parts --output ./build
python3 -m unittest discover -s tests -v
```

The build validates multipart integrity, compiles a capability plan, generates a place-bound Lua diagnostic utility, checks its expected structure, and writes a deterministic release ZIP plus manifest. The GitHub Actions workflow `offline-pipeline.yml` runs the tests and builds an example artifact on relevant pushes. The generator does **not** implement arbitrary gameplay automation, deploy to Roblox, or prove in-game behaviour. Do not upload sensitive scan reports to a public repository.


## v11 real inspection data compatibility

The compiler accepts numbered JSON parts from the actual inspector, including metadata-only and interaction-history-only parts, plus an optional local manifest JSON. Run `python3 tools/build_release.py scan-parts --output build`. Inspect the receiver's `/reports/READ_KEY/SCAN_ID/integrity` response and require all parts acknowledged, no duplicate object keys and exact recorded-object accounting. Receiver changes are source-only until the Cloudflare Worker is deployed. The manifest's `uploadedParts: 0` is a snapshot-time placeholder, not proof of failure or success. Client-side state corroboration is not server-side verification.


## v12 Inspector UI fix

AUTO EVIDENCE is now in a dedicated right-hand sidebar, away from the title and minimise button. The output pane is narrower so it does not cover the new controls. The sidebar shows the automatic full-rescan budget and clarifies that multipart ACKs are not the same as receiver-side integrity verification. Static UI tests run with the existing CI suite. Roblox runtime layout has not yet been visually verified.


## v13 workflow evidence compilation

Run `python3 tools/build_release.py scan-parts --output build` to produce a release ZIP containing `workflow-specs.json` alongside the capability plan, generated Lua utility and release manifest. Workflow evidence tiers distinguish observed clicks, temporal state changes and client-state corroboration. They do not establish executable server gameplay actions. This is a universal evidence-processing stage for any scanned Roblox place, not a Muscle Legends-specific implementation.


## v14 automatic implementation review

The one-command build now produces `implementation-review.md` in the release archive. It ranks discovered gameplay features by observed evidence and documents the missing validation needed for each one. The inspector title now reserves space for the minimise button; the AUTO EVIDENCE control is placed below the interaction toggle with separate sidebar labels. Run `python3 -m unittest discover -s tests -v` to validate the offline pipeline. This is an evidence-driven development report, not executable server gameplay automation.
