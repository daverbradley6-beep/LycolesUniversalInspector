# Lycoles Universal Inspector

Current inspector release: **v30.6.33**

Current integrated offline pipeline: **v108**

The repository has two version tracks. `LycolesUniversalInspector.lua` and the deterministic multipart release builder use the v30 release line. The newer v100–v110 tools are staged, independently tested inspection-to-client-observer components; v109 analyzes local manifest readiness and v110 composes evidence-ranked gameplay understanding without changing the inspector's multipart wire format.

## Current capabilities

- Read-only inspection of bounded, client-visible Roblox instance metadata across replicated services, the local player, character, GUI, lighting, teams, sound, and workspace.
- A two-tab in-game interface keeps inspection controls and Generated Script status in one panel. `PRODUCE SCRIPT` records a bounded client-visible capability request and captures a complete scan for offline compilation; it does not generate or execute gameplay behavior in the target session. The Generated Script tab distinguishes request text from evidence and tracks scan identity, numbered parts, local export, receiver acknowledgements, and pending offline validation while keeping receiver integrity and gameplay unverified. Offline generation emits a place-bound `Lycoles-PLACE-generated-result.json`; schema 113 embeds validated generation readiness so `LOAD RESULT` can display generated bounded capabilities, exact target/outcome evidence, unavailable requested behavior, static-validation status, and verification limits alongside code. The loader retains display-only schema 110 compatibility, never executes imported code, and explicitly treats package authenticity and runtime/gameplay behavior as unverified.
- Multipart JSON upload with acknowledgement, retry, scan identity, object accounting, explicit local transport lifecycle status, and a separately deployed Cloudflare Worker integrity endpoint. `SAVE REPORT` exports every exact numbered part and finalizes a self-consistent matching manifest; partial part or manifest writes remain explicitly incomplete/failed. v30.6.1 separately labels upload attempts, receiver progress, integrity, and downstream availability, including configuration blocks before or after an attempt and durable complete/partial ACK coverage. Manifest-readiness v109.3 derives and validates the same stages and recommends local-part or receiver recovery without assuming an unavailable or failed receiver; local write success and ACKs remain claims pending independent import/integrity validation.
- Passive observation of normal user interactions and bounded before/after client-state evidence from leaderstats, Data, and privacy-filtered LocalPlayer numeric/boolean ValueBase candidates. v30.6 samples supported GUI, ProximityPrompt, and newly equipped Tool paths from a bounded pre-activation signal so synchronous changes are less likely to be missed; every event labels whether it used that baseline or a callback-time fallback. Exact pending/completed/failed window accounting, pre-activation capture failures, and possible-loss diagnostics disclose incomplete evidence. v30.6.2 preserves that timing provenance through Prompt/Tool/GUI action discovery, canonical workflow steps, generated capability summaries, strict result validation, and the Generated Script display. v30.6.6 additionally records monotonic session-relative activation timing, validates timing coverage, and reports bounded adjacent unlinked event pairs for review; proximity never creates a transaction link or generated workflow. Coverage is limitations-only: complete accounting does not increase readiness, and feature-consistent or temporally adjacent changes never prove causality, server authority, live runtime success, or gameplay success.
- v30.6.33 surfaces transport readiness and blocker context directly in `LycolesManifestAssistedWorkflow.lua` status views so manifest-assisted trial scripts retain upload/readiness diagnostics while preserving fail-closed gameplay claims.
- v30.6.32 extends `manifest-assisted-workflow.json` with upload/readiness context (`transportReadinessStatus`, `transportReadinessBlockers`, `scriptGenerationReady`) and schema `30.6.manifest-assisted-workflow.4`, helping downstream tools distinguish evidence availability from upload-lifecycle blockers.

- v30.6.31 strengthens manifest-assisted script targeting by prioritizing interactions that include explicit `observableOutcomeCandidate` evidence, exposing that flag in generated Lua and metadata, and bumping manifest-assisted workflow schema to `30.6.manifest-assisted-workflow.3`.

- v30.6.30 improves manifest-readiness upload diagnostics for legacy snapshots with `uploadedParts` ambiguity: readiness now separates complete-local-export unknown lifecycle, partial-local-export unknown lifecycle, attempted-without-lifecycle, and pre-upload placeholder states with explicit blockers and next-action guidance.

- v30.6.29 adds a conservative post-capture fallback that backfills missing `observableOutcomeCandidate` entries from already-captured feature-consistent state/GUI changes across observation windows, while preserving fail-closed claims (`causalityProven=false`, `serverAuthorityVerified=false`, `gameplayVerified=false`) and explicitly reporting recovered counts via `backfilledOutcomeCandidates`.

- v30.6.28 improves manifest-assisted generation quality for manifest-only sessions: target extraction now prioritizes feature-attributed interactions with observed GUI/state transitions, filters unattributed no-change noise, surfaces per-target observed change counts in generated Lua, and emits schema `30.6.manifest-assisted-workflow.2` metadata with explicit `stateChangeCount`, `guiStateChangeCount`, and `observableChange` fields.

- v30.6.27 improves real-world workflow root-cause diagnostics without lowering verification standards: manifest-readiness now derives feature-attributed transition coverage from `recentInteractions`, surfaces transition counts per feature, and emits `feature_attributed_transitions_without_outcome_contract` when observable feature transitions exist but no completed workflow candidate contract can be resolved.


- v30.6.26 expands manifest-assisted generated activation for observed controls: `Activate` now supports bounded attempts for `GuiButton.Activated`, `ProximityPrompt.Triggered` (when an executor exposes `fireproximityprompt`), and `Tool.Activated` (official equip + `Tool:Activate()`), each with before/after state-hint snapshots and explicit unverified runtime/gameplay status.
- v30.6.25 adds manifest-assisted functional generation fallback: when only a manifest snapshot is available (no numbered object parts), offline build now emits `LycolesManifestAssistedWorkflow.lua` plus `manifest-assisted-workflow.json` using observed interaction evidence (exact paths, feature candidates, control contracts, bounded state hints). The generated UI exposes bounded Prev/Next/Probe/Activate controls for real game-specific targets while preserving explicit blocked full-release status and unverified runtime/gameplay claims. `integrated_pipeline_v108.py` now detects this manifest-only mode and returns a structured blocked summary instead of crashing with `invalid inspection`.

- v30.6.24 improves linkage root-cause diagnostics for real-world scans: manifest-readiness now reports transaction-ID reuse metrics and flags `transaction_ids_not_reused_across_steps` when callbacks are single-use, with explicit recording guidance for capturing linked multi-step workflows.

- v30.6.23 clarifies legacy upload diagnostics for manifest-only sessions: when `uploadedParts` is zero but `localPerformance` shows multipart export telemetry, manifest-readiness now distinguishes local export evidence from unknown receiver upload lifecycle and provides stage-specific recovery guidance.
- v30.6.22 extends linked-workflow diagnostics for GUI-only flows: planner now surfaces bounded review-only linked GUI workflow candidates when linked transitions are observed without scalar outcome contracts, and readiness reports dedicated review-only linked-candidate planning diagnostics without promoting generation-ready status.
- v30.6.21 sharpens request-readiness guidance for GUI-only sessions: when request-aligned GUI transition evidence exists but no resolvable scalar outcome contract is available, readiness now emits an explicit fail-closed blocker and bounded review-only path diagnostics.
- v30.6.20 hardens workflow selection compatibility: planner, readiness, and guided-workflow validation now share consistent request-term normalization, preventing false selection drift from synthetic stems while preserving conservative bounded matching.
- v30.6.19 integrates deterministic workflow-candidate artifacts into the v106 integrated pipeline: normalized interaction history now feeds `workflow-candidates.json`, diagnostics expose completed/review-only workflow counts, and verification fail-closes on any workflow artifact tampering.
- v30.6.18 improves mixed GUI/state evidence diagnostics without overclaiming readiness: GUI targets now classify observable outcome evidence as `resolvable-scalar`, `gui-transition-only`, or `none`, and aggregate review-only GUI transition candidates are surfaced separately from generation-ready targets.
- v30.6.17 refines follow-up-only capture guidance: when linkage evidence comes only from non-confirm follow-up links, manifest-readiness now recommends capturing one same-menu confirmation/cancel step with observable before/after values.
- v30.6.16 improves readiness diagnostics clarity by exposing explicit workflow-linkage evidence typing (`none`, `confirmations-only`, `followups-only`, `confirmations-and-followups`) plus total linked-workflow-event counts in manifest-readiness outputs.
- v30.6.15 improves workflow correlation without overclaiming authority: bounded non-confirm follow-up linking can connect semantically meaningful consecutive actions into one transaction when context overlap is strong, and diagnostics now report `linkedFollowups`/`linkedWorkflowEvents` with explicit `observed-followup-link` provenance.
- v30.6.14 improves functional guided GUI generation: text-only GUI metadata drift can remain generation-ready when non-text availability and identity fields stay stable, and generated/planned workflows explicitly mark `guiTextDynamic` while still fail-closing on control-class, visibility, scrolling, and interactable drift.
- v30.6.13 adds clearer upload/linkage diagnostics for legacy and live manifests (`transportReadiness`, `uploadLifecycle`, `workflowLinkageDiagnostics`) and improves passive confirmation linking by expanding bounded yes/no tokens, dialog-context cues, and conservative feature-default action inference for generic controls.
- v30.6.12 improves generation readiness for confirmation-driven UI flows: action discovery can now inherit resolvable scalar outcome evidence from later events in the same linked transaction when initiator events lack direct scalar deltas, while preserving explicit inherited-evidence provenance and all-negative verification claims.
- v30.6.11 improves functional interaction interpretation: bounded context-scored attribution (control name/text + ancestor/path context), expanded real-game menu hints, context-token confirmation linking, and unambiguous action-kind feature inference so more observed interactions can be grouped into meaningful workflow evidence without claiming causality, runtime success, or server authority.
- v30.6.9 adds an explicit `SCAN MODE` toggle (FULL/QUICK), configurable auto-evidence observation delay, and cancellation/recovery for active scan/upload work. QUICK mode records targeted client-visible evidence with stricter profile-filtered omission disclosure and a default one-rescan budget for faster feedback. Snapshot completion, part packaging, and upload lifecycle now surface as separate stages with local timing output. `PRODUCE SCRIPT` automatically switches to FULL mode so generation requests still capture complete evidence packages.


- v30.6.8 adds an explicit `RECORD FLOW` Inspector control. When armed, it assigns one random shared transaction ID and consecutive order to at most eight normal observed interactions over at most 60 seconds. Recording stops on the operator command, timeout, capacity, observer disable, inspector close, or scan start. The planner validates the full recording contract before use. This proves only operator-intended order—not causality, runtime success, gameplay success, or server authority—and every step still needs an exact evidence-derived action/state contract.
- v30.6.7 augments changed GUI visibility records with exact PlayerGui component identity and reports a bounded followup candidate when a later normal user activation targets the revealed component or an exact descendant within 15 seconds. The planner independently checks the source transition, both endpoint identities, session timing, and negative claims. These episodes remain review-only: they do not create transaction IDs, generated workflow candidates, causality, runtime readiness, or gameplay verification.
- Deterministic offline compilation of complete scans into capability plans, workflow evidence, reviewed read-only client actions, manifests, reproducible release archives, and normalized source-provenance status. Local multipart provenance records SHA-256 for the exact current raw bytes of every accepted numbered part and rejects raw-byte-ambiguous duplicates; those hashes establish deterministic input identity, not source authenticity or equivalence to receiver or original in-game bytes. Generated utility UI exposes local digest coverage, retrieval integrity, and their explicit trust limits without claiming authenticity or gameplay verification.
- v109 manifest readiness analysis explains upload ambiguity, interaction evidence, outcome-candidate lower bounds, missing multipart data, and generation blockers without treating the local manifest as a full report.
- v110 composes multiple concurrent gameplay-system candidates, observed resources/actions, temporal relationships, loop candidates, objective candidates, automation opportunities, and request blockers. Its versioned provider-independent profile index preserves unknown discovered feature categories under stable generic IDs, uses path-and-component-identity-derived resource IDs so equal labels and duplicate flat paths cannot collide, and publishes structured unresolved evidence gaps for downstream consumers. The system inventory is bounded with explicit truncation counts. It deliberately reports no single genre, causal mechanics, implementation readiness, or verified gameplay behavior.
- v30.6.5 generated utilities embed any selected evidence-linked workflow alongside evidence-backed Prompt/Tool/GUI controls and the reusable **Admin Commands** section, so one `LycolesGeneratedUtility.lua` launch exposes all supported generated controls; the linked workflow also remains a separate reviewable artifact. The `;` command bar provides local client utilities (`fly`, `noclip`, `tp`, `goto`, `speed`, `jump`, `coords`, evidence-backed `systems`/`readiness`, `reset`, `rejoin`, `stopall`, and help/GUI controls). Admin GUI and command controls share state and cleanup; each generated trial retains its own explicit STOP/CLOSE controls. Actual generated Luau is exercised in bounded client stubs for state changes, cleanup, respawn continuity, and place guarding; this remains simulated evidence, game restrictions may override local effects, and no server administrator privilege is implied.
- v30.5 retains bounded actionable prompt/GUI/Tool metadata, class/name/sibling-ordinal component identities, composable action surfaces, and deterministic action-to-state/GUI temporal relationships. Any observed ProximityPrompt with a resolvable scalar outcome can produce a place-bound `LycolesPromptInteractions.lua` trial ranked by requested-capability alignment and gameplay-objective usefulness; when several scalar values change together, request/context alignment deterministically selects the one bounded outcome that generated code monitors. Prompt text, enabled state, hold duration, activation distance, input keys, and anchor metadata are normalized into bounded observation snapshots; distinct snapshots expose drift rather than silently overwriting evidence. The generated UI and shared `;interaction*`/compatible `;egg*` Admin Commands select a target, move to its nearby anchor, invoke executor-provided `fireproximityprompt` only when available, observe the recorded increased/decreased/changed outcome direction, and stop after three failures or 25 total attempts. `;interactionfeedback` exports at most 100 discovery-digest-bound attempt records for offline validation by `tools/evaluate_prompt_trial_feedback.py`; the evaluator rejects unknown targets, unselected outcomes, forged directional changes, and positive verification claims. Component identities preserve literal dots and duplicate sibling names; ambiguous new state identities fail closed while legacy evidence retains a flat-path fallback. No discovered remote is invoked. Bubble Gum Simulator INFINITY's Rainbow Egg is the primary real-evidence example, but temporal correlation and imported feedback still do not prove causality, server authority, Roblox runtime success, or gameplay functionality. Auto and Multi game modes remain unavailable until the explicit live-observation blockers in `action-capabilities.json` are resolved. Controlled official-Luau execution validates wiring only in simulation.
- Generated guided workflows now add digest-bound feedback for multi-step GUI trials. `LycolesGuidedWorkflow.lua` records each exact ordered step as one of unresolved identity, metadata drift, unreadable state, normal-user activation timeout, outcome not observed, or expected client-visible direction observed; it caps records at 400 and provides a local print-only JSON export without clipboard, network, synthetic activation, or remote invocation. `tools/evaluate_guided_workflow_feedback.py` requires the exact canonical `generated-workflow-plan.json` digest, deterministic rendered candidate, step identity/order, outcome contract, run order, scalar direction, and all-negative verification claims. `tools/aggregate_guided_workflow_feedback.py` can combine up to 100 uniquely identified matching sessions, disclosing recurrence, status conflicts, and scalar-type drift; repeatable release `--guided-feedback` inputs bundle that aggregate and project only an informational correlation summary into generation readiness. v30.6.4 adds an operator-armed five-sequence repeat mode: the first sequence must match exact observed entry state, every later step must continue from the prior observed value for the same state identity, and STOP/CLOSE or any drift/failure/unobserved outcome cancels the trial. A complete or repeated client-observation sequence is still not causal, server-authoritative, gameplay-semantic, source-authenticated, implementation-ready, or live-runtime verification.
- Observed `Tool.Activated` events retain enabled/manual-activation/handle/drop/tooltip prerequisites, exact LocalPlayer component identity, and selected resolvable scalar outcome evidence. When all three evidence classes are present and unambiguous, the shared interaction artifact can generate an operator-started bounded Tool trial: it uniquely resolves the observed Tool across Backpack/Character movement, rejects changed Tool prerequisite metadata, equips through `Humanoid:EquipTool()`, checks `Tool.Enabled`, calls official `Tool:Activate()`, watches only the selected scalar direction, and stops after three uncorroborated attempts or 25 total attempts. Digest-bound feedback accepts Tool-specific disabled, equip, and metadata-drift failures without upgrading claims. A strict official-Luau stub harness verifies equip, activation, selected outcome observation, shared controls, cleanup, and failure limits in simulation only; live Roblox runtime, causality, server authority, action outcome, and gameplay remain unverified. Incomplete or ambiguous Tool evidence remains discovery-only, and no discovered remote is directly invoked.

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

Outputs: `LycolesGeneratedUtility.lua`, standalone `LycolesAdminCommands.lua`, `gameplay-understanding.json`, `action-capabilities.json`, `generated-workflow-plan.json`, `generation-readiness.json`, and `release-manifest.json`; `LycolesPromptInteractions.lua` is added only when at least one observed prompt, Tool, or GUI control has an eligible bounded trial contract, while `LycolesGuidedWorkflow.lua` is added only for a complete explicitly linked sequence of at least two exact guided GUI controls. The readiness artifact recomputes emitted bounded capabilities, request-matched subsets, unavailable behavior, and discovery-only candidates from the source artifacts; every live verification claim remains false. The combined utility contains client-side diagnostics, shared local commands, and any gated runtime trial. Its target dropdown and categorized game commands share selection, mode, running, and failure state. After an authorized client trial, save the JSON returned by `;interactionfeedback`; evaluate it directly with `python3 tools/evaluate_prompt_trial_feedback.py build/action-capabilities.json feedback.json` or rebuild with `python3 tools/build_release.py scan-parts --output build-with-feedback --prompt-feedback feedback.json`. The latter digest-links `prompt-trial-evaluation.json` into the release manifest and bundle. For a generated multi-step GUI trial, press **PRINT DIGEST-BOUND FEEDBACK JSON**, save the JSON following the local `LYCOLES_GUIDED_WORKFLOW_FEEDBACK|` prefix, and run `python3 tools/evaluate_guided_workflow_feedback.py build/generated-workflow-plan.json guided-feedback.json`; combine matching sessions with `python3 tools/aggregate_guided_workflow_feedback.py build/generated-workflow-plan.json guided-a.json guided-b.json`, or rebuild with repeated options such as `python3 tools/build_release.py scan-parts --output build-with-feedback --guided-feedback guided-a.json --guided-feedback guided-b.json` to include `guided-workflow-feedback-aggregate.json` and an informational-only readiness correlation. Command wiring and Luau syntax are checked but not live Roblox verified, and evaluated feedback remains client-observed correlation. This is a working generation stage, **not** a system that can infer or implement arbitrary server-authoritative gameplay features from read-only scans.

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

The offline pipeline now retains up to 2,000 observed client interaction records in the capability plan and writes `observed-workflows.json` in every release. `tools/compile_interaction_sequences.py` groups events only when they share an observed transaction identifier, retains bounded before/after state evidence, records step order and keeps unlinked events separate. `tools/plan_generated_workflows.py` additionally writes `generated-workflow-plan.json`: a review-only projection emitted only when one explicit transaction contains at least two Prompt, Tool, or guided GUI steps whose exact component identities, prerequisite snapshots, selected scalar outcomes, and source sequence evidence still match action discovery. It preserves original transaction positions, discloses omitted non-ready events, and records adjacent equal-value state continuity without treating it as causation. Legacy flat paths remain compatible with eligible single-control trials but cannot qualify for exact workflow planning. When every linked event is represented by an exact guided GUI contract, `LycolesGuidedWorkflow.lua` can highlight the controls one at a time, wait for each normal user `Activated` event, require the selected client-visible scalar direction before advancing, and stop on identity, prerequisite, timeout, or outcome failure. It never synthesizes a GUI event. This is an operator-started bounded trial, not automatic gameplay execution: no workflow is marked executable, runtime verified, gameplay verified, or causally proven. No remote calls are inferred or executed. v30.6.3 separately reports transaction groups, shared multi-event IDs, singleton per-event IDs, absent linkage, insufficient exact contracts, partial mappings, and over-bound sequences; a unique ID on one event is no longer described as a linked transaction. Those diagnostics are limitations-only and cannot upgrade causality, runtime, gameplay, server-authority, or source-authenticity claims. This release does not change receiver indexing or add automatic upload-to-build execution.

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
