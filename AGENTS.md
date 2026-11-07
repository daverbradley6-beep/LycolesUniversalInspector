# Lycoles Universal Inspector Development Guidance

## Objective

Develop Lycoles as a universal, evidence-driven Roblox inspection and script-generation system. Prioritize reliability, accurate interpretation, compatibility, automated testing, and functional Luau generated only when supported by observable evidence.

## Permanent environment constraints

Target experiences are third-party games that the user does not own and cannot open in Roblox Studio.

- Never require target-game Studio access, `.rbxl`/`.rbxlx` files, private source, server scripts, developer-only services, or experience ownership.
- Never make ownership-dependent validation a prerequisite or repeatedly recommend Studio access as the solution.
- Build from legitimately observable client-side information and permitted interfaces.
- Do not implement anti-cheat bypasses, exploit loaders, security circumvention, unauthorized remote invocation, stealth mechanisms, or access-control evasion.
- Do not merge into `main` without explicit authorization. Develop and push verified work on `openhands-development`.

## Evidence architecture

Prioritize, in order:

1. Client-visible instance hierarchy and object metadata.
2. Observable UI structure, state, and interactions.
3. Replicated objects and properties available through permitted interfaces.
4. Observable gameplay state changes.
5. Evidence-based gameplay-system identification.
6. Deterministic normalization and provenance preservation.
7. Evidence-backed Luau generation.

Every contract must distinguish:

- **Observed fact:** directly present in a validated client-side report.
- **Inference:** a deterministic interpretation supported by stated evidence.
- **Unknown:** server authority, causality, remote behavior, anti-cheat behavior, or runtime outcomes not established by evidence.

Client visibility never proves server authority, causality, or gameplay success.

Current v108 interpretation contract: `tools/system_interpreter_v108.py` emits explicitly classified deterministic-inference `108.system-interpretation.1` candidates over the exact canonical v107 report/feature plan. Optional `108.relationship-evidence.1` inputs are immutable caller-supplied, shape/provenance-reference validated, ambiguity-quarantined correlations; their source authenticity, causality, server authority, and gameplay meaning remain explicit unknowns.

Current v108 runtime contract: `tools/runtime_contract_v108.py` derives exact expected checks and compares optional bounded `108.runtime-observation.1` evidence by structured status, never display text. Absence is `not_observed`, a failed status is `drifted`, and complete matching is only deterministic comparison evidence. `tools/integrated_pipeline_v108.py` must reconstruct every v107/v108 artifact exactly, report unsupported observations/capabilities/APIs explicitly, and keep source authenticity, Roblox runtime, live-game, server-authority, causality, and gameplay claims false.

Current v30.1 inspector contract: generic controls may derive action candidates only from bounded semantic ancestry; feature readiness may use only feature-consistent observable state/GUI changes. `completedCandidates` means an observable correlation candidate, never causal success. `outcomeVerified`, source authenticity, server authority, and gameplay verification remain false unless separately established.

Current v109 manifest contract: `tools/manifest_readiness_v109.py` analyzes a local manifest without treating it as the numbered multipart report. Legacy `uploadedParts: 0` is an unknown pre-upload snapshot, not transport failure. New manifests expose the generated multipart `scanId`, and local-manifest identity/counts must match numbered parts. Inspector `SAVE REPORT` must persist the exact already-encoded `pendingParts` bodies plus a self-consistent finalized manifest; complete may be recorded only after every part and the manifest carrying that completed state are written, while partial/finalization failure remains explicit. It must not claim local part digests were computed when they were not. Manifest readiness must distinguish local export claims from upload ACKs, receiver integrity, and downstream availability, and recommend recovery without claiming files or receiver data were actually retrieved. The Generated Script tab may summarize scan, local-export, upload, and offline-generation handoff state, but must label request text as non-evidence and keep ACK-only receiver integrity plus gameplay unverified. Generated-result imports are display-only, bounded, place-bound, and must require false authenticity/runtime/gameplay/execution claims; never evaluate imported code or treat its embedded digest as authenticated in-game. Explicit ACK state still does not establish receiver integrity or downstream availability. A separately validated direct Worker `/integrity` response may establish receiver-stored report availability, but not local payload equivalence without matching hashes. Manifest-only input must keep v107/v108 script generation blocked because canonical object parts and reviewed contracts are absent. `tools/fetch_receiver_scan.py` is the network boundary: keep read keys environment-only, require HTTPS, reject redirects, use constant-cost receiver metadata rather than the O(part-count) Worker integrity route, validate every part before atomic publication, and leave `tools/build_release.py` offline.

Current v30.2 transport contract: the Worker hashes exact accepted request bodies, persists per-part SHA-256 sidecars, and returns them in ACKs and numbered-part headers. The inspector requires and records digest-bearing ACKs. The importer must fail closed on missing/mismatched persisted digests and may compare a supplied local ACK manifest. Optional resume state must stay outside output, contain no read key, bind to receiver origin plus canonical metadata, retain only digest-verified parts through atomic checkpoint updates, revalidate every cached part before final atomic publication, and remain explicitly unauthenticated. `receiverStoredPayloadDigestsVerified`, `receiverAcknowledgementDigestEquivalent`, and resume checks do not authenticate either party or establish locally computed original-byte equivalence. Production Worker deployment remains separately authorized.

Current release provenance contract: `tools/compile_scan.py` must distinguish ordinary local manifests, strict `30.2.receiver-import.2`, and explicit `30.2.receiver-import-legacy.1`, require the exact matching field set, reconcile every identity/accounting field, and recompute each current raw part digest. Receiver imports retain normalized `30.2.source-provenance.1`; local multipart compilation emits `30.2.source-provenance.2` with complete exact-current-byte digest coverage and rejects duplicate indices whose canonical documents match but raw bytes differ. Strict v12 requires receiver-stored digest verification. Legacy v11 first requires complete receiver integrity, records exact locally computed response digests, forbids resume, and must keep receiver-stored digest verification false. Direct multipart input must report receiver checks unavailable. `source-provenance.json`, release manifests, documentation, and generated UI may surface retrieval integrity, ACK equivalence, and resume reuse only while checkpoint authentication, receiver-response/source authenticity, original local payload equivalence, causality, authority, replayability, gameplay, and action outcomes remain false or unverified. `tools/diagnose_receiver_access.py` may probe configured known scan IDs without printing origin/read-key values or unrelated record IDs and must name missing configuration before network access. Probe the authenticated collection first: `multipart-scans` can continue to per-scan v12/v11 checks, while `legacy-single-reports` is the original pre-multipart contract and is never eligible for multipart recovery. Agent Canvas conversations may retain their startup secret snapshot; after Settings secrets are added, use a fresh conversation rather than requesting duplicates or plaintext values.

Current v30.6.1 handoff-lifecycle contract: in-game status and `reportTransport` must distinguish report generation/local export from upload attempt, receiver storage acknowledgement/integrity, and downstream availability. `uploadAttemptStatus` is not attempted, blocked before attempt, attempted, or previously attempted/currently blocked; `receiverReportStatus` is unavailable, configuration-blocked, upload-in-progress/incomplete, partially acknowledged, fully acknowledged awaiting integrity, or integrity verified. Complete or partial ACK accounting survives a later configuration error. `downstreamAvailabilityStatus` remains not validated until independent integrity/import evidence permits otherwise. `tools/manifest_readiness_v109.py` derives these labels from canonical status/count/verification fields, rejects contradictory explicit labels, treats legacy `uploadedParts: 0` as unknown rather than failure, and recommends integrity verification after complete ACK coverage even if the latest retry is blocked. Local writes and ACKs alone never establish receiver integrity, downstream availability, source authenticity, runtime behavior, or gameplay verification.


Current v30.3 capability-request contract: the in-game Generated Script tab stages one bounded client-visible request and triggers a complete evidence scan. The request may be carried through metadata-bearing parts, lifecycle manifests, capability plans, release manifests, and generated read-only Luau only as user intent and evidence-review context. `PRODUCE SCRIPT` does not imply in-game generation, runtime installation, action support, causality, replayability, authority, or gameplay success; those remain offline-validated or unverified as explicitly reported.
- v30.6.19 v104/v106 pipeline integration now treats normalized `observedInteractionHistory` as first-class deterministic workflow evidence. Integrated output must include `workflow-candidates.json`, diagnostics must expose workflow/completed/review-only counts, and verification must fail closed on any workflow-artifact tampering or drift.

- v30.6.20 workflow selection normalization contract: planner (`plan_generated_workflows.py`), readiness (`assess_generation_readiness.py`), and guided workflow validator (`generate_guided_workflow.py`) must keep request-term tokenization semantically aligned. Synthetic `stem+"e"` forms are disallowed; canonical matching must not emit invalid artifacts like `traine`.

- v30.6.21 readiness diagnostic contract: request-feature synthesis must surface request-aligned review-only GUI transition evidence separately from generation-ready workflow candidates and emit `request_aligned_gui_transition_outcomes_without_scalar_contract` when aligned GUI transitions lack a resolvable scalar outcome contract.

- v30.6.22 workflow-planning contract: linked GUI transition evidence without resolvable scalar outcomes may surface bounded review-only workflow candidates, but must remain non-generation-ready and explicitly reported via `reviewOnlyLinkedCandidates`, `requestAlignedReviewOnlyLinkedCandidates`, and `selectedReviewOnlyCandidateId` diagnostics.


- v30.6.23 manifest-readiness legacy transport contract: when `reportTransport` is absent, `uploadedParts` alone is insufficient; bounded `localPerformance` multipart telemetry must be surfaced as diagnostic context (`legacyLocalMultipart*`) while preserving unknown upload lifecycle unless receiver acknowledgement/integrity is explicitly verified.

- v30.6.40 performance/action-correlation pass adds adaptive queued input processing with strict frame budgets and queue caps, local-player-only Humanoid/Tool universal observers, scoped state snapshots by action priority, and backpressure-aware observation windows. Low-priority repetitive movement/animation noise is explicitly deprioritized, while meaningful inputs (fire/reload/switch/equip/unequip/interact) remain queued for bounded correlation. Diagnostics now expose queue depth/throughput, callback peak rate, phase transitions, and state-snapshot timing without asserting causality/server authority/gameplay success.
- Real scan archive note (2026-11-06): `Lycoles_..._AC79D385..._part-1249.zip` on `origin/main` is a combined archive containing both full datasets (`AC79D385...` Bubble: 1,254 JSON files including manifest; `7965AF57...` Arsenal: 1,235 JSON files including manifest). Extract by scan-id token match rather than assuming one scan per uploaded ZIP filename.
- v30.6.40 live-capture export fix: `COPY JSON` now emits a fresh `30.6.live-observation-export.1` dynamic-observation payload (not the frozen startup manifest). It flushes bounded queued input tasks before encoding, carries baseline scan linkage (`baselineScanId`), exposes recent interactions/action classifications/state-change windows/performance telemetry, and is merge-ingestable as a no-rescan evidence overlay (`scanMode="dynamic-observations"`, local multipart provenance claims all false, `mergeTool="tools/merge_observations.py"`).
- Readiness diagnostics update (v30.6.39 follow-up): `tools/assess_generation_readiness.py` now emits explicit combat-request observation gap blockers when evidence is missing: `request_aligned_input_observation_not_captured` and `request_aligned_state_transition_not_observed`. These are evidence-gap diagnostics only; they do not upgrade causality/runtime/gameplay verification claims.

- v30.6.24 workflow-linkage diagnostic contract: when linked workflow evidence is absent, manifest-readiness must report bounded transaction-ID reuse metrics and flag single-use transaction patterns (`transaction_ids_not_reused_across_steps`) as root-cause capture guidance without claiming causality or workflow completion.
- Arsenal-like games may not emit enough GUI-only interaction evidence. v30.6.39 extends passive capture with bounded global input, tool equip/unequip, humanoid movement/jump, and animation observations; keep these pathways read-only and throttled.
- New interaction diagnostics now include `inputObservationStats` and automatic workflow recording policy (`automatic-activity-window-with-optional-manual-override-not-causal-proof`). Preserve this contract in future schema adjustments.
- Potassium lexical-local pressure is sensitive to top-level `local`/`local function` growth. For new observer logic, prefer namespace method assignment (e.g., `WORKFLOW_HELPERS.someMethod = function(...)`) over additional top-level local function declarations to stay within `tests/test_inspector_compiler_limits.py` root-pressure budget (<=170).


- v30.6.25 manifest-only functional fallback contract: `tools/build_release.py` must keep full-release generation fail-closed when numbered multipart object parts are unavailable, but may emit bounded manifest-assisted operational artifacts (`LycolesManifestAssistedWorkflow.lua`, `manifest-assisted-workflow.json`) derived only from captured client-visible interaction evidence (exact observed paths/contracts/state hints) with all verification/authenticity/authority/gameplay claims remaining false. `tools/integrated_pipeline_v108.py` CLI must detect this manifest-only input shape and return a structured blocked summary instead of raising `invalid inspection`.


- v30.6.26 manifest-assisted activation contract: generated manifest-assisted Lua may attempt bounded activation only for observed `GuiButton.Activated`, `ProximityPrompt.Triggered`, and `Tool.Activated` controls (with availability checks for executor prompt support and Tool equip prerequisites). Each attempt must preserve explicit before/after hint reporting and retain all-negative verification claims.

- v30.6.27 workflow root-cause contract: manifest-readiness must derive bounded observable-transition diagnostics from `interactionDiagnostics.recentInteractions` and flag `feature_attributed_transitions_without_outcome_contract` when feature-attributed GUI/state transitions exist but no completed workflow candidate contract is available; this remains fail-closed guidance only and never upgrades causality/runtime/gameplay verification.


- v30.6.28 manifest-assisted target-selection contract: manifest-only fallback target extraction should prioritize feature-attributed interactions with observed GUI/state transitions, suppress unattributed zero-change noise, and expose bounded per-target transition counts (`stateChangeCount`, `guiStateChangeCount`, `observableChange`) in both generated Lua target context and `manifest-assisted-workflow.json` schema `30.6.manifest-assisted-workflow.2`.


- v30.6.29 post-capture outcome contract: before report export, inspector may conservatively backfill missing `observableOutcomeCandidate` entries from already-captured event/window evidence only when existing feature-consistent state/GUI heuristics match. Backfilled candidates must retain all-negative verification flags, increment explicit diagnostics counters (`workflowStats.backfilledOutcomeCandidates`, `interactionDiagnostics.backfilledOutcomeCandidates`), and never imply causal/server/gameplay verification.


- v30.6.30 legacy upload-lifecycle contract: manifest-readiness must distinguish legacy `unknown_legacy_manifest_snapshot` states by observed context (`local-multipart-export-observed`, `partial-local-multipart-export-observed`, `attempted`, `unknown`) with explicit status/blocker/next-action outputs, especially separating pre-upload placeholders from ambiguous post-upload lifecycle snapshots.



- v30.6.31 manifest-assisted ranking contract: when interaction events expose `observableOutcomeCandidate`, manifest-only target extraction should treat that as stronger bounded evidence than generic transition presence, surface it in generated Lua/JSON target metadata, and keep fail-closed claims (no causal/server/runtime/gameplay verification upgrades).
- v30.6.32 manifest-assisted metadata contract: when build-release emits `manifest-assisted-workflow.json`, include upload/readiness context (`transportReadinessStatus`, `transportReadinessBlockers`, `scriptGenerationReady`) so downstream tooling can separate upload-lifecycle blockers from evidence-interpretation limits without upgrading verification claims.

- v30.6.33 manifest-assisted Lua diagnostics contract: generated `LycolesManifestAssistedWorkflow.lua` should persist transport-readiness context (status + bounded blocker summary) in every rendered status view so manual bounded trials retain upload/readiness provenance context.

- v30.6.34 manifest-readiness evidence contract: emit `evidence.interactionCoverageDiagnostics` and fail-closed legacy blockers (`legacy_manifest_missing_outcome_candidate_field`, `explicit_outcome_candidate_events_unavailable`) when observable interaction changes exist without explicit outcome-candidate fields.


- v30.6.35 manifest-assisted output contract: `manifest-assisted-workflow.json` now uses schema `30.6.manifest-assisted-workflow.5` and includes `generationReadinessBlockers` plus `interactionCoverageDiagnostics`; generated `LycolesManifestAssistedWorkflow.lua` status views should display both transport and generation readiness/blocker summaries.

- v30.6.35 Lua blocker-summary ordering contract: bounded generation-blocker text must prioritize legacy outcome-gap and workflow-corroboration blockers so high-signal diagnostics remain visible even when blocker lists exceed display caps.




- v30.6.10 introduces FULL/QUICK scan profiles plus configurable observation delay and explicit cancellation/recovery. QUICK scans are targeted and must disclose profile-filtered omissions; they default to one auto-rescan. `PRODUCE SCRIPT` must force FULL profile capture so generation requests remain complete. Interaction diagnostics now include `workflowGenerationDiagnostics` root-cause blockers, and manifest-readiness accepts `upload-cancelled` snapshots without hiding partial ACK progress. Manifest-readiness now emits schema `109.manifest-readiness.3`; build-release manifest-only blocking must treat any `109.manifest-readiness.*` schema as non-release input.
- v30.6.11 strengthens functional interaction interpretation: context-scored feature attribution (name/text/ancestor/path), Bubble Gum-oriented menu hints, bounded context-token confirmation linking fallback, and default feature inference from unambiguous action kinds. This is evidence-ranking only: no new causality, runtime, server-authority, or gameplay verification claims.
- v30.6.12 extends action discovery with linked transaction outcome inheritance: when an initiating control has no direct scalar outcome, a later linked event in the same transaction can contribute resolvable state evidence (with explicit inherited-source provenance) so generation-readiness can cover confirmation-driven UI flows without introducing positive causality/runtime/gameplay claims.


- `tools/universal_gameplay_intelligence.py` now normalizes per-action `during.actionSource` (`user-input`, `tool`, `humanoid`, etc.) and bounded input metadata, and summary now includes `inputActionRecords` plus `actionSourceBreakdown`; preserve these when evolving downstream generation heuristics.

Current v30.5 action-discovery contract: `tools/compile_scan.py` retains at most 20,000 actionable Prompt/ClickDetector/GUI/Tool records with explicit truncation. `tools/discover_action_capabilities.py` may classify composable action surfaces and emit a reusable prompt runtime-trial target only from an exact observed `ProximityPrompt.Triggered` event plus at least one resolvable scalar state change. Interaction and outcome evidence should carry bounded class/name/sibling-ordinal identities; malformed, mismatched, or explicitly unavailable new identities cannot authorize generation. Event-time prompt prerequisite metadata must be normalized to the allowed text/enabled/duration/distance/input/anchor fields, preserve at most eight distinct snapshots with explicit drift status, and be revalidated by generation rather than overwritten or trusted implicitly. `tools/generate_prompt_interactions.py` ranks request-aligned and useful gameplay-objective candidates ahead of menu-like navigation, requires discovery's deterministically selected request/context-aligned scalar outcome when several signals compete, resolves identities before legacy flat paths, teleports only to the observed prompt hierarchy, checks prompt availability and executor-provided `fireproximityprompt`, monitors only the selected change direction, stops after three failures, and never invokes discovered remotes. Shared Admin Commands must expose generic `;interaction*` controls and compatible `;egg*` aliases with `;stopall` cleanup. `;interactionfeedback` may expose at most 100 attempt records bound to the exact action-capability digest; `tools/evaluate_prompt_trial_feedback.py` must accept only selected target/outcome contracts, independently recompute directional changes, reject unknown/forged claims, and retain authenticity, causality, server authority, runtime, gameplay, and action-outcome verification false. Auto and Multi game modes remain non-executable until their explicit live-observation blockers are resolved; names, temporal correlation, and operator-supplied feedback alone are insufficient. Passive `Tool.Activated` evidence and combat names remain discovery-only; generation additionally requires exact unambiguous LocalPlayer identity, one stable enabled prerequisite snapshot, and one selected resolvable scalar outcome before bounded official equip/`Tool:Activate()` trials are permitted.

Current guided GUI contract: normalize the same GUI prerequisite fields at scan and activation time: control class/text, Visible/Active/Selectable/AutoButtonColor/optional Interactable, ancestor visibility, ScreenGui enabled state, scrolling-frame intersection, and effective visibility. A generated `guided-gui-activation-trial` requires one exact unambiguous PlayerGui component identity, one complete stable available snapshot, and one selected resolvable scalar outcome. Generated Luau may highlight that exact control, observe the official `Activated` event, wait bounded time for normal user activation, and evaluate the selected outcome; it must not use `firesignal`, `VirtualInputManager`, `VirtualUser`, an invented `GuiButton:Activate()`, or classify this as automatic replay. Readiness and result validators must require `automaticActivation=false`, `manualActivationRequired=true`, and `exactControlHighlighting=true`. Hidden, disabled, off-scroll, malformed, ambiguous, incomplete, or drifted controls stay discovery-only.
- v30.6.13 manifest readiness adds `transportReadiness`, `evidence.uploadLifecycle`, and `evidence.workflowLinkageDiagnostics` so legacy manifests explicitly report unknown upload-attempt state vs failed upload state and provide one bounded `workflowCaptureRecommendation` without implying receiver or gameplay verification.
- v30.6.13 interaction linking expands bounded confirmation tokens (`yes/no/ok/accept/decline`), includes dialog cues (`prompt`, `purchase`, `unlock`), and allows conservative feature-default generic-control action inference (`shops→purchase`, `rewards/quests→claim`, `rebirth`, `travel`) to improve passive initiator capture for later confirmation linkage.

- v30.6.14 guided GUI contract allows text-only metadata drift when all non-text fields match across snapshots. Discovery marks this as `guiMetadataTextDynamic=true`; generator/runtime/planner may ignore text-only drift in matching but must continue fail-closed checks on control class, visibility/active/selectable, ancestor/screen visibility, scrolling bounds, interactable, exact path identity, and exact scalar state-outcome identity.

- v30.6.15 inspector may emit conservative non-confirm follow-up links: semantic actions within 6 seconds and context-token overlap >=3 can share a transaction (`observed-followup-link`) without any positive causality/runtime/gameplay claims. Diagnostics now include `linkedFollowups` and `linkedWorkflowEvents`; readiness/mapping should treat combined linked events (confirmations + followups) as linkage evidence.

- v30.6.16 manifest-readiness linkage diagnostics expose `linkedEvidenceType` (`none`, `confirmations-only`, `followups-only`, `confirmations-and-followups`) and `linkedWorkflowEvents`; downstream interpretation should use these fields for operator guidance while keeping existing blocker mappings backward compatible.

- v30.6.17 readiness guidance specialization: when linkage evidence is `followups-only`, manifest-readiness should recommend capturing one same-menu confirmation/cancel step with observable before/after values, rather than generic linked-action advice.

- v30.6.18 GUI discovery now classifies outcome evidence per target (`observableOutcomeEvidenceKind`: `resolvable-scalar` / `gui-transition-only` / `none`) and surfaces review-only candidates (`reviewOnlyTemporalOutcomeCandidate`, aggregate `reviewOnlyTemporalOutcomeCandidates`). These diagnostics must not increase generation readiness without resolvable scalar outcome identity evidence.

- v30.6.18 integration note: `tools/integrated_pipeline_v107.py` depends on `tools/action_registry_v107.py`; keep the runtime-evidence action registry, its unit test (`tests/test_action_registry_v107.py`), and CI workflow (`.github/workflows/v107-integrated.yml`) tracked together so clean checkouts retain v107 workflow-candidate and readiness summaries.
- v107 runtime evidence for `action_registry_v107` must reference canonical feature IDs from `feature_planner_v107` (e.g., `observe_0000`), not path-derived IDs; unknown IDs fail closed during generation/verification.
- `action_registry_v107` now reports `summary.workflowCorrelatedActions` and per-action `runtimeEvidence.completedWorkflowHits` / `partialWorkflowHits`; generation readiness can be `high` from completed workflow correlation even when an individual action has only one success sample.

Current v30.6.2 generation-readiness provenance contract: `tools/discover_action_capabilities.py` must normalize complete per-event baseline tuples fail-closed and aggregate pre-activation, activation-callback, and legacy-unknown counts independently for Prompt, Tool, and GUI targets. `tools/plan_generated_workflows.py` preserves independently validated timing on canonical steps; `tools/generate_guided_workflow.py` accepts same-schema legacy omission but rejects malformed present provenance. Generation readiness exposes target/workflow `observationBaseline` plus scan-wide `interactionObservationCoverage`; both are `limitations-only`, all verification claims remain false, and neither complete accounting nor pre-activation coverage may increase readiness or imply causality, complete state observation, runtime behavior, gameplay, authority, or authenticity. Current compiled summaries include `preActivationCaptureFailures`; older summaries may omit it. Generated-result and in-game loaders preserve same-schema legacy compatibility while independently validating any present bounded counts, classifications, loss claims, and workflow step totals before display.


Current v30.6 interaction-baseline contract: supported GuiButton, ProximityPrompt, and newly equipped Tool observations may capture bounded LocalPlayer scalar state, nearby GUI state, and character position from `InputBegan`, `PromptButtonHoldBegan`, or `Equipped` before the primary `Activated`/`Triggered` callback. Each history item, raw interaction event, and observation window must state `baselineSource`, `baselineTiming`, and `preActivationBaselineAvailable`; absent, stale, unsupported, or failed pre-captures use `activation-callback-fallback`, which explicitly implies possible synchronous evidence loss. Diagnostics must account for every scheduled 0.35/1.25/3.0-second window as completed, failed, or pending instead of hardcoding pending zero. `tools/compile_scan.py` and `tools/compile_interaction_sequences.py` must accept legacy reports as timing-unknown, validate all new timing/counter claims fail-closed, preserve per-feature/workflow timing coverage, and state loss limitations without upgrading temporal correlation to causality, server authority, runtime success, gameplay success, or action-outcome verification.


Current linked workflow contract: `tools/plan_generated_workflows.py` may classify a complete exact linked sequence as `mixed-guided` when any GUI step needs normal user activation or `bounded-automatic` when every step is an exact Tool/Prompt contract. `tools/plan_generated_workflows.py` ranks complete candidates by bounded normalized request terms matched against exact feature, action, label, path, and selected-outcome evidence, then readiness and lower required user involvement; `tools/generate_guided_workflow.py` independently recomputes selection scores and deterministically emits the highest-ranked eligible candidate, resolves exact identities, revalidates stable prerequisites, uses only normal-user GUI `Activated`, bounded official `Tool:Activate()`, and checked executor-provided `fireproximityprompt`, and stops at the first unavailable target, drift, failed activation, or unobserved selected scalar direction. Prompt workflow steps additionally require an enabled snapshot plus exact ancestor BasePart path, finite captured position, and activation distance; runtime anchor drift beyond 12 studs fails closed. The runtime must bind `115.guided-workflow-feedback.1` records to the canonical `114.generated-workflow-plan.1` SHA-256 and selected candidate, cap entries at 400, and keep clipboard, network, synthetic GUI activation, and discovered remote invocation unavailable. `tools/evaluate_guided_workflow_feedback.py` must independently validate exact candidate/step/outcome identities, contiguous entry order, increasing run order, terminal status semantics, scalar direction, and all-negative claims. `tools/aggregate_guided_workflow_feedback.py` may aggregate at most 100 uniquely identified sessions only after each passes that evaluator; recurrence, status conflicts, and scalar-type drift remain client-observation correlation. Generation readiness may describe the emitted linked workflow as a bounded request-aligned capability but must keep implementation readiness, source authenticity, causality, server authority, Roblox runtime, gameplay, and action-outcome verification false.

Workflow readiness must recompute the complete `114.generated-workflow-plan.1` from the compiled plan plus action capabilities and reject any byte-structural drift before projecting a generated capability. Expose only canonical matched request terms and their recomputed score. Selection transparency is bounded to 20 candidates, must retain the selected candidate, and classifies each alternative only as not ready, lower-scoring, more user-intensive, or a stable-identity tiebreak; generated UI shows at most three alternatives. Generation supports exact repeated mixed-action sequences through 64 steps; longer sequences remain review-only. Every emitted step binds its exact observed scalar entry value and fails before activation when that state has drifted. A generated session allows at most five operator-started attempts, cleans active highlights/connections on cancellation, and permits a later bounded retry without upgrading evidence claims. Inspector v30.5.2 accepts display-only mixed-workflow results only when the workflow selection, capability identity, execution mode, bounded steps, and all-negative claims agree; available feedback must be digest-bound to that selected candidate, remain at most 64 steps, and is summarized as informational client observation rather than execution proof. Controlled official-Luau coverage must exercise GUI→Tool→Prompt order, state-prerequisite rejection, cancellation recovery, and retry limits using normal GUI events, official Tool activation, bounded Prompt activation, and plan-bound feedback while retaining all live-runtime and gameplay claims as false.

Current request-feature-readiness compatibility contract: generated-result and release manifests must carry `generationReadiness.requestFeatureReadiness` exactly as emitted by `tools/assess_generation_readiness.py` when present, and fail closed on impossible claims. Generated evidence IDs in `requestFeatureReadiness.generatedEvidence` must equal the canonical `generatedCapabilities` IDs, matched IDs must remain a subset of generated IDs, and `implementationReady`/runtime/gameplay/causality/action-outcome claims cannot be promoted true. Request status and blockers are bounded to observed generated subset semantics (`generated-bounded-subset` / `evidence-only-no-replay-contract`) and explicit mode-selection blockers (`auto-game-mode`, `multi-game-mode`) until live replay contracts exist.

Current dynamic-overlay provenance contract: each complete observation scan must carry compiler-normalized source provenance whose scan/place/part identity matches that overlay and whose unsupported trust claims remain false. `source-provenance.json` describes only the baseline; overlay records stay separate in `capability-plan.json` and `evidence-overlay-provenance.json`, with a digest-linked release-manifest summary. Mixed source modes never imply source authenticity, causality, server authority, replayability, gameplay verification, or action-outcome verification.

## Generated features

- v30.6.3 workflow planning distinguishes all transaction groups from genuine shared multi-event links: a transaction ID present on one event is a singleton, not a linked workflow. Planning diagnostics/status are recomputed, cross-field validated, propagated as limitations-only readiness evidence, and displayed without changing causality/runtime/gameplay claims.
- v30.6.4 generated linked workflows offer operator-armed repetition capped at five sequences and 400 feedback records. Sequence one requires exact observed entry values; later sequences use the prior observed value keyed by the exact resolved state instance. STOP/CLOSE, identity/metadata/state drift, activation failure, or missing selected outcome terminates immediately.
- v30.6.5 appends an eligible `LycolesGuidedWorkflow.lua` source into the primary `LycolesGeneratedUtility.lua` in both generation paths while retaining the standalone file for review. Manifests/control inventories must agree through `integratedInGeneratedUtility` and `Linked Workflow Trial`; no eligible workflow means neither claim is present.
- v30.6.6 interaction records optionally carry validated `sessionId` and monotonic `sessionElapsedSeconds`. Observed/generated workflow plans may surface bounded adjacent unlinked pairs for review, but temporal proximity must never create a transaction, workflow candidate, causality claim, or execution readiness.
- v30.6.8 explicit workflow recordings are operator-armed, same-session, and bounded to 60 seconds/eight events. Their shared random ID and consecutive order express user intent only. Planner validation must reject malformed order, provenance, limits, timing, session, or non-false causality/runtime/gameplay claims; generation readiness still requires exact per-step contracts.
- v30.6.7 GUI reveal followups require an observed transition to visible, exact class/name/sibling-ordinal containment of the later normally activated control, matching same-session elapsed timing, and all-negative claims. They are bounded review episodes only and must not create transaction IDs, workflow candidates, automatic linkage, execution readiness, or causal/gameplay claims.

Each generated feature must define:

- Evidence source and stable provenance.
- Evidence classification and unknown boundaries.
- Implementation strategy.
- Runtime checks.
- Success conditions.
- Failure conditions.
- Accurate verification status.

Generate complete functional read-only/client-local behavior when evidence supports it. Fail closed instead of fabricating game-specific functionality when evidence is insufficient.

Current v110 gameplay-understanding contract: `tools/understand_gameplay.py` composes concurrent systems, observable resources, action candidates, temporal relationships, loop/objective candidates, automation opportunities, structured evidence gaps, and request blockers. `profileIndex` is the versioned provider-independent reference inventory: unknown discovered feature categories receive deterministic generic system IDs, path-and-component-identity-bound resource IDs prevent equal terminal labels or duplicate flat paths from colliding, every relationship/loop/objective uses canonical IDs, and bounded system truncation is explicit. It must not assign one genre, infer causality from chronology, invent action mechanisms, promote user request text into evidence, or mark implementation/runtime/gameplay/action outcomes verified. Explicitly absent features stay excluded.

Current generated command contract: every complete generated utility and reviewed-actions GUI includes the same place-guarded Admin Commands framework. GUI and `;` command entry share one local state and cleanup path. Universal commands are client-local utilities, not server administrator privileges; game restrictions may override them. `stopall`/close must restore tracked collision and humanoid state. `systems` and `readiness` are informational only: release/standalone generation may embed bounded v110 candidate and blocker summaries, while absent evidence must remain explicit and every system stays unverified/implementation-not-ready. Game-specific action commands may be added only with sufficient observed capability evidence and explicit action contracts. Never add inferred remote calls.

## Validation without target-game Studio access

Use layered validation:

1. Python and Node.js regression tests.
2. Luau syntax parsing and static/semantic contract checks.
3. Roblox API compatibility checks from versioned public definitions.
4. Synthetic hierarchy and gameplay-state fixtures.
5. Deterministic resolver-model tests.
6. Controlled Luau execution when safely and technically available.
7. User-supplied observations and results from permitted environments.
8. Regression fixtures derived from prior inspection reports.

Always label simulated/model/static success separately from actual permitted-environment runtime evidence. Studio-based testing may be used for separate authorized test experiences but is never a prerequisite for target-game milestones.

## Development cycle

For every substantial cycle:

1. Audit the current highest-impact evidence, functionality, or validation gap.
2. Add focused regression tests before implementation when practical.
3. Make minimal, versioned, backward-compatible changes.
4. Run focused tests, the complete Python suite, Node receiver/Luau tests, and `git diff --check`.
5. Resolve regressions and document failures, resolutions, limitations, and next priorities.
6. Commit verified changes on `openhands-development` with the OpenHands co-author trailer.
7. Push and verify exact local/remote commit SHA equality.
8. Update `OPENHANDS_PROGRESS.md` and begin the next highest-impact improvement.

Do not stop merely because one implementation commit is complete; finish its tests, documentation, progress record, push, and SHA verification.

## Current controlled Luau validation

- Install the hash-pinned official Luau `0.744` runtime with `python tools/install_luau_v108.py --output build/luau-0.744`.
- Run all Python tests with `LUAU_BIN="$PWD/build/luau-0.744/luau" python -B -m unittest discover -s tests -v`, then run `npm test` and `git diff --check`.
- `tools/controlled_admin_commands.py` executes actual `generate_admin_commands.py` output in bounded local stubs and verifies command/chat/GUI shared state, tracked cleanup, fly continuity across a simulated character replacement, deterministic output, and assertion-based place guarding. Its report must keep Roblox runtime, live-game, server-authority, and gameplay claims false.
- `tools/controlled_gui_activation.py` executes actual guided interaction output in bounded stubs and verifies exact identity resolution, highlighting, official `Activated` observation, selected scalar direction, drift/unavailable/timeout failure boundaries, cleanup, and the 25-attempt cap. It simulates user-event activation and must keep `automaticGuiActivationUsed`, Roblox runtime, server authority, causality, and gameplay verification false.
- Controlled Luau success is simulated, read-only evidence only; it never upgrades Roblox runtime, live-game, server-authority, causality, or gameplay verification claims.

## Live Bubble test preparation workflow (v30.6.36+)

- `tools/prepare_live_test_bubble_package.py` generates `build/live_test_bubble/` from a manifest plus manifest-assisted artifacts, including:
  - 18-target analysis table (`targets-18-analysis.md/.json`),
  - primary/backup workflow selection,
  - beginner operator checklist,
  - export/retrieval and post-test validation instructions.
- For the Bubble Gum INFINITY baseline package, run:
  - `python3 tools/prepare_live_test_bubble_package.py --manifest "Pasted text(20261102-152723).txt" --artifact-dir build/e2e_bubble_v108 --output build/live_test_bubble --place-id 85896571713843`
- `tools/validate_live_capture.py` validates returned live captures (manifest + optional parts directory), runs `build_release`, and emits machine-readable and markdown summaries:
  - `python3 tools/validate_live_capture.py --manifest <manifest.json> --parts-dir <parts_dir> --output <out_dir> --place-id 85896571713843`
- Validation summary explicitly separates available interaction history from inspector-reported total events (`events` vs `eventsReportedByInspector`) so subset histories are not misinterpreted as complete capture failure.
- Potassium/Roblox executors may fail on top-level lexical-local pressure before runtime (`Out of local registers ... exceeded limit 200`). v30.6.36 had 203 top-level locals even though official Luau disassembly stayed below register index 200; these are different compiler properties.
- Keep bounded-policy constants grouped under `LIMITS` and cohesive helper families inside lexical `do` scopes exported through namespace tables. Do not flatten `EVIDENCE_HELPERS` or `WORKFLOW_HELPERS` back into top-level local functions.
- Regression guard: `tests/test_inspector_compiler_limits.py` uses the official Luau AST to enforce root lexical pressure at or below 170, including active locals inside scoped modules, and compiles `LycolesUniversalInspector.lua` across every Luau 0.744 optimization/debug combination. Potassium remains live-unverified until user-confirmed `loadstring(source)` success.

## Dedicated generation service baseline

- `tools/lycoles_generation_service.py` is the current production-service boundary for evidence-to-script processing, separate from OpenHands conversation state.
- CLI:
  - synchronous job: `python3 tools/lycoles_generation_service.py run-job --evidence-kind <manifest|parts_dir> --evidence-path <path> --output-root <dir> [--requested-capability <text>]`
  - service mode: `python3 tools/lycoles_generation_service.py serve --host 127.0.0.1 --port 8787 --output-root build/generation-jobs`
- HTTP API (service mode):
  - `POST /v1/generation/jobs`
  - `GET /v1/generation/jobs`
  - `GET /v1/generation/jobs/{jobId}`
- The service currently uses deterministic pipeline artifacts (`build_release`, `generation-readiness`, `generated_result`) and keeps all authenticity/runtime/gameplay claims false.
- `tests/test_lycoles_generation_service.py` is the regression guard for manifest-blocked, multipart-generated, and async lifecycle flows.
- Receiver bridge: `tools/receiver_generation_pipeline.py`
  - local parts: `python3 tools/receiver_generation_pipeline.py from-parts --parts-dir <dir> --output-root <dir> [--requested-capability <text>]`
  - receiver fetch + generation: `python3 tools/receiver_generation_pipeline.py from-receiver --receiver-endpoint <https-origin> --scan-id <id> --output-root <dir> [--local-manifest <manifest.json>] [--resume-dir <dir>] [--requested-capability <text>]`
  - receiver mode requires `LYCOLES_READ_KEY` in the environment.
- Provider-backed generation environment knobs (server-side only):
  - `LYCOLES_LLM_PROVIDER=deterministic|openai|openai-compatible`
  - `LYCOLES_OPENAI_API_KEY` (or `OPENAI_API_KEY` fallback)
  - `LYCOLES_OPENAI_BASE_URL` (default `https://api.openai.com/v1`)
  - `LYCOLES_ANALYSIS_MODEL`, `LYCOLES_GENERATION_MODEL`, `LYCOLES_REPAIR_MODEL`
  - optional cost tracking: `LYCOLES_ANALYSIS_COST_GBP_PER_1K`, `LYCOLES_GENERATION_COST_GBP_PER_1K`, `LYCOLES_REPAIR_COST_GBP_PER_1K`
  - `LYCOLES_PREFER_AI_GENERATION=true` enables AI-first script synthesis when deterministic output is also available.
- Real Bubble Gum INFINITY dataset location/reference:
  - Source ZIP (main branch): `Lycoles_BubbleGum_Clean_Inspection.zip`
  - Scan identity: `scanId=AC79D385-BCB0-4928-85D5-6C3D960C44AE`, `placeId=85896571713843`, `partCount=1253`.
- Real-data compatibility note: `compile_scan.py` now tolerates invalid interaction `pathIdentity` by dropping mismatched entries instead of aborting the full scan; this was required for the verified live dataset.
- Gameplay-first generation refactor (2026-11-06): `generate_script.py` now emits a `Gameplay` tab with evidence-ranked action targets (`ACTION_TARGETS`) and bounded client-side activation attempts (`fireproximityprompt` for prompts, virtual input fallback for GUI buttons). Legacy `Features` tab is removed.
- Safety compatibility constraint: do not reintroduce `firesignal(` in generated Lua; `test_build_release` enforces this.
- `understand_gameplay.py` now outputs `mechanicCandidates` with ranked gameplay mechanics and publishes `summary.topAutomationMechanic`; profile index includes `mechanicCandidateIds`.
- `assess_generation_readiness.py` now computes per-feature `gameplayPriorityScore`, reports `summary.meaningfulGameplayFeatureMatches`, and emits blocker `no_meaningful_gameplay_feature_matches` when request matches are UI-only/low-value.
- Requested-capability propagation fix: `build_release.build(..., requested_capability=...)` can override compiled plan request (validated, fail-closed), and `lycoles_generation_service.EvidenceProcessor` now forwards `GenerationRequest.requested_capability` into `build_release.build`. This resolves prior `no-capability-requested` false negatives when pipeline callers supplied request text.
- Latest gameplay-first real artifacts:
  - `generated/live/BubbleGumInfinity_PipelineGenerated_GameplayFirst_v2.lua`
  - `generated/live/BubbleGumInfinity_PipelineGenerated_GameplayFirst_Requested_v2.lua`
  - `generated/live/BubbleGumInfinity_gameplay-understanding_v2.json`
  - `generated/live/BubbleGumInfinity_generation-readiness_gameplay-first_v2.json`
  - `generated/live/BubbleGumInfinity_generation-readiness_requested_v2.json`

- Universal discovery extraction (2026-11-06): `compile_scan.py` now emits `universalDiscovery` (`30.7.universal-discovery.1`) containing bounded `regions`, `interactables`, `economySignals`, `stateChangeSignals`, and `interactionPatterns` derived from full multipart objects plus interaction history.
- New intelligence artifact: `tools/universal_gameplay_intelligence.py` emits `111.universal-gameplay-intelligence.1` with `world`, `economy`, `actions`, `workflows`, and `relationships`; all verification/authenticity/causality claims are fail-closed false.
- Release integration: `build_release.py` now writes `universal-gameplay-intelligence.json`, records it in `release-manifest.json` under `universalGameplayIntelligence`, and includes summary counts in `README.txt`.
- Workflow diagnostics refinement in `LycolesUniversalInspector.lua`: `explicit-workflow-recording-not-armed` now triggers only when there is no linked/completed workflow evidence; diagnostics include `derivedWorkflowEvidenceEvents` to avoid recording-only false negatives.
- Regression coverage added:
  - `tests/test_compile_scan.py` now validates universal discovery schema and extraction of interactable/economy/state signals.
  - `tests/test_universal_gameplay_intelligence.py` validates analyzer output and deterministic `validate()` roundtrip.
  - `tests/test_build_release.py` verifies manifest/file integration for universal intelligence artifacts.

- Potassium compile headroom fix (`v30.6.38`): demoted six late UI declarations from local bindings to reduce top-level register pressure near the observation-control block where Potassium previously failed (`observationToggle` allocation). Local Luau text-compile register scan now peaks at `R154`.

