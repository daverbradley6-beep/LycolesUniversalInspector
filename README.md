# Lycoles Universal Inspector

Current inspector release: **v30.0.0**

Current integrated offline pipeline: **v106**

The repository has two version tracks. `LycolesUniversalInspector.lua` and the deterministic multipart release builder use the v30 release line. The newer v100–v106 tools are staged, independently tested inspection-to-client-observer components; v106 does not change the inspector's v30 wire version.

## Current capabilities

- Read-only inspection of bounded, client-visible Roblox instance metadata across replicated services, the local player, character, GUI, lighting, teams, sound, and workspace.
- Multipart JSON upload with acknowledgement, retry, scan identity, object accounting, and a separately deployed Cloudflare Worker integrity endpoint.
- Passive observation of normal user interactions and bounded before/after client-state evidence. Observation never proves causality or server authority.
- Deterministic offline compilation of complete scans into capability plans, workflow evidence, reviewed read-only client actions, manifests, and reproducible release archives.
- v106 normalization, evidence-gated feature planning, generated read-only Luau observer controls, quality/diagnostic reports, SHA-256 manifests, and independent artifact verification.

## Validate locally

```sh
python3 -B -m unittest discover -s tests -v
npm ci --ignore-scripts
npm test
```

The Python tools currently use only the standard library. The Node suite exercises the Cloudflare Worker receiver contract and parses checked-in plus representative generated Luau with a WebAssembly tree-sitter grammar. Lifecycle scripts stay disabled because native bindings are unnecessary for the WASM validator.

## Build from inspector scan parts

```sh
python3 tools/build_release.py ./scan-parts --output ./build
```

The builder rejects incomplete or inconsistent multipart input and keeps executable output limited to explicitly reviewed, supported, client-local read operations. See `CHANGELOG.md` for v30 provenance and per-feature verification details.

## Run the v106 integrated observer pipeline

```sh
python3 tools/integrated_pipeline_v106.py --inspection inspection.json --place-id 85896571713843 --output build/v106
python3 tools/integrated_pipeline_v106.py --output build/v106 --verify-only
```

See `docs/v106-integrated-pipeline.md` for artifacts, guarantees, and limitations.

## Inspector installation

1. Run `LycolesUniversalInspector.lua` in the supported client environment.
2. Keep the receiver endpoint in the local `LycolesInspectorReceiver.txt` configuration file; never commit receiver secrets.
3. Run a scan, confirm required-root coverage and object accounting, then verify multipart integrity through the receiver before compiling the report.

## Safety and interpretation limits

- The inspector does not read script source, private text input, chat, or arbitrary remote payloads.
- Generated observer controls do not invoke remotes, bypass security, or claim server-authoritative gameplay behavior.
- Client-visible names, values, paths, and temporal changes are evidence for review, not proof of mechanics, authorization, causality, or anti-cheat compatibility.
- Generated Luau has source-level regression coverage but still requires controlled Roblox runtime validation.
- The Cloudflare Worker must be configured and deployed separately; a repository commit does not deploy receiver changes.

## Earlier client milestones

v4.2 introduced bounded concurrent uploads, adaptive scan yielding, cached sibling context, and scan timing diagnostics. v4.3 added scan-local collision suffixes and reduced repeated sibling metadata. These behaviors are retained in the current inspector and are historical milestones, not the current release number.


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


## v15 reviewed action contracts

The build pipeline now optionally accepts a reviewed contract file: `python3 tools/build_release.py scan-parts --output build --contracts reviewed-contracts.json`. The contract schema requires `schemaVersion: "15.0"`, a matching `placeId`, and an array of `contracts` with discovered feature names, `reviewed: true`, and a supported read-only client action (`read_leaderstats`, `list_player_gui`, `list_proximity_prompts`). Contracts are validated and bundled, not executed. Unsupported operations are rejected. This is an incremental step toward reliable implementations, not automatic arbitrary gameplay scripting.


## v16 — Baseline plus dynamic observation fusion

The release builder can now combine a verified complete baseline scan with up to 64 complete dynamic-observation scans for the same Roblox Place ID. Example: `python3 tools/build_release.py ./baseline-parts --observation ./delta1-parts --observation ./delta2-parts --output ./build`. The new `tools/merge_observations.py` validates scan identity, rejects duplicate scans and mismatched places, merges per-feature evidence counters and records overlay provenance in the capability plan. Dynamic observations never replace the baseline object inventory or establish executable gameplay contracts. Supply each scan's complete multipart JSON files in its own folder.


## v17 — Executable reviewed client actions

A release built with `--contracts reviewed-contracts.json` now also contains `LycolesClientActions.lua`, generated by `tools/generate_client_actions.py`. The module implements three real read-only client operations: `read_leaderstats()`, `list_player_gui()`, and `list_proximity_prompts()`. Functions are exported in a returned Lua table and guarded by Roblox Place ID. They are not injected into the GUI and have not been tested in a live Roblox client. This is the first bounded executable implementation generation stage, not arbitrary-game gameplay automation.


## v18 — Working GUI wiring for reviewed actions

The offline release builder now generates `LycolesReviewedActionsGUI.lua` when `--contracts` contains at least one reviewed read-only action. Each button calls a real generated Lua function and displays its result or error; there are no placeholder controls. The existing diagnostic utility remains separate. Run `python3 tools/build_release.py ./baseline-parts --contracts ./reviewed-contracts.json --output ./build`. Only reviewed client diagnostics are supported; no game-specific server automation is generated or live-verified.


## v19 — Evidence-driven client action proposals

The offline release pipeline now writes `action-proposals.json` for every complete scan. `tools/propose_actions.py` derives bounded, generic read-only action candidates from observed class counts (replicated values, UI elements, proximity prompts). Each proposal includes evidence classes and review instructions, and is always `reviewed: false`. To generate executable Lua, independently create a reviewed contract document with the supported v15 schema and run the builder with `--contracts`. Feature associations are provisional, not gameplay implementation evidence. The inspector itself still uploads scans; this change does not make the receiver automatically build scripts.


## v20 — Interaction sequence reconstruction

The offline pipeline now retains up to 2,000 observed client interaction records in the capability plan and writes `observed-workflows.json` in every release. `tools/compile_interaction_sequences.py` groups events only when they share an observed transaction identifier, retains bounded before/after state evidence, records step order and keeps unlinked events separate. This can represent multi-step interactions such as opening a rebirth menu and confirming it. No remote calls are inferred or executed. All generated workflow specifications remain non-executable pending review and live verification. This release does not change receiver indexing or add automatic upload-to-build execution.


## v21 — Manual runtime verification

Release builds now include `manual-verification-plan.json`. When observed workflows include valid `leaderstats.<name>` state changes, builds also include `LycolesManualVerification.lua`, exposing `capture_before()` and `compare_after()` for manual, read-only client state comparisons. The harness does not trigger game actions, and state changes do not prove server-side causality. This is an offline release-builder feature, not a new inspector UI feature.


## v22 — Runtime feedback ingestion

The offline release builder accepts an optional `--feedback path/to/report.json` flag. `tools/evaluate_runtime_feedback.py` validates a schema v22 report against the generated `manual-verification-plan.json`, checks Place ID and feature/transaction identity, rejects duplicate checks and unexpected state keys, and classifies each submission as `client-change-observed`, `no-client-change` or `incomplete-observation`. The resulting `runtime-feedback.json` is packaged with the release. This feedback never automatically approves gameplay automation or establishes server authority. Reports are supplied manually; the inspector does not automatically upload verification results.


## v23 — Export verification observations as JSON

Generated `LycolesManualVerification.lua` now provides `capture_all_before()` and `export_report()`. The first captures replicated leaderstats. After the tester performs a game action manually, the second returns a schema v22 JSON report accepted by the existing `--feedback` ingestion stage. Export requires explicit baseline capture. Save the returned JSON as a report file for the offline builder. Report transfer and gameplay action execution remain manual.


## v28 — Six reviewed client operations and review-to-code workflow

The offline build now proposes six bounded read-only client operations from complete inspection evidence. The supported operations are `read_leaderstats`, `list_player_gui`, `list_proximity_prompts`, `list_visible_gui_buttons`, `read_local_player_attributes`, and `inspect_local_character`. These functions are not game-specific gameplay automation and are not generated until a corresponding reviewed contract is supplied.

Build a release and inspect the unapproved `review-contracts-template.json`:

```sh
python3 tools/build_release.py ./scan-parts --output ./build
```

The template uses the v15 reviewed-contract schema. Remove irrelevant entries, confirm each feature association and explicitly set `reviewed: true` for actions you have reviewed. Then build:

```sh
python3 tools/build_release.py ./scan-parts --contracts ./reviewed-contracts.json --output ./build
python3 -m unittest discover -s tests -v
```

The reviewed build includes `LycolesClientActions.lua` and `LycolesReviewedActionsGUI.lua`, with structurally validated button wiring. Generated output is not live-tested in Roblox; source inspection and class counts do not prove server-side gameplay behaviour. The GitHub repository and loadstring do not automatically generate scripts in-game.


## v29 — Per-action audit evaluation and feature coverage

Generated reviewed-actions GUIs can export bounded client execution audit JSON. The offline builder can now evaluate that audit against explicitly reviewed contracts:

```sh
python3 tools/build_release.py ./scan-parts --contracts ./reviewed-contracts.json --audit ./client-action-audit.json --output ./build
```

The release includes `action-audit-evaluation.json` when an audit is provided, and `feature-coverage.json` for every complete scan. The evaluator distinguishes client function returns, client errors, and untested operations; it rejects unknown actions and mismatched Place IDs. No reported client result establishes gameplay automation or server authority. For standalone use:

```sh
python3 tools/evaluate_action_audit.py reviewed-validated-contracts.json client-action-audit.json --output build/action-audit-evaluation.json
python3 tools/report_feature_coverage.py build/capability-plan.json build/implementation-backlog.json --output build/feature-coverage.json
```

The standalone audit evaluator expects the **validated** v15 contract document, not the unapproved review template.
