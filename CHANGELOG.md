## v27.0.0 — Evidence-driven contract drafting

- Generate review-required, read-only client action candidates from validated class inventories.
- Include contract-draft.json in offline releases and count candidates in the manifest.
- Preserve explicit review and prohibit automatic promotion to gameplay automation.
- Add regression tests for class evidence, missing evidence, and invalid scans.

## v25.0.0 — Evidence-backed implementation backlog

- Compile per-workflow implementation candidates from validated scan and observed interactions.
- Correlate optional client observation feedback without claiming executable gameplay support.
- Include implementation-backlog.json in the offline release ZIP and candidate count in its manifest.
- Fix duplicated trailing source in interaction sequence compiler.
- Add regression tests for provenance and fail-closed validation.

## v23.0.0 — Runtime report export

- Generated read-only verification harness exports schema-compatible JSON from before/after client snapshots.
- Require baseline capture before report export.
- Expand regression tests for report generation.
- Report transfer and gameplay execution remain manual.

## v22.0.0 — Runtime feedback evaluation

- Add optional runtime feedback report ingestion to offline releases.
- Validate report Place ID, check identities, expected leaderstats keys and duplicate submissions.
- Produce structured before/after comparison statuses without automatically approving gameplay automation.
- Add regression tests for valid and invalid reports.

## v21.0.0

- Generate manual read-only before/after verification plans from observed leaderstats transitions.
- Package an optional place-guarded Lua verification module.
- Add source-level tests; no live runtime validation or gameplay automation claimed.

## v20.0.0 — Observed interaction workflow compiler

- Preserve bounded client interaction history in compiled scan plans.
- Generate `observed-workflows.json` with transaction-linked steps and state transitions.
- Keep unlinked events separate and preserve explicit non-executable status.
- Add tests for event linking, state evidence and malformed/incomplete input.
- No automatic remote replay, gameplay automation or anti-cheat guarantees.

## v19.0.0 — Evidence-driven proposal stage

- Every offline release now includes `action-proposals.json` with evidence-based read-only client action suggestions.
- Class inventory gates suggestions for leaderstats, PlayerGui and proximity prompt discovery.
- No suggestion is approved or executable without separate contract review.
- Added negative and positive regression tests for proposal integrity.
- Automatic server-side gameplay script creation remains unsupported.

## v18.0.0 — Reviewed action GUI generation

- Added `tools/generate_actions_gui.py` to create an executable ScreenGui with buttons directly connected to generated reviewed client functions.
- Includes error feedback, bounded result display, close/cleanup and Place ID protection.
- Release builder packages `LycolesReviewedActionsGUI.lua` only when validated contracts exist.
- Added tests for action wiring, empty contracts and unreviewed contracts.
- Not a gameplay exploit generator; live Roblox runtime verification still required.

## v17.0.0 — Generated read-only Lua implementations

- New `tools/generate_client_actions.py` emits actual place-guarded Lua functions for three explicitly reviewed client action types.
- Release builder includes `LycolesClientActions.lua` when reviewed contracts are supplied.
- New regression tests verify generated functions and reject unreviewed, unsupported and wrong-scope actions.
- Server gameplay actions, remote calls, anti-cheat bypasses and live verification are not supported.

## v16.0.0 — Verified dynamic evidence fusion

- Added `tools/merge_observations.py` to combine full baseline capability plans with separately validated dynamic observation scans.
- Added repeatable `--observation` folders to release builder and provenance counts to manifest.
- Reject duplicate scan IDs, incomplete scans, cross-game observations and dynamic-only baselines.
- Added evidence fusion regression tests.
- The feature evidence overlay is additive; overlapping repeated observations may double-count events. Runtime and gameplay functionality remain unverified.

## v15.0.0 — Reviewed client action contracts

- Added `tools/validate_contracts.py` to validate explicitly reviewed, place-bound, read-only client action contracts against features discovered in a complete scan.
- Added optional `--contracts` to the release builder; validated contracts are packaged with a count in the release manifest.
- Added tests for approval, unreviewed contracts, unsupported actions and mismatched places.
- This is a conservative implementation-contract stage. It does not infer or execute server gameplay actions and does not bypass anti-cheat.

## v14.0.0 — Evidence-ranked implementation review and UI clearance

- Add `implementation-review.md` to each generated release bundle, ranking candidate game features by observed evidence.
- Include concrete validation requirements for each discovered feature instead of treating candidates as implemented.
- Reserve inspector header space for the minimise button, align title left and move AUTO EVIDENCE further below INTERACT.
- Update workflow and UI regression tests and release manifest version.
- Limitations: client-only gameplay evidence; no guaranteed arbitrary-game automation; in-game visual check pending.

## v13.0.0 — Universal Workflow Evidence Compiler

- Added `tools/compile_workflows.py` to turn validated inspection capability plans into structured per-feature workflow evidence specifications.
- Distinguishes discovery, observed interaction, temporal state transition, client corroboration and observed client outcome.
- Integrates `workflow-specs.json` into one-command release ZIPs, including evidence summary in the release manifest.
- Adds regression tests and aligns the inspector version.
- Gameplay execution remains unimplemented without validated action contracts; Roblox runtime remains unverified.

## v12.0.0 — Inspector UI and Upload Reliability

- Fixed AUTO EVIDENCE button overlapping the title/minimise button by moving it into a dedicated sidebar.
- Resized report output to avoid overlapping sidebar controls; added clear evidence-rescan and receiver-ack hints.
- Clarified that upload part ACKs do not independently verify the receiver's final multipart integrity.
- Guarded first-part JSON decoding against malformed data; improved partial-upload retry progress messaging.
- Added automated UI/layout/source regression tests.
- Still not implemented: unlimited lightweight interaction delta capture, deployed receiver validation, or automatically functional server gameplay scripts.

## v11.0.0 — Real-Scan Compatibility and Receiver Integrity Hardening

- Compiler now accepts actual inspector multipart format: dedicated metadata, separate interaction history, object parts, optional manifest.
- Preserve client-corroborated interaction evidence, temporal transitions and feature readiness in capability plans.
- Reject malformed objects, incomplete source diagnostics and inconsistent object counts.
- Receiver now rejects conflicting duplicate uploads and inconsistent scan metadata, handles byte-size checks, and verifies strict multipart object accounting.
- Add Python real-schema regression tests and Node receiver integration tests to GitHub Actions.
- Scope: inspector's live observation and four-full-rescan cap remain unchanged; receiver must be deployed separately; gameplay automation is not automatically inferred or runtime verified.

## v10.0.0 — One-command Release Build and CI (experimental)

- Add `tools/build_release.py` for a single scan-parts-to-Lua release build.
- Add structural source checks, explicit place guard, SHA-256 manifest, deterministic ZIP archive.
- Add end-to-end regression tests for release reproducibility and fail-closed behaviour.
- Add GitHub Actions CI workflow for Python compilation, regression tests and sample artifact upload.
- Preserve clear distinction between client diagnostics and unsupported server gameplay automation.
- Not yet verified: GitHub Actions run status, Roblox runtime behaviour, deployed receiver, automatic publishing to game-specific repositories.

## v9.0.0 — Deterministic Client Utility Generation (experimental)

- Add `tools/generate_script.py` to convert validated v8 capability plans into place-specific Roblox Lua utilities.
- Generate functional client diagnostics (numeric stats, UI catalog, proximity prompts, discovered-feature inventory), with cleanup and place guard.
- Add SHA-256 release manifest with explicit untested/client-only status.
- Add generator regression tests including malformed input and injection-resistant feature strings.
- Scope limit: no automatic implementation of server-authoritative gameplay; no live Roblox test yet. Source is committed to GitHub but not deployed to a game.

## v8.0.0 — Automated Scan Compilation (experimental)

- Add stdlib-only offline multipart compiler: `tools/compile_scan.py`.
- Validate all parts, identities, duplicate objects, scan completeness and recorded object totals.
- Generate a full feature candidate inventory and machine-readable implementation release gate in one run.
- Add regression tests for complete scans, missing parts, conflicting identities and duplicates.
- Update universal prompt to require compilation before implementation.
- Limits: source is committed but not tested in Roblox; receiver deployment remains separate; capability planning is not automatic gameplay code generation.

## v7.0.0 — Multipart Integrity & Automation Foundation (experimental)

- Rework reference Cloudflare Worker to accept inspector multipart scan uploads with matching acknowledgements.
- Persist parts idempotently by scan ID and part index; expose scan metadata, individual parts, and integrity reports.
- Validate part identity in Lua before upload and include full diagnostics in metadata parts.
- Clarify upload acknowledgement versus receiver indexing verification.
- Strengthen universal master prompt with an integrity gate and batch-first development policy.
- Deployment note: Worker source must be deployed to Cloudflare separately. Connected inspector backend and Roblox runtime have **not** been updated/tested by this commit.
- Limitation: client-visible inspection cannot guarantee full automation of arbitrary server-controlled game mechanics.

## v6.0.0 — Automatic Evidence Collection (experimental)

- Enable passive interaction observation at startup.
- Add auto-evidence toggle, activity-settling timer, cooldown and four-scan cap.
- Include automatic evidence diagnostics in scan manifest and report.
- Add strict script-development evidence gates to master prompt.
- Known limitations: not runtime-tested in Roblox; receiver indexing coverage must be validated independently; client observations cannot prove server behaviour.

## 5.8.0 — Faster full hierarchy traversal
- Cache computed ancestry paths within each scan root to avoid repeatedly traversing common parent chains.
- Reset cache between roots to retain root-specific path labels and duplicate-root handling.
- Preserve existing object records, metadata, occurrence disambiguation, interaction observation, and multipart export schema.
- Runtime performance gains are pending in-game measurement.

## 5.7.0 — Faster lossless report preparation and pagination attribution
- Replace repeated growing-history JSON serialization with linear incremental size estimates; retain exact-size final validation and splitting.
- Increase object chunk packing target from 85 KB to 96.5 KB within existing 105 KB part limit, retaining all recorded objects.
- Detect pagination from parent PreviousButton/NextButton/PageButton controls as well as direct control names.
- Keep pagination visibility changes distinct from inventory mutation candidates.
- Preserve full read-only scan and multipart export; no lossy object compression or evidence removal.
- Runtime timing and export compatibility need in-game verification; scan traversal itself is not materially changed.

## 5.6.0 — Faster GUI candidate sampling and action-aware inventory evidence
- Avoid expensive GUI ancestry/path construction for non-inventory candidates.
- Distinguish pagination and selection from equipment actions when interpreting inventory GUI changes.
- Report inventoryPageChangeCandidate and inventoryEvidenceKind separately from inventoryGuiCandidate.
- Correct misleading pendingObservationEvents label; preserve cumulativeChangeEvents diagnostic.
- Preserve full read-only object scanning and complete multipart export; no object-data omission introduced.
- Full export size is not yet reduced; performance improvement is primarily inventory observation CPU time.
- In-game runtime validation pending.

## 5.5.0 — Unique inventory GUI identities and compact evidence
- Use full relative GUI ancestry and sibling occurrence indices for unique inventory slot/indicator identities.
- Restrict inventory sampling to inventory/pet GUI contexts and inventory-related interactions.
- Fix false sample-appeared transitions caused by duplicate keys.
- Export compact before/after counts and only actual per-object changes, rather than repeating entire snapshots.
- Preserve read-only client-side evidence and scan truncation diagnostics.
- In-game runtime and multipart export still require testing.

## 5.4.0 — Per-indicator inventory and pet evidence
- Record bounded client-visible GUI slot and equipped-indicator samples with relative paths and visibility.
- Compare before/after individual GUI indicator and slot samples, not just aggregate counts.
- Distinguish unequip-all and unequip from equip in action classification and state evidence.
- Explicitly flag overlapping interactions and distinguish GUI candidates from verified inventory outcomes.
- Preserve read-only operation, bounded sample sizes and client-only verification limits.
- In-game execution and export still require testing.

## 5.3.0 — Inventory discovery and transaction evidence
- Discover client-visible inventory slot and equipped indicator counts in PlayerGui, in addition to ValueBase roots.
- Preserve before/after inventory coverage summaries for interactions.
- Deduplicate repeated state transitions across linked initiation/confirmation events using transaction identifiers and bounded signatures.
- Distinguish unlinked travel confirmations from generic unlinked confirmation actions.
- Recognize the Items navigation control.
- Keep server verification and causality explicitly unproven; in-game runtime and receiver testing required.

## 5.2.0 — Large evidence quality batch
- Deduplicate repeated state and GUI changes across the 0.35/1.25/3 second observation windows.
- Count unique changes rather than repeatedly attributing the same state transition.
- Record travel displacement candidates and reward-claimed GUI candidates separately from verified outcomes.
- Recognize travel confirmation as an unlinked contextual workflow when no initiator is observed.
- Add bounded inventory/pet/equipment value coverage diagnostics to interaction records.
- Preserve read-only client-only evidence and server-verification disclaimers.
- Runtime and multipart receiver compatibility still require testing.

## 5.1.1 — Oversized JSON export hotfix
- Separate scan summary and large interaction history into dedicated bounded upload parts.
- Split oversized history and object parts recursively rather than failing the entire scan.
- Preserve full interaction event evidence where it fits; exceptionally oversized individual events use compact summaries.
- Multipart receiver compatibility and in-game export require testing.

## 5.1.0 — Major interaction evidence batch
- Fix rebirth ConfimButton matching and improve feature-matched confirmation/cancellation linking.
- Prefer pet-specific and travel menu context over generic control names.
- Add three observation windows (0.35, 1.25, 3 seconds), tracking numeric state, GUI transitions and character displacement.
- Detect added and removed sampled values and export bounded action-specific evidence.
- Expand diagnostics for state corroboration, observation windows and errors.
- All evidence remains read-only, heuristic and client-visible; in-game verification required.

## 5.0.0 — Major evidence and workflow update
- Link generic confirmation and cancellation interactions to recent candidate actions within a bounded 12-second window.
- Track workflow initiations, inferred confirmations, cancellations and expired pending actions.
- Expand read-only numeric/boolean player-state sampling from 300 to 1000 values.
- Record nearby GUI elements appearing and disappearing, in addition to visibility and Active changes.
- Expand recent interaction history to 180 and expose workflow diagnostics.
- Correct scan invocation accounting to count only accepted scan requests.
- All workflow links remain heuristics; no server-side verification or remote invocation.
- In-game runtime validation remains required.

## 4.7.7
- Add bounded nearby GUI state snapshots for observed interactions.
- Record visibility and Active transitions without collecting text or input contents.
- Export GUI transition evidence separately from numeric state changes and verified outcomes.
- Preserve passive read-only inspection and existing feature evidence checks.

## 4.7.6
- Add menu-context hints for generic buttons in known gameplay menus.
- Add feature-specific client-state corroboration for rebirth and training.
- Keep corroboration separate from independent server verification.
- Fix feature readiness unattributed interaction count to reflect actual unattributed events.

## 4.7.5
- Capture ancestor names, ScreenGui enabled state, and visible GUI ancestors at interaction time.
- Increase bounded client-state snapshot to 300 values with hierarchical paths to reduce key collisions.
- Mark event evidence levels separately from unverified gameplay outcomes.
- Retain read-only observation and no remote invocation.

## 4.7.4
- Classify observed controls by their own names or up to six ancestor names.
- Correct attributed and unattributed interaction counters.
- Retain a bounded 60-event interaction history with paths, timestamps and candidate features.
- Attach observed client-state deltas to their corresponding history records.
- Export recent interaction evidence in the scan manifest; no causal verification implied.

## 4.7.3
- Label startup baseline and manual scans in interaction diagnostics.
- Add scan invocation count and observerReady status to exported manifest.
- Display observer activation count in INTERACT toggle and scan type/readiness in scan status.
- Interaction capture remains subject to live validation.

## v4.7.2
- Track observer activation/deactivation, timestamps, callback activity, sweep start/completion and errors.
- Show observer callback and sweep status in the scan output; explicitly instruct users to scan again after gameplay.
- Diagnostic changes do not prove that game actions were captured or verified.

## 4.7.1
- Explicitly attach listeners to existing PlayerGui buttons when INTERACT is enabled.
- Export observer diagnostics in the manifest and first multipart scan part: listener count, callback count, state-delta count, binding errors, sweep status, and pending events.
- Read-only observation retained. Runtime verification and receiver indexing remain pending.

## 4.7.0
- Add conservative control-name feature attribution for manually activated controls.
- Capture bounded local numeric/Boolean state before and 0.5 seconds after manual interactions, without reading text fields.
- Record temporal state-change evidence without asserting causality or server verification.
- Reflect observed interactions and possible state changes in feature readiness; implementation and testing remain unverified.
- Preserve interaction and state-delta events on multipart preparation retry.
- No runtime test yet; receiver indexing of new fields remains to be verified.

## 4.6.0
- Add per-feature implementation readiness records (discovered, observed, implemented, tested), with conservative default false for unverified stages.
- Add successive-scan feature-candidate count deltas. These are not causal before/after gameplay verification.
- Include readiness and deltas in saved manifest and first multipart upload part.
- Preserve v4.5.1 token matching and upload byte diagnostics.
- Not implemented in this release: guided interaction labeling, feature-specific state-change verification, GUI/controller behavioral mapping, verified formulas, or executable regression tests. Runtime test required.

## 4.5.1
- Token-aware feature detection splits PascalCase and camelCase object names and avoids matching `quest` inside `Request`.
- Include `localPerformance.uploadBytes`, `uploadParts`, and `serializationSeconds` in the saved JSON manifest for measurable multipart size comparisons.
- Preserve read-only scanning and existing multipart upload behavior; Potassium runtime test pending.

## 4.5.0
- Restrict feature evidence to object names instead of full ancestor paths to reduce false-positive classifications.
- Limit feature examples to six per category and shorten example paths to reduce repeated upload metadata.
- Preserve v4.4.1 multipart byte validation and first-part-only summary metadata.
- Add GAME_SPECIFIC_GUI_MASTER_PROMPT.md integrating the new evidence rules and game-specific GUI workflow.
- Requires live Potassium test; receiver deployment unchanged.

## 4.4.1
- Validate every multipart payload against the actual encoded byte size and split oversized object chunks.
- Send scan-wide counts, diagnostics and feature evidence only in the first part to avoid repeated metadata.
- Add scan-local ordinal identifiers; these are not stable across sessions.
- Preserve read-only inspection and existing acknowledgement/retry handling.
- Receiver indexing changes and Potassium runtime verification are not included.

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

# Changelog

## 4.1.0
- Added multi-label system classification and semantic ValueBase roles.
- Added parent/ancestor context and bounded sibling value relationships.
- Improved controller candidate and GUI control metadata.
- Added per-root coverage and per-class/configuration/GUI/script diagnostics.
- Excluded PlayerGui and Character from duplicate LocalPlayer-root captures.
- Replaced unconditional complete=true with required-root and object-accounting validation.
- Retained read-only behaviour, multipart delivery, acknowledgements and retry logic.

## 4.0.0
- Added universal client-visible root inspection, bounded metadata, GUI and interaction observation, dynamic discovery, and multipart reporting.
