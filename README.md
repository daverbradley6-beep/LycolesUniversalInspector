# Lycoles Universal Inspector

Current inspector release: **v30.5.0**

Current integrated offline pipeline: **v108**

The repository has two version tracks. `LycolesUniversalInspector.lua` and the deterministic multipart release builder use the v30 release line. The newer v100–v110 tools are staged, independently tested inspection-to-client-observer components; v109 analyzes local manifest readiness and v110 composes evidence-ranked gameplay understanding without changing the inspector's multipart wire format.

## Current capabilities

- Read-only inspection of bounded, client-visible Roblox instance metadata across replicated services, the local player, character, GUI, lighting, teams, sound, and workspace.
- A two-tab in-game interface keeps inspection controls and Generated Script status in one panel. `PRODUCE SCRIPT` records a bounded client-visible capability request and captures a complete scan for offline compilation; it does not generate or execute gameplay behavior in the target session. The Generated Script tab distinguishes request text from evidence and tracks scan identity, numbered parts, local export, receiver acknowledgements, and pending offline validation while keeping receiver integrity and gameplay unverified. Offline generation emits a place-bound `Lycoles-PLACE-generated-result.json`; schema 113 embeds validated generation readiness so `LOAD RESULT` can display generated bounded capabilities, exact target/outcome evidence, unavailable requested behavior, static-validation status, and verification limits alongside code. The loader retains display-only schema 110 compatibility, never executes imported code, and explicitly treats package authenticity and runtime/gameplay behavior as unverified.
- Multipart JSON upload with acknowledgement, retry, scan identity, object accounting, explicit local transport lifecycle status, and a separately deployed Cloudflare Worker integrity endpoint. `SAVE REPORT` exports every exact numbered part plus a matching manifest, so offline generation is not limited to the small manifest summary when upload is unavailable.
- Passive observation of normal user interactions and bounded before/after client-state evidence from leaderstats, Data, and privacy-filtered LocalPlayer numeric/boolean ValueBase candidates. v30.1 distinguishes generic temporal changes from feature-consistent observable outcome candidates; neither proves causality, server authority, or gameplay success.
- Deterministic offline compilation of complete scans into capability plans, workflow evidence, reviewed read-only client actions, manifests, reproducible release archives, and normalized source-provenance status. Generated utility UI exposes retrieval integrity and its explicit trust limits without claiming authenticity or gameplay verification.
- v109 manifest readiness analysis explains upload ambiguity, interaction evidence, outcome-candidate lower bounds, missing multipart data, and generation blockers without treating the local manifest as a full report.
- v110 composes multiple concurrent gameplay-system candidates, observed resources/actions, temporal relationships, loop candidates, objective candidates, automation opportunities, and request blockers. It deliberately reports no single genre and no verified gameplay mechanics.
- Generated utilities include a reusable **Admin Commands** section and `;` command bar for local client utilities (`fly`, `noclip`, `tp`, `goto`, `speed`, `jump`, `coords`, evidence-backed `systems`/`readiness`, `reset`, `rejoin`, `stopall`, and help/GUI controls). GUI and command controls share state and cleanup. Actual generated Luau is exercised in bounded client stubs for state changes, cleanup, respawn continuity, and place guarding; this remains simulated evidence, game restrictions may override local effects, and no server administrator privilege is implied.
- v30.5 retains bounded actionable prompt/GUI/Tool metadata, class/name/sibling-ordinal component identities, composable action surfaces, and deterministic action-to-state/GUI temporal relationships. Any observed ProximityPrompt with a resolvable scalar outcome can produce a place-bound `LycolesPromptInteractions.lua` trial ranked by requested-capability alignment and gameplay-objective usefulness; when several scalar values change together, request/context alignment deterministically selects the one bounded outcome that generated code monitors. Prompt text, enabled state, hold duration, activation distance, input keys, and anchor metadata are normalized into bounded observation snapshots; distinct snapshots expose drift rather than silently overwriting evidence. The generated UI and shared `;interaction*`/compatible `;egg*` Admin Commands select a target, move to its nearby anchor, invoke executor-provided `fireproximityprompt` only when available, observe the recorded increased/decreased/changed outcome direction, and stop after three failures. `;interactionfeedback` exports at most 100 discovery-digest-bound attempt records for offline validation by `tools/evaluate_prompt_trial_feedback.py`; the evaluator rejects unknown targets, unselected outcomes, forged directional changes, and positive verification claims. Component identities preserve literal dots and duplicate sibling names; ambiguous new state identities fail closed while legacy evidence retains a flat-path fallback. No discovered remote is invoked. Bubble Gum Simulator INFINITY's Rainbow Egg is the primary real-evidence example, but temporal correlation and imported feedback still do not prove causality, server authority, Roblox runtime success, or gameplay functionality. Auto and Multi game modes remain unavailable until the explicit live-observation blockers in `action-capabilities.json` are resolved. Controlled official-Luau execution validates wiring only in simulation.
- Observed `Tool.Activated` events now retain enabled/manual-activation/handle/drop/tooltip prerequisites, exact LocalPlayer component identity, and selected resolvable scalar outcome evidence. Offline discovery identifies activation-contract-ready candidates only when all three evidence classes are present and unambiguous. Tool generation remains deliberately unintegrated and discovery-only until a fail-closed generator, bounded equip/activation flow, feedback contract, and controlled official-Luau harness are complete; no live runtime, causality, outcome, or gameplay claim is made.

- v107 full-path class/ordinal identity, fail-closed legacy migration, generated read-only Luau observer controls, strict artifact verification, and deterministic synthetic resolver modeling.
- Versioned per-feature contracts linking canonical observation digests to observed facts, bounded inferences, runtime checks, success/failure conditions, verification status, and explicit unknowns.
- A pinned, bounded snapshot of Roblox's public Studio API dump verifies every emitted class member and supported read property, while separately listing globals outside the dump.
- v108 controlled execution runs actual generated Luau against strict bounded Roblox stubs, drives generated UI controls, and compares results with the independent resolver model without claiming live Roblox verification.
- v108 system interpretation deterministically infers interface, interaction-affordance, state, and candidate feedback-surface roles from observed v107 objects; optionally groups them through strictly shaped caller-supplied correlation references; and preserves source authenticity and causality as explicit unknowns without generating gameplay actions.
- v108 integrated bundles add system plans, expected runtime checks, optional permitted-client observation contracts, expected-versus-observed drift diagnostics, per-feature verification, explicit unsupported reporting, and exact full-bundle reconstruction while all live/gameplay/authority claims remain false.

## Validate locally

```sh
python3 tools/install_luau_v108.py --output build/luau-0.744
LUAU_BIN="$PWD/build/luau-0.744/luau" python3 -B -m unittest discover -s tests -v
npm ci --ignore-scripts
npm test
```

The Python tools currently use only the standard library. The Node suite exercises the Cloudflare Worker receiver contract and parses checked-in plus representative generated Luau with a WebAssembly tree-sitter grammar. Lifecycle scripts stay disabled because native bindings are unnecessary for the WASM validator. The optional actual-Luau layer downloads only the pinned official release and verifies both its archive and executable hashes; see `docs/v108-controlled-luau.md` for simulation limits and verification claims.

## Build from inspector scan parts

```sh
python3 tools/build_release.py ./scan-parts --output ./build
```

The builder rejects incomplete or inconsistent multipart input. Read-only operations still require reviewed supported contracts; v30.5 can additionally emit a narrowly bounded ProximityPrompt egg trial only when an exact observed prompt path has a temporal hatch/egg counter increment, and reports that trial as runtime/gameplay unverified. Complete v30.1 parts preserve validated observable outcome candidates and feature-state/GUI correlation counts in `capability-plan.json`, `workflow-specs.json`, `release-manifest.json`, and `implementation-review.md`; those correlations never establish causality, outcome verification, replayability, server authority, or automatic execution. `source-provenance.json` records whether the baseline was a direct local multipart directory or a validated receiver import. Imported part bytes are rechecked against the receiver-manifest digests before those statuses reach `capability-plan.json`, the release manifest, bundled README, or generated Features panel. See `CHANGELOG.md` for v30 provenance and per-feature verification details.

### Retrieve verified receiver parts

Receiver access requires both the HTTPS origin and read key; a scan ID alone is not a routable endpoint or credential. Diagnose known scans without downloading all parts:

```sh
export LYCOLES_RECEIVER_ORIGIN=https://receiver.example
# Set LYCOLES_READ_KEY through a secure environment or secret manager.
python3 tools/diagnose_receiver_access.py SCAN_ID [SCAN_ID ...]
```

The diagnostic never prints either value or unrelated receiver record IDs. It first probes the authenticated collection and distinguishes multipart `scans` deployments from the original pre-multipart `reports` deployment, then checks requested metadata/first-part access and whether a multipart deployment supports v12 persisted digest headers or the older v11 contract. A `legacy-single-reports` collection is not eligible for multipart v11 recovery. Add `--check-integrity` only when the Worker's potentially expensive full integrity route should be run. Long-running Agent Canvas conversations may retain their startup secret snapshot; start a fresh conversation after adding Settings secrets rather than creating duplicate secrets or transferring values through chat.

For a v12 receiver, run:

```sh
python3 tools/fetch_receiver_scan.py https://receiver.example receiverscanid \
  --local-manifest path/to/Lycoles_PLACE.json \
  --resume ./receiver-resume --output ./scan-parts
python3 tools/build_release.py ./scan-parts --output ./build
```

`--local-manifest` is optional; a v30.2 post-upload manifest lets the importer compare every retrieved part with the digest acknowledged during upload. The read key has no command-line option and is never written to imported output or resume state. Retrieval requires HTTPS, rejects redirects, reads constant-cost receiver metadata, downloads bounded numbered parts with bounded transient retries, verifies each exact response body against its receiver-stored upload digest, validates identity, uniqueness and accounting locally, runs the existing multipart compiler, and publishes the new output directory atomically. Strict-default import requires the checked-in Worker contract with `/metadata` and digest-bearing part responses; committing this source does not deploy it.

A confirmed scan stored by a v11 receiver can be imported explicitly when the diagnostic reports `v11-no-persisted-digests`:

```sh
python3 tools/fetch_receiver_scan.py https://receiver.example receiverscanid \
  --allow-legacy-v11 --output ./scan-parts
```

Legacy mode first requires the receiver `/integrity` response to report complete identity, uniqueness, and object accounting, then retrieves every part and repeats bounded identity/accounting/compiler validation locally. It records locally observed response digests but keeps `receiverStoredPayloadDigestsVerified`, response authenticity, source authenticity, local-payload equivalence, causality, runtime verification, and gameplay verification false. It is never selected automatically and does not support resume checkpoints. The stricter v12 path remains the default.

`--resume` is optional for v12 imports. It stores each successfully verified part and an atomic, metadata-bound checkpoint in a persistent directory that must not overlap `--output`. A later run revalidates checkpoint structure, metadata identity, cached byte digests, multipart identity, optional ACK digests, global accounting and compiler output before reusing cached parts. Corrupt or conflicting state fails closed; the output remains unpublished. Resume files contain report data and must not be committed or shared casually. The checkpoint is explicitly unauthenticated, and `receiverStoredPayloadDigestsRevalidatedThisRun` is false when any cached part is reused.

`receiverStoredPayloadDigestsVerified` records receiver-digest checks performed during the current or checkpointed retrieval. `receiverAcknowledgementDigestEquivalent` additionally means all supplied local ACK digest records match. These flags and local resume checks do not independently authenticate the checkpoint, local manifest, or receiver response; prove equivalence to locally computed original bytes; or establish gameplay causality, server authority, replayability, or action success. The release builder remains offline and does not fetch network data itself.

Before building a receiver-imported scan, the compiler requires the exact matching strict or legacy schema, identity/accounting agreement, complete current-part digest coverage, and byte-for-byte matches with the recorded digest kind. Strict v12 provenance additionally requires receiver-stored digest verification; legacy v11 provenance must explicitly keep that claim false. Forged positive authenticity claims, part drift, malformed resume diagnostics, and conflicting accounting block generation. The normalized artifact deliberately keeps checkpoint authentication, receiver-response authenticity, original-local-payload equivalence, source authenticity, causality, server authority, and gameplay verification false.

When only the small local manifest is available, pass that file to the same release entry point:

```sh
python3 tools/build_release.py path/to/Lycoles_PLACE.json --output build
```

The command writes `build/manifest-readiness-v109.json`, emits explicit diagnostics and feature-consistent outcome-candidate lower bounds, and intentionally exits with blocked status 2. It never creates a release ZIP or Luau utility because the manifest lacks the numbered object-bearing parts, canonical object identity, receiver integrity evidence, and a reviewed implementation contract. The standalone `tools/manifest_readiness_v109.py` CLI remains available when a successful analysis-only exit status is preferred.

## Run the v107 integrated observer pipeline

```sh
python3 tools/integrated_pipeline_v107.py --inspection inspection.json --place-id 85896571713843 --output build/v107
python3 tools/integrated_pipeline_v107.py --output build/v107 --verify-only
```

See `docs/v107-path-identity.md` for identity, provenance, artifacts, guarantees, and limitations.

## Interpret observable system candidates

```sh
python3 tools/system_interpreter_v108.py \
  --report build/v107/inspection-report.json \
  --feature-plan build/v107/feature-plan.json \
  --relationship-evidence path/to/108.relationship-evidence.json \
  --output build/v108/system-interpretation.json
```

Relationship evidence is optional, caller-supplied, and correlation-only; source authenticity remains unknown. See `docs/v108-system-interpretation.md` for schemas, canonical ordering, confidence categories, unsupported capabilities, and verification limits.

## Generate and verify a v108 integrated bundle

```sh
python3 tools/integrated_pipeline_v108.py \
  --source inspection.json \
  --place-id 85896571713843 \
  --output build/v108
python3 tools/integrated_pipeline_v108.py --output build/v108 --verify-only
```

Optional `--relationship-evidence` and `--runtime-observation` inputs add strictly validated, digest-bound evidence without changing v107 inspection compatibility or upgrading authenticity, causality, authority, runtime, or gameplay claims. Runtime checks carry exact class-qualified identity, provenance, property, and value-type contracts without inventing expected values. Supplied incomplete or drifted evidence writes a verifiable bundle with `comparisonPassed: false` and exits nonzero. See `docs/v108-runtime-contracts.md` for exact schemas, outcomes, artifact names, failure behavior, and evidence boundaries.

## Inspector installation

1. Run `LycolesUniversalInspector.lua` in the supported client environment.
2. Keep the receiver endpoint in the local `LycolesInspectorReceiver.txt` configuration file; never commit receiver secrets.
3. Run a scan, confirm required-root coverage and object accounting, then verify multipart integrity through the receiver before compiling the report.

## Safety and interpretation limits

- The inspector does not read script source, private text input, chat, or arbitrary remote payloads.
- Generated observer controls do not invoke remotes, bypass security, or claim server-authoritative gameplay behavior.
- Client-visible names, values, paths, and temporal changes are evidence for review, not proof of mechanics, authorization, causality, or anti-cheat compatibility.
- Generated Luau has source-level regression coverage; controlled execution and user-supplied results from permitted client environments remain separately labeled runtime evidence and never require target-game Studio ownership.
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

Outputs: `LycolesGeneratedUtility.lua`, standalone `LycolesAdminCommands.lua`, `gameplay-understanding.json`, `action-capabilities.json`, `generation-readiness.json`, and `release-manifest.json`; `LycolesPromptInteractions.lua` is added only when at least one observed prompt has a generation-resolvable scalar outcome. The readiness artifact recomputes emitted bounded capabilities, request-matched subsets, unavailable behavior, and discovery-only candidates from the source artifacts; every live verification claim remains false. The combined utility contains client-side diagnostics, shared local commands, and any gated runtime trial. Its target dropdown and categorized game commands share selection, mode, running, and failure state. After an authorized client trial, save the JSON returned by `;interactionfeedback`; evaluate it directly with `python3 tools/evaluate_prompt_trial_feedback.py build/action-capabilities.json feedback.json` or rebuild with `python3 tools/build_release.py scan-parts --output build-with-feedback --prompt-feedback feedback.json`. The latter digest-links `prompt-trial-evaluation.json` into the release manifest and bundle. Command wiring and Luau syntax are checked but not live Roblox verified, and evaluated feedback remains client-observed correlation. This is a working generation stage, **not** a system that can infer or implement arbitrary server-authoritative gameplay features from read-only scans.

## v10 one-command release build

Place all JSON parts for **one** scan in a directory and run:

```sh
python3 tools/build_release.py ./scan-parts --output ./build
python3 -m unittest discover -s tests -v
```

The build validates multipart integrity, compiles a capability plan, generates a place-bound Lua diagnostic utility, checks its expected structure, and writes a deterministic release ZIP plus manifest. The GitHub Actions workflow `offline-pipeline.yml` runs the tests and builds an example artifact on relevant pushes. The generator does **not** implement arbitrary gameplay automation, deploy to Roblox, or prove in-game behaviour. Do not upload sensitive scan reports to a public repository.


## v11 real inspection data compatibility

The compiler accepts numbered JSON parts from the actual inspector, including metadata-only and interaction-history-only parts, plus an optional local manifest JSON. Run `python3 tools/build_release.py scan-parts --output build`. New v30.1 manifests include the multipart `scanId`; legacy manifests such as the supplied Bubble Gum report do not, so their receiver records cannot be identified from that manifest alone. Save the receiver's `/reports/READ_KEY/SCAN_ID/integrity` JSON and run `python3 tools/reconcile_receiver.py local-manifest.json receiver-integrity.json`. A verified result establishes that the supplied response satisfies receiver-stored part identity, uniqueness and object-accounting checks, making that receiver report available for downstream retrieval; it does not authenticate the saved response or prove byte-for-byte equivalence to local payloads without matching part hashes. Receiver changes are source-only until the Cloudflare Worker is deployed.

In legacy manifests, `uploadedParts: 0` is a snapshot-time placeholder, not proof of failure or success. v30.1 adds `reportTransport` with explicit not-attempted, uploading, acknowledged, incomplete, failed, or configuration-error state; even `acknowledged` keeps receiver integrity and downstream availability false until separately verified. `tools/manifest_readiness_v109.py` emits a safe integrity path when `scanId` is present. Local manifests are identity-checked against numbered parts during release compilation. Client-side state corroboration is not server-side verification.


## v12 Inspector UI fix

AUTO EVIDENCE is now in a dedicated right-hand sidebar, away from the title and minimise button. The output pane is narrower so it does not cover the new controls. The sidebar shows the automatic full-rescan budget and clarifies that multipart ACKs are not the same as receiver-side integrity verification. Static UI tests run with the existing CI suite. Roblox runtime layout has not yet been visually verified.


## v13 workflow evidence compilation

Run `python3 tools/build_release.py scan-parts --output build` to produce a release ZIP containing `workflow-specs.json` alongside the capability plan, generated Lua utility and release manifest. Workflow evidence tiers distinguish observed clicks, temporal state changes and client-state corroboration. They do not establish executable server gameplay actions. This is a universal evidence-processing stage for any scanned Roblox place, not a Muscle Legends-specific implementation.


## v14 automatic implementation review

The one-command build now produces `implementation-review.md` in the release archive. It ranks discovered gameplay features by observed evidence and documents the missing validation needed for each one. The inspector title now reserves space for the minimise button; the AUTO EVIDENCE control is placed below the interaction toggle with separate sidebar labels. Run `python3 -m unittest discover -s tests -v` to validate the offline pipeline. This is an evidence-driven development report, not executable server gameplay automation.


## v15 reviewed action contracts

The build pipeline now optionally accepts a reviewed contract file: `python3 tools/build_release.py scan-parts --output build --contracts reviewed-contracts.json`. The contract schema requires `schemaVersion: "15.0"`, a matching `placeId`, and an array of `contracts` with discovered feature names, `reviewed: true`, and a supported read-only client action (`read_leaderstats`, `list_player_gui`, `list_proximity_prompts`). Contracts are validated and bundled, not executed. Unsupported operations are rejected. This is an incremental step toward reliable implementations, not automatic arbitrary gameplay scripting.


## v16 — Baseline plus dynamic observation fusion

The release builder can combine a verified complete baseline scan with up to 64 complete dynamic-observation scans for the same Roblox Place ID. Example: `python3 tools/build_release.py ./baseline-parts --observation ./delta1-parts --observation ./delta2-parts --output ./build`. `tools/merge_observations.py` validates scan and normalized source-provenance identity, rejects duplicate scans, mismatched places, and unsupported positive trust claims, then merges per-feature evidence counters. Each overlay retains provenance separately in the capability plan and deterministic `evidence-overlay-provenance.json`; `source-provenance.json` continues to describe only the baseline. Dynamic observations never replace the baseline object inventory or establish authenticity, causality, authority, replayability, gameplay success, or executable gameplay contracts. Supply each scan's complete multipart JSON files in its own folder.


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
