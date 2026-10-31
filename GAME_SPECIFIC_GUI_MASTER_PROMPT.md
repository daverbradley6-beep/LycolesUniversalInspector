# Universal Roblox Inspector → Game-Specific Script Master Prompt (Inspector v8.0+)

## Mission
Create a **complete, functional, game-specific Luau script with a polished GUI** using evidence collected by **Lycoles Universal Inspector**. This prompt is UNIVERSAL: never assume the target is Muscle Legends or that a fixed set of gameplay systems exists. Determine the target game from the latest inspection's placeId, gameId, gameName and user instructions. The user may execute via Potassium without Roblox Studio. Do not deliver a menu full of placeholder buttons or fabricate functionality.

## 1. Locate and verify the inspection
- Query the available Inspector connector for the **latest matching game and placeId**, including scan version, inspectedAt, sessionId, snapshotId, parentSnapshotId and scanRequestType. If the connector cannot retrieve the scan, use the supplied full inspection files; do not silently use another game or an older scan.
- Verify required-root coverage, rootAccountingValid, recorded/scanned/omitted counts, scan limitations and truncation. Distinguish startup-baseline from a manual post-interaction scan.
- Verify **multipart receiver acknowledgements and indexed parts** before calling an upload complete. A local manifest with partCount/expectedParts and uploadedParts=0 can be a pre-upload snapshot, not proof of upload success or failure. Report missing parts and retry when supported.
- v5.8 adds per-root ancestry-path caching; v5.7 adds more efficient report packing and exact-size validation; v5.6 improves inventory sampling and pagination attribution. These are implementation claims, not proof of in-game reliability or universal speedups.

## 2. Discover the actual game's systems
- Enumerate the **game's real systems**, not a predefined menu template: player stats, inventory/equipment, movement, navigation, interactions, tools, quests, rewards, pets, upgrades, shops, combat, NPCs, bosses, crafting, training, rebirth, events, or any other game-specific mechanics *only if present*.
- Inspect the complete relevant object records, not only the manifest. Map GUI control paths and labels, prompts, client-visible ValueBase state, safe attributes, replicated configuration, named controller/module candidates, world objects and remote names/paths.
- The Inspector is **read-only and client-visible**. It does not provide server-side source, module source, private remote arguments, authoritative server state, or proof that a named remote performs a specific action. Never invent any of these.
- Distinguish candidate name/path classification from directly observed events. Avoid false matches from unrelated telemetry/observability objects. `scanOrdinal` is scan-local, not a persistent identifier.

## 3. Build a per-feature evidence and feasibility matrix BEFORE coding
For every proposed feature record:
- Feature name, user-facing purpose, discovered instance paths, GUI/control context, expected action, prerequisites, relevant client-visible state and evidence source.
- Whether the action is client-controlled, server-authoritative, UI-only, or unknown.
- Evidence levels: **DISCOVERED** (name/path only), **OBSERVED** (normal user input captured), **STATE-CORRELATED** (client-visible changes nearby in time), **IMPLEMENTED** (real callback/code exists), **TESTED** (user or supported runtime test confirms the intended result). Track these independently.
- Confidence and failure modes; separate observed state from causal proof, server verification and actual feature success. `featureReadiness` and `featureEvidence` are navigational evidence, not implementation tests. `featureSnapshotDelta` compares candidate counts between successive scans, not gameplay outcomes.
- Prioritize features by feasibility and evidence, not by how impressive a menu looks. Never claim full support if the inspection cannot establish it.

## 4. Use v5.x interaction evidence correctly
- Inspect `interactionDiagnostics`: observer activation/enabled state, sweepCompleted/sweepScanned, listenersAttached, callbacksFired, attributed/unattributed events, bindingErrors, observationFailures, recentInteractions and workflowStats.
- Use `recentInteractions` with timestamps, sequence, transactionId, controlType, guiContext, featureCandidate, attribution, workflow phase, and the 0.35/1.25/3-second observation windows when present.
- Distinguish `stateChanges`, `guiStateChanges`, `travelCandidate`, `rewardClaimGuiCandidate`, `inventoryGuiCandidate`, `inventoryPageChangeCandidate`, `inventoryEvidenceKind`, and `inventoryOutcomeVerified`. A visible tick, claim label, menu closure, strength change, or player displacement is **not by itself proof** of a successful equip, claim, rebirth or travel.
- Inventory samples may be truncated, overlap concurrent actions, or use sibling-occurrence GUI identities that change after reordering. Do not treat selection, page changes or reused slots as confirmed inventory mutations. Inspect relevant before/after evidence and state the uncertainty.
- If observation is missing, guide the user to enable INTERACT, perform **normal gameplay actions**, run a manual SCAN, and provide the new report. Correlate by session/snapshot/sequence. Never claim that passive observation reveals unknown remote payloads.
- Ask for targeted interaction recordings when a particular function is unsupported, rather than endlessly rescanning the entire game.

## 5. Build a real, comprehensive script
- Produce a **complete Luau implementation**, not pseudocode, an empty framework, a UI-only mockup, or a list of proposed functions.
- Use the target game's actual available systems to create logical tabs and controls. Every enabled button/toggle must invoke real, supported behavior and provide status/error feedback. Do not create fake functions or misleading "success" notifications.
- Prefer documented, authorized client-visible controls and workflows. Respect server authority and game permissions. Do not invent remote signatures, brute-force remote arguments, or bypass paid items, access controls or server validation.
- Include reliable instance resolution with bounded waits, nil checks, character/respawn handling, GUI lifecycle and duplicate-execution cleanup, non-blocking operations, stop/pause controls, error isolation, sensible defaults, and restoration of changed client state on unload.
- Use throttling, bounded loops, cooldowns, cancellation, cleanup of connections/tasks and rate limiting for **stability and to avoid excessive traffic**. Do not market these as anti-ban bypasses or guarantee that a script cannot be detected or sanctioned.
- **Safety and anti-cheat:** Do not implement anti-cheat/anti-ban evasion, detection suppression, identity spoofing, log tampering, stealth hooks or security bypasses. Explain that no universal "undetectable" mode exists. Instead offer permission-respecting behavior, low-impact execution, transparent controls and a clear risk notice where appropriate.
- If a feature is technically unsupported or requires authority unavailable to the client, **omit it from enabled controls** and document it in an explicit limitations section. Do not substitute simulated effects for real gameplay outcomes.
- Keep the implementation modular and adaptable, but do not assume identical game mechanics across Roblox experiences.

## 6. Verify and publish
- Audit every enabled control: callback wired, dependencies available, action logic present, errors handled, stop/unload works. Include a **feature-by-feature test table** showing source evidence, implemented state, and tested/untested status.
- Perform static consistency checks and reason through state transitions. Do not claim Potassium runtime validation, successful gameplay outcomes, or ban safety without actual evidence.
- If the user requests publication, use their specified game-specific GitHub repository; inspect existing files before replacing them, use current blob SHAs, update README/version as appropriate, verify the committed source, and provide the exact raw GitHub loadstring. Do not publish to the Inspector repository as though it were the game-specific script repository.
- For large scripts, keep all required modules accessible and loadable, avoid truncated outputs, and verify entrypoint dependencies. Preserve existing working features on subsequent revisions.
- On failure, request the precise control, expected/actual behavior and runtime error or relevant observation. Fix the implementation based on evidence, then repeat tests.

## 7. Required deliverables
A. Correct game and scan identity, coverage and multipart verification.
B. Discovered systems inventory and feature-by-feature evidence/feasibility matrix.
C. Implemented functions, omitted/unsupported functions and reasons.
D. Complete, runnable Luau source with a functional GUI (and verified GitHub loadstring if actually published).
E. Test checklist with each function explicitly marked **untested**, **passed**, **failed**, or **blocked**; never turn inference into a pass.
F. Performance/stability considerations, known risks and next targeted observation requests.

**Priority:** working functionality > evidence accuracy > stability > UI polish > feature count. A universal Inspector enables discovery across games; it cannot automatically guarantee a working implementation for every game or bypass server-enforced behavior.


## v6.0 — Automatic Evidence and Release Gate

- Use the newest matching inspection and compare baseline with automatic post-interaction reports. The inspector enables passive observation automatically and schedules bounded scans after gameplay interactions settle.
- A complete multipart upload is **not** proof of a complete searchable index. Verify indexed unique objects, duplicates, scan part counts, and missing roots independently. If indexing coverage is insufficient, block feature claims and report the precise receiver defect.
- Distinguish client-visible UI state from the game's own controller callbacks. Never invent instance APIs or claim that changing a GUI's Visible property invokes gameplay logic. GuiButton.Activated is an event, not an invocable method.
- Inventory every feature before implementation. For each, record the observed operation, dependencies, permitted client implementation, expected observable result, and confidence. Implement only where evidence supports a working approach.
- A successful static check or GitHub upload is not a live Roblox test. Report these stages separately: discovered, observed, implemented, static-checked, live-tested, confirmed.
- Prefer a substantial implementation batch to incremental GUI mockups. No placeholder gameplay buttons; unavailable features should be described in the release report rather than masquerading as working controls.
- A client-only read-only inspector cannot guarantee reproduction of server-authoritative mechanics, and should not inspect inaccessible scripts, bypass protections, intercept private data, or forge network operations.
- If the user's aim is minimal manual effort, request a single representative normal gameplay session covering multiple systems, not repeated one-feature-at-a-time debugging. Automatic evidence capture should run throughout that session.


## v7.0 — Receiver Integrity and Automated Release Gating

Before generating game-specific Lua, obtain the scan ID from the inspection report and verify multipart receiver integrity. A scan is not implementation-ready merely because uploads were acknowledged. Verify expected versus received parts, expected versus indexed objects, duplicate keys, and whether interaction history was retained. The reference Cloudflare Worker exposes GET /reports/READ_KEY/SCAN_ID/integrity and /manifest after deployment.

Produce a game-specific capability matrix in one batch from all available evidence. Separate observed gameplay outcomes from repeatable client-side implementations. Do not fabricate network calls, GUI activation methods, or protected/server behaviour. Prioritize a complete, coherent release over piecemeal GUI mockups. Generate executable modules only for supported and permitted operations; unimplementable features belong in the report, not decorative buttons.

Review the Lua source for syntax, API usage, lifecycle cleanup, and dependency failures before GitHub upload. GitHub verification proves deployment, not gameplay functionality. State explicitly when a runtime test is unavailable. Use one representative user gameplay session with automatic passive recording rather than asking for dozens of individual feature tests.

The reference receiver must be deployed separately to Cloudflare. Updating its GitHub source alone does not update the running Worker or the connected Inspector plugin backend. Never claim live indexing is repaired until the deployed service reports integrity success.


## v8.0 — Automated Scan Compiler Gate

When scan parts are available as JSON files, run `python3 tools/compile_scan.py PARTS_DIR --output build`. Require a successful exit before using evidence for implementation. Read `build/capability-plan.json` and `build/capability-plan.md` to inventory all feature candidates in one batch. The compiler rejects missing or conflicting multipart uploads, inconsistent object counts, duplicate identities and incomplete source scans. It does not claim that observed controls can be replayed or that arbitrary server actions are implemented. Never generate empty buttons or invent remote calls to fill feature gaps. If the compiler blocks, report the single concrete data defect and fix ingestion before generating code.
