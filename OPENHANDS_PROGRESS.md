# OpenHands Development Progress

_Last updated: 2026-11-02 — v30.1 live evidence and v109 manifest readiness cycle_

## Repository State

- Workspace: `/home/openhands/workspace/project/e716d1c75342477e819d44e14ce33441`
- Branch: `openhands-development`
- Latest implementation commit: `c721d40` (`Preserve outcome candidates in workflow compilation`)
- Implementation head: full SHA `c721d40c18587fdadae19a7f0480d6d0e4251f00`; the previously published handover head `fc51c4af7619587439fb1809a3fb8600212e11c9` was confirmed byte-for-byte on `origin/openhands-development` before this cycle
- Implementation snapshot relative to `origin/main`: **24 commits ahead, 0 behind**
- All **18** workflows triggered for pushed head `fc51c4a` completed successfully
- The supplied recovery handover and raw live manifest remain local, untracked inputs; only the sanitized regression fixture is committed
- Follow-up progress-only commits intentionally do not embed their own self-referential SHA
- Remote policy: push only `openhands-development`; never modify or merge `main`

## Changes Implemented

1. `2421342` — aligned three stale tests with intended current contracts:
   - Inspector version consistency now follows `version.txt` and the Lua header.
   - v82 retains fail-closed handling instead of generating invalid `GuiButton:Activate()` calls.
   - v54 coverage follows bounded batch streaming, change-only updates, and legacy receipt parsing.
2. `2a9d86c` — refreshed release and safety documentation:
   - README now distinguishes the v30 inspector/release line from the v106 staged integrated pipeline.
   - Corrected v54 transcript markers and obsolete v82–v84 activation claims.
3. `740738c` — added parser-level Luau validation:
   - Reusable WebAssembly tree-sitter validator and CLI.
   - Locked Node dependencies and script-free installation instructions.
   - Tests reject malformed input and parse checked-in plus representative v54/v82/v104/v106 generated Luau.
   - GitHub Actions runs receiver and Luau syntax validation.
4. `d48c6ab` — strengthened v106 object identity:
   - Feature plans preserve terminal `className` evidence.
   - Emission rejects mismatched class/property contracts.
   - Generated Luau resolves terminal objects by both name and class and fails closed on mismatch.
   - Diagnostics and static contracts verify exact class mapping; four new regression tests cover the behavior.
5. `ccd4dda` — introduced the versioned v107 full-path identity contract:
   - Canonical `{name,className,ordinal}` identity for every segment, including explicit service roots.
   - Deterministic preservation of duplicate names with distinct sibling ordinals and rejection of exact identities.
   - Compatibility with v55 segments, v72/v74 unique paths, direct canonical segments, and legacy name-only paths.
   - Validated one-way v104 migration without fabricating missing identity evidence.
   - Added 15 focused tests and documented schema guarantees and dynamic-hierarchy limits.
6. `7b3a486` — integrated complete path identity through v107 generation:
   - Feature planning and validation preserve canonical segment identities and resolution modes.
   - Generated Luau resolves every rich segment by name, class, and same-name/class sibling ordinal.
   - Migrated name-only paths require a unique child at every segment and fail closed on ambiguity.
   - Quality and diagnostics report full-identity versus legacy-resolution coverage.
   - Artifact verification reconstructs canonical reports, plans, diagnostics, quality, Luau, hashes, and identity counts.
   - Added 15 end-to-end tests and generated-v107 Luau parser coverage.
7. `540f5dc` — strengthened deterministic source and artifact verification:
   - Independently parses canonical Luau runtime feature entries instead of trusting hashes or generated-plan bytes alone.
   - Compares IDs, labels, paths, every identity segment, resolution modes, classes, properties, and place guard to the plan.
   - Rejects duplicate/noncanonical runtime entries, extra artifacts, extra manifest fields, malformed hashes, and noncanonical manifest bytes.
   - Added 10 focused tamper and strict-contract tests.
8. `a6a931b` — added a bounded controlled resolver model:
   - Evaluates validated v107 feature plans against strict synthetic hierarchy fixtures.
   - Exercises class-qualified ordinals, legacy uniqueness, place guards, and property availability.
   - Enforces depth, node, child, field, scalar, and canonical service-root bounds.
   - Labels results `modelVerified` while explicitly keeping Luau execution, Roblox runtime, and gameplay verification false.
   - Added 10 focused deterministic and fail-closed model tests.
9. `3810947` — made v107 features explicitly evidence-backed:
   - Added authoritative root `AGENTS.md` guidance for third-party, client-observable development without target-game Studio ownership.
   - Introduced `107.feature-plan.2` with canonical observation-object digests, observed facts, bounded inferences, implementation strategy, runtime checks, success/failure conditions, and explicit unknowns.
   - Preserved strict `107.feature-plan` validation and identical Luau emission, plus report-bound deterministic v1-to-v2 migration.
   - Added evidence/status/contract/unknown coverage to quality and diagnostics artifacts.
   - Updated current README and v107 documentation to remove ownership-dependent validation prerequisites.
   - Added 10 focused provenance, tamper, diagnostics, and migration tests.
10. `9b3bfbd` — added static compatibility against Roblox's public API definitions:
   - Pinned official `QTStudio` dump version `version-d0e8cfcd943d4ae2` and its full source SHA-256 in a bounded 41-member canonical snapshot.
   - Added reproducible hash-verified extraction, strict snapshot validation, inheritance-aware member ownership, member-kind checks, public access checks, and read-only write rejection.
   - Covers every v107 runtime class member and all 12 supported feature class/property reads; globals outside API-dump class members remain explicit assumptions.
   - Added fail-closed emitted-source token accounting so new or missing member references cannot silently outrun the contract.
   - Integrated deterministic `api-compatibility.json` generation, manifest hashing, reconstruction, and tamper verification.
   - Added 10 focused source, access, inheritance, snapshot, compatibility, and artifact tests.

11. `3e4c61e` — published the accumulated v107 evidence-cycle progress record:
   - Consolidated path identity, semantic artifact verification, resolver-model, feature-provenance, and public-API compatibility results.
   - Recorded test counts, limitations, encountered problems, and the controlled-execution priority without changing runtime behavior.
12. `45fb3a6` — added v108 controlled actual-Luau execution:
   - Added a hash-pinned installer for the official Luau `0.745` Ubuntu release, with a 10 MB download cap, exact four-file archive contract, path/target safety checks, and archive plus per-executable SHA-256 verification.
   - Runs instrumented generated v107 Luau in the trusted official CLI with wall, CPU, address-space, output, file, descriptor, environment, and total-source bounds.
   - Implements strict local Roblox stubs, drives refresh/filter/auto-refresh/unload UI paths, captures deterministic transcripts, and compares class-qualified and legacy resolution with the independent model.
   - Preserves explicit evidence boundaries: simulation is read-only; Roblox runtime, live-game, server-authority, causality, and gameplay verification remain false.
   - Added canonical UTF-8 Luau byte escaping and independent strict decoding for Unicode paths, identities, labels, and values; identity admission now uses a version-stable non-printing-code-point policy.
   - Hardened fail-closed handling for missing/`nil` properties, exact Luau integer precision, runtime/plan/fixture place provenance, unknown stub APIs, untrusted binaries, timeouts, and output limits.
   - Added a complete runtime-enabled CI workflow, v108 documentation, persistent validation guidance, 21 installer/runtime tests, and additional identity/model regressions.
13. `fb5f71b` — published the v108 controlled-execution validation record separately from implementation.
14. `edc3854` — hardened v108 interpretation, execution evidence, and supply-chain controls:
   - Added deterministic `108.system-interpretation.1` role classification and system candidates over exact canonical v107 reports/plans, with optional strictly validated correlation-only relationship evidence.
   - Preserves observation, deterministic inference, reported correlation, source authenticity, causality, server authority, and gameplay verification as separate explicit fields; ambiguous temporal evidence is quarantined and unsupported capabilities remain declared.
   - Prevents source-evidence mutation and aliases, revalidates canonical output exactly, and covers interface, interaction-affordance, state, feedback-surface, confidence, provenance, ordering, and fail-closed role semantics.
   - Replaced display-text status inference with structured generated-Luau status/value results so legitimate StringValue content matching an error phrase remains a resolved value.
   - Made the controlled CLI print `ok == simulationPassed`, expose `simulationPassed`, preserve the complete report, and exit nonzero for any failed simulation.
   - Pinned every action in the newly introduced v108 workflow to a reviewed immutable full commit SHA.
   - Replaced too-fresh Luau `0.745` with soak-compliant immutable official `0.744`, independently matching GitHub's published archive digest and all four executable hashes.
15. `4749ea2` — integrated strict v108 permitted-environment runtime evidence:
   - Added canonical runtime check, observation, comparison, system-plan, feature-verification, unsupported-report, and manifest contracts over exact reconstructed v107 artifacts.
   - Preserved raw inspection, v104 report, and canonical v107 report compatibility while rejecting ambiguous legacy v107 plans unless they match their exact report and migrate deterministically.
   - Made runtime checks self-contained with class-qualified full-path identity, class/property, source index/digest, deterministic scalar type, expected checks, failures, and unknowns.
   - Added explicit `not_observed`, `matched`, and `drifted` outcomes; tri-state `comparisonPassed`; non-vacuous completeness; typed resolved-value drift; unsupported API failure; and safe value/status separation.
   - Kept source authenticity, runtime execution, live-game behavior, server authority, causality, and gameplay verification false in every generated and supplied-evidence path.
   - Added strict output-directory safety, optional-evidence artifact sets, canonical byte reconstruction, manifest cross-checks, CLI nonzero failure for supplied non-passing evidence, adversarial tests, README guidance, and detailed runtime-contract documentation.

16. `1c2e55b` — improved live interaction evidence and manifest diagnostics:
   - Audited the complete 273,704-byte Bubble Gum Simulator INFINITY v30 manifest: 153 interactions, 89 heuristic attributions, 10 distinct state events, 88 GUI transitions, and zero linked, corroborated, or completed outcomes.
   - Confirmed the historical v108 resolved-value type-drift attribution defect is already fixed: `value_type_drift` retains an empty `failedRuntimeChecks` list, with targeted regression coverage.
   - Made v30.1 semantic action discovery use bounded ancestry for generic controls and added pet-scoped egg/hatch interpretation without promoting unrelated quest tabs.
   - Expanded before/after state sampling to a bounded, privacy-filtered registry of other LocalPlayer numeric/boolean ValueBase objects while retaining existing leaderstats/Data coverage.
   - Added feature-consistent state and reward-GUI outcome candidates; unrelated Bubbles drift remains temporal evidence and does not raise shops/inventory readiness.
   - Made `completedCandidates` reachable only for explicitly classified observable candidates while keeping `outcomeVerified`, causality, server authority, and gameplay verification false.
   - Added explicit pre-upload, uploading, acknowledged, incomplete, failed, and configuration-error manifest lifecycle diagnostics; ACK state still never claims receiver integrity or downstream availability.
   - Added deterministic `109.manifest-readiness.1` analysis, a sanitized eight-event real-world fixture retaining complete aggregate counts, and fail-closed transport/accounting tests.

17. `9a4591e` — integrated manifest-only readiness with the release entry point:
   - `tools/build_release.py` now accepts either a complete multipart directory or a local manifest file without changing valid multipart release behavior.
   - Manifest-file mode writes only deterministic `manifest-readiness-v109.json`, returns blocked CLI status 2, and creates no ZIP or generated Luau artifact.
   - Reused the v109 bounded-size and symlink-safe loader and deterministic writer instead of duplicating validation logic.
   - Added direct API, subprocess exit/artifact, no-release-output, symlink rejection, and unchanged multipart reproducibility coverage.
   - Exercised the full supplied manifest through the integrated command: 15 correlation candidates, generation false, gameplay verification false, and exactly one readiness artifact.

18. `c721d40` — preserved v30.1 observable candidates through workflow compilation:
   - Validates the exact feature-consistent state/GUI evidence and observable-candidate shapes, feature identity, evidence kinds, non-empty references, and explicit false authenticity/causality/authority/gameplay claims.
   - Rejects malformed, mismatched, or positively verified candidate evidence, including hidden positive verification aliases.
   - Carries distinct observable-candidate, state-correlation, and GUI-correlation counts through capability plans, workflow specs, release summaries, and implementation review output.
   - Ranks candidates above generic temporal transitions while labelling them `observable-outcome-candidate-unverified`; executable contracts, automatic execution, causality, authority, and gameplay verification remain false.
   - Added complete multipart-to-release regression coverage proving candidates reach artifacts without creating gameplay automation.

## Tests and Results

Resumed clean validation from commit `d48c6ab`:

- `npm ci --ignore-scripts`: **passed**, 7 packages audited, 0 vulnerabilities.
- `python -B -m unittest discover -s tests -v`: **1,167 passed** in 0.624s.
- `npm test`:
  - Cloudflare receiver duplicate/conflict/count/integrity checks: **passed**.
  - Luau parser tests: **3 passed** (malformed rejection, checked-in sources, generated artifacts).
- `git diff --check`: **passed**.
- Development branch push and local/remote full-SHA comparison: **passed**.

v107 schema cycle from commit `ccd4dda`:

- Focused path identity/migration suite: **15 passed**.
- Complete Python suite: **1,182 passed** in 0.623s.
- Receiver and Luau parser Node suite: **passed**, 3 parser tests passed.
- Deterministic reverse-input probe and accounting invariant: **passed**.
- `git diff --check` and local/remote commit comparison: **passed**.

v107 integration cycle from commit `7b3a486`:

- Focused schema and integration suite: **30 passed**.
- Complete Python suite: **1,197 passed** in 0.643s.
- Receiver and Luau parser Node suite: **passed**, including representative generated v107 Luau.
- Deterministic artifact-order, migration, tamper, malformed-identity, and ambiguity checks: **passed**.
- `git diff --check` and local/remote commit comparison: **passed**.

v107 semantic artifact cycle from commit `540f5dc`:

- Focused semantic and integration suite: **25 passed**.
- Complete Python suite: **1,207 passed** in 0.645s.
- Receiver and Luau parser Node suite: **passed**, including generated v107 Luau.
- Property, ordinal, duplicate-entry, hidden-line, place-guard, manifest, hash, and extra-file tamper checks: **passed**.
- `git diff --check` and local/remote commit comparison: **passed**.

v107 resolver model cycle from commit `a6a931b`:

- Focused v107 schema, integration, semantics, and model suite: **50 passed**.
- Complete Python suite: **1,217 passed** in 0.655s.
- Receiver and Luau parser Node suite: **passed**, including generated v107 Luau.
- Ordinal selection, class mismatch, missing ordinal/property, legacy ambiguity, place mismatch, root duplication, and determinism checks: **passed**.
- `git diff --check` and local/remote commit comparison: **passed**.

v107 evidence-contract cycle from commit `3810947`:

- Focused provenance, identity, integration, semantics, and model suite: **60 passed**.
- Complete Python suite: **1,227 passed** in 0.657s.
- Receiver and Luau parser Node suite: **passed**, including representative generated v107 Luau.
- Source-digest, observed/inferred distinction, outcomes, unknowns, v1 compatibility/migration, diagnostics, and tamper checks: **passed**.
- `git diff --check` and local/remote implementation commit comparison: **passed**.

v107 public API compatibility cycle from commit `9b3bfbd`:

- Official API snapshot extraction and byte-for-byte regeneration: **passed**, 41 members.
- Focused provenance, API, identity, integration, semantics, and model suite: **70 passed**.
- Complete Python suite: **1,237 passed** in 0.868s.
- Receiver and Luau parser Node suite: **passed**, including representative generated v107 Luau.
- Missing/inaccessible members, inherited owners, malformed source hash, unaccounted source member, artifact tamper, and deterministic-order checks: **passed**.
- `git diff --check` and local/remote implementation commit comparison: **passed**.

v108 controlled Luau execution cycle from commit `45fb3a6`:

- Official Luau `0.745` installer end-to-end download and archive verification: **passed**.
  - Archive SHA-256: `186e5ddaa2b048ebc7390c11ed1b00c04e7d3beaffed429250329e3575d2ece2`.
  - `luau`, `luau-analyze`, `luau-ast`, and `luau-compile` each matched their pinned executable SHA-256.
- Focused controlled execution, installer, model, identity, semantic, and integration suite: **78 passed**.
- Complete runtime-enabled Python suite: **1,265 passed** in 1.146s.
- Receiver and Luau parser Node suite: **passed**, including 3 parser tests and representative generated v107 Luau.
- Controlled CLI smoke test: **passed** with `simulationPassed: true`, model agreement, value `42`, and all live/Roblox/gameplay claims false.
- Independent read-only review: completed; integer precision overflow, Python-version-dependent Unicode admission, and empty-plan fixture-place provenance findings were reproduced and fixed.
- Python compilation, workflow YAML structure, deterministic reports, timeout/output/runtime-digest boundaries, Unicode actual-Luau execution, and `git diff --check`: **passed**.
- Implementation push and exact local/remote full-SHA comparison at `45fb3a62346bbefd710dd15e85bb5747b9c71e0e`: **passed**.

v108 interpretation and committed-history audit remediation cycle from commit `edc3854`:

- Official immutable Luau `0.744` release age, tag target, GitHub asset digest, fresh archive download, exact four-member archive, and per-executable hashes: **verified**.
  - Archive SHA-256: `6506f0852c623aaffcb28494aac16c26dc04a269ea0e16cc0aafc8c8ac79f3ec`.
  - Runtime SHA-256: `fdb514ab8341829b7ca7b734fd8c5abea5efba47886632ce35e2c5400b3211ce`.
- Structured error-like StringValue regressions and truthful failed-simulation CLI exit regression: **passed against actual Luau**.
- Controlled CLI smoke: successful simulation exited `0`; failed simulation exited `1`; both summaries matched `simulationPassed` exactly.
- Complete controlled-Luau suite: **24 passed** against `/tmp/lycoles-luau-0.744/luau`.
- Focused v107/v108 compatibility suite after static-contract correction: **107 passed**.
- Complete runtime-enabled Python suite: **1,284 passed** in 1.755s; independent re-review repeated all **1,284 passed**.
- Receiver and Luau parser Node suite: **passed**, including all 3 parser tests and representative generated Luau.
- Python compilation, deterministic system interpretation, source immutability/alias rejection, class-qualified identity, `nil`, Unicode, legacy ambiguity, model agreement, output/time/runtime-digest limits, tracked/untracked whitespace, and `git diff --check`: **passed**.
- Historical audit covered exactly `9b3bfbd..fb5f71b`; its four findings were reproduced and remediated. Fresh interpretation review found no material issues; fresh combined re-review found no remaining implementation or evidence-boundary issue.
- The combined reviewer additionally recommended pinning 98 legacy workflow references. That repository-wide suggestion was not part of the audited range: those workflows predate `9b3bfbd`; only `v108-controlled-luau.yml` changed in-range, and all three of its actions are immutable full-SHA pins.
- Implementation push and exact local/tracking/remote comparison at `edc3854b22fcf7ef93eb9a02150bb066838047a6`: **passed**.

v108 runtime-evidence integration cycle from commit `4749ea2`:

- Focused runtime-contract and integrated-pipeline suite: **22 passed** after final type, completeness, and review corrections.
- Complete runtime-enabled Python suite: **1,306 passed** against official Luau `0.744` at `/tmp/lycoles-luau-0.744/luau`.
- Receiver duplicate/conflict/count/integrity checks and all **3** Node/Luau parser tests: **passed**.
- Independent architecture review confirmed the derived-v108 layering and motivated self-contained identity/provenance/type checks; its larger optional observer proposal was not required for the caller-supplied evidence contract.
- Independent final review reproduced one material diagnostic issue: resolved value-type drift incorrectly attributed a failed property read. The result now retains `value_type_drift` with no false failed-read check, and regression coverage passes.
- Adversarial missing/partial/drifted/unsupported/type-mismatched/empty-plan evidence, manifest/check-plan tampering, v104/v107 compatibility, CLI failure, symlink/nonempty output, deterministic bytes, and claim-boundary checks: **passed**.
- Tracked and untracked whitespace checks, `git diff --check`, cache cleanup, branch verification, and exact local commit verification: **passed**.
- Implementation committed locally at `4749ea2924c5d7a12c6b6f7adc9f4c94b3cac64d`; no push, merge, pull request, or `main` change was performed.

v30.1 live-evidence and v109 manifest-readiness cycle from commit `1c2e55b`:

- Pre-change baseline: **1,306 Python tests passed**, receiver checks passed, all **3** parser tests passed, and the historical v108 type-drift attribution regression was present and green.
- Focused v30.1/v109 suite: **17 passed**, covering explicit transport states, impossible ACK counts, real-manifest readiness, deterministic output, bounded semantic actions, state scope, and candidate verification boundaries.
- Complete runtime-enabled Python suite against official Luau `0.744`: **1,317 passed** in 1.705s.
- Receiver duplicate/conflict/count/integrity checks and all **3** Node/Luau parser tests: **passed**.
- v109 CLI over the complete supplied manifest: scan/accounting valid; legacy upload attempt remains unknown; **15** feature-consistent outcome candidates found as a lower bound across pets and rewards; script generation remains blocked; every runtime/live/authority/causality/gameplay claim remains false.
- Python compilation, deterministic emit, version consistency, sanitized-fixture privacy checks, and `git diff --check`: **passed**.
- No Roblox runtime claim is made for v30.1; the updated inspector behavior has static/parser/offline regression coverage only.

Manifest-to-builder integration cycle from commit `9a4591e`:

- Regression-first direct and subprocess tests reproduced the prior unrelated `No JSON scan parts found` error before implementation.
- Focused builder/readiness suite: **13 passed**, including complete multipart reproducibility, manifest artifact/exit semantics, no ZIP/Luau output, strict accounting, deterministic output, and symlink rejection.
- Complete runtime-enabled Python suite against official Luau `0.744`: **1,320 passed** in 1.740s.
- Receiver checks and all **3** Node/Luau parser tests: **passed**.
- Integrated CLI over the complete supplied manifest: intentional exit 2; exactly `manifest-readiness-v109.json`; 15 correlation candidates; generation false; gameplay verification false.
- Python compilation and `git diff --check`: **passed**.

Correlation-aware workflow compilation cycle from commit `c721d40`:

- Four regression-first tests reproduced missing candidate counters/ranking and absent fail-closed validation before implementation.
- Focused scan/workflow/release integration suite: **18 passed**.
- Complete runtime-enabled Python suite against official Luau `0.744`: **1,325 passed** in 1.762s.
- Receiver checks and all **3** Node/Luau parser tests: **passed**.
- Python compilation and `git diff --check`: **passed**.
- The prior pushed builder-cycle head `fc51c4a` completed all **18** GitHub workflows successfully.

Earlier cycle gates also passed: 35 focused regression tests and complete 1,163-test Python suites before the v106/v107 tests were added.

## Failures and Regressions

- Remaining automated failures: **none**.
- Newly introduced regressions: **none detected**.
- The three inherited failures were stale expectations confirmed against implementation history; production safety behavior was not relaxed.

## Problems Encountered and Resolutions

- Git smart-HTTP bearer authentication prompted interactively; token-backed `x-access-token` access was verified non-interactively.
- The initial PAT lacked GitHub `workflow` scope and could not push the committed CI workflow. A securely supplied workflow-scoped token pushed only `openhands-development`, and the remote SHA was verified.
- Initial shell status handling reset the terminal; subsequent test commands used non-terminating status capture.
- Native tree-sitter installation failed under Node 24 while building a transitive native grammar. Switched to the Luau grammar's bundled WASM through `web-tree-sitter` and disabled lifecycle scripts.
- Parser construction initially preceded asynchronous runtime initialization; the validator now awaits `Parser.init()` first.
- Historical documentation contradicted later fail-closed behavior; affected implementations and downstream analyzers were inspected before documentation was corrected.
- The first strict-validator insertion temporarily split the existing `build()` invariant; immediate source inspection caught it before tests, and the invariant/return were restored.
- Focused review found legacy intermediate `FindFirstChild` traversal could silently choose among duplicate names. v107 now requires exactly one matching child at every legacy segment and returns no object on ambiguity.
- Regression-first artifact tests showed that extra manifest fields and unexpected files were previously ignored. Verification now requires exact fields, hashes, canonical bytes, and directory membership.
- Semantic parser review found that scanning only canonical entry prefixes could overlook a differently indented line inside the feature table. Parsing now isolates the exact table block and rejects every noncanonical line.
- Initial model tests exposed that `ROOTS` is a set while canonical classes live in `ROOT_CLASSES`; fixture validation now uses the canonical mapping and all 10 model tests pass.
- Official Luau rejects JSON-style Unicode escapes. Generated strings now use canonical three-digit decimal UTF-8 byte escapes, and the independent semantic verifier decodes only that strict grammar with strict UTF-8 validation.
- Executing an untrusted or drifting runtime would weaken evidence. The installer and harness now accept only the soak-compliant pinned official Luau `0.744` archive and executable digests; arbitrary local binaries are rejected.
- Capturing unbounded subprocess pipes could exhaust memory before timeout handling. Runtime output is redirected to bounded temporary files under file-size limits and rejected at the deterministic capture cap.
- Independent review reproduced oversized-integer conversion failure, Python-Unicode-database-dependent identity admission, and empty-plan fixture-place false success. Exact-integer bounds, an explicit non-printing code-point policy, and three-way place identity checks resolved them.
- Historical audit found that the original controlled CLI reported process success when `simulationPassed` was false. The complete report is still written, but JSON `ok` now equals `simulationPassed` and failed simulation exits nonzero.
- Historical audit found that display text doubled as status transport, misclassifying legitimate strings such as `missing object or identity mismatch`. Generated Luau now preserves explicit status/value pairs end to end, with actual-Luau regressions for every prior sentinel phrase.
- Historical audit found mutable action tags in the newly added v108 workflow. Its checkout, Python, and Node actions are now pinned to reviewed established 40-character commit SHAs, and a regression enforces full-SHA references in that workflow.
- Historical audit found Luau `0.745` was adopted inside the required seven-day soak window. The active runtime pin is official immutable `0.744`, published more than seven days before adoption; GitHub's asset digest, a fresh download, and all executable hashes agree.
- The permanent requirements included anti-cheat bypass/security circumvention language that conflicts with permitted-interface inspection and project safety; it was not adopted, and `AGENTS.md` explicitly prohibits bypasses, exploit loaders, stealth, access-control evasion, and unauthorized remote invocation.
- Adding evidence metadata directly to the existing schema would break strict consumers. The plan is versioned as `107.feature-plan.2`; v1 remains strictly accepted and can migrate only by exact comparison with its validated source report.
- A test insertion briefly split the provenance tamper test body. Immediate source inspection restored separate tamper and diagnostics tests before the full suite ran.
- The official API dump is over 4 MB and changes independently. Only the required 41-member subset is committed; source version, URL, byte count, and full-dump hash retain reproducibility without vendoring unrelated definitions.
- Roblox API dumps describe class members but not all globals/data-type helpers. The compatibility artifact explicitly separates `Instance.new`, `RBXScriptSignal.Connect`, `UDim`, `UDim2`, `game`, `task`, and `workspace` as assumptions rather than overstating dump coverage.
- An initial source-accounting insertion split the compatibility assessment loop. Immediate file inspection replaced the affected block before validation; 70 focused and 1,237 complete tests then passed.
- Architecture review exposed that feature IDs and digests alone made runtime checks inconvenient to execute independently. Each check now embeds exact full-path identity, class/property, source provenance, and deterministic expected scalar type, with source-digest binding and tamper tests.
- A supplied complete observation over a zero-feature plan initially passed vacuously. Comparison completeness now requires at least one expected feature and emits `empty_runtime_check_plan` as a global fail-closed diagnostic.
- Final independent review found resolved value-type drift incorrectly listed `property_read_succeeds` as failed. Type drift remains a comparison failure, but no longer contradicts the explicit resolved read status; a targeted regression locks the attribution.
- The live report's 153 interactions produced zero completed candidates because `completedCandidates` had no increment path, generic control names lacked semantic ancestry, and feature readiness counted any temporal state drift. v30.1 adds bounded semantics and feature-consistent candidates while keeping causality and verification false.
- The live report primarily exposed `Data.Bubbles` changes around shops, inventory, quest, and hatch interfaces. v30.1 records such drift temporally but no longer promotes unrelated feature readiness; state monitoring also expands to bounded non-private LocalPlayer ValueBase objects.
- `uploadedParts: 0` was generated before `transmit()` and therefore could not diagnose receiver behavior. v30.1 refreshes explicit lifecycle metadata around attempts and acknowledgements; v109 treats legacy zero as unknown rather than failure.
- The supplied artifact contains the complete local manifest and interaction history but no numbered multipart object payloads. The sanitized fixture preserves aggregate evidence plus eight representative sequences, and the analyzer blocks downstream script generation instead of inventing missing objects.

## Remaining Technical Limitations

- Tree-sitter verifies syntax, not Roblox API types or runtime semantics.
- The Luau grammar currently emits an npm deprecation warning for an unused transitive native Lua grammar; lifecycle scripts are disabled and `npm audit` reports no vulnerability.
- Rich v107 resolution depends on class-qualified sibling ordering remaining stable after observation. Migrated legacy paths cannot recover missing class/ordinal evidence and therefore fail closed whenever a name match is ambiguous.
- The Python resolver model remains synthetic and independent. v108 now executes emitted Luau in the official CLI, but only against strict local Roblox stubs; this does not validate Roblox engine behavior.
- Feature source digests prove deterministic linkage to a validated report object, not that the observation is current, causal, server-authoritative, or available at runtime.
- v108 system interpretation classifies observable roles and deterministic candidate groupings only. Optional relationship evidence remains caller-supplied correlation with unverified source authenticity; it cannot establish temporal direction, causality, server authority, action semantics, or gameplay success.
- API compatibility is pinned to one public Studio dump version; it does not establish compatibility with later releases until the source hash is reviewed and the bounded snapshot is deliberately regenerated.
- Class-member checks do not define Roblox globals or data-type helpers, and capitalized member-token accounting intentionally supports only the canonical v107 emitter format.
- The repository defines strict caller-supplied permitted-environment observations but has no authenticated Roblox-engine or target-environment result. Even a fully matched supplied observation establishes only client-observable correspondence, never source authenticity, server authority, causality, action semantics, or gameplay success.
- The harness instruments only the canonical place-guard line and suppresses scheduled loop execution after counting it; generated and instrumented source hashes remain separate.
- The pinned Ubuntu runtime installation requires access to the official GitHub release; offline runs can reuse only an already verified executable with the exact digest.
- The semantic verifier intentionally parses the canonical v107 emitter format rather than arbitrary equivalent Luau; noncanonical source is rejected even if it might execute equivalently.
- The v30.1 inspector changes have offline/static/parser validation only; no updated Roblox session has confirmed their runtime layout, event sequencing, sampling overhead, or transport snapshots.
- Feature-consistent outcome candidates remain temporal correlations gathered during overlapping interaction windows. They are useful generation inputs but do not establish causal action success, server authority, or replayability.
- Expanded state sampling is bounded to LocalPlayer numeric/boolean ValueBase objects. It does not observe arbitrary module state, server-only values, table values, protected payloads, or authoritative results.
- The legacy Bubble Gum manifest cannot establish whether upload was attempted or whether any of 1,330 parts reached the receiver. No receiver endpoint, credentials, integrity response, or production deployment was tested.
- Manifest-only v109 analysis cannot feed v107/v108 generation because canonical object-bearing parts and reviewed implementation contracts are absent.
- The Cloudflare receiver still requires separate deployment plus secret/KV configuration.
- The README retains a long historical chronology below its corrected current overview.

## Next Highest-Priority Tasks

1. Add synthetic v30.1 multipart fixtures covering pre-upload, retry, ACK, incomplete, and failure snapshots, then verify compatibility through the existing receiver integrity and release-builder paths.
2. When complete real numbered parts become available, run them through receiver integrity plus v107/v108 generation; do not request another live test solely to replace the missing historical payload.
3. Keep complete Python, actual-Luau, receiver, parser, integrity, determinism, immutable-action, and dependency-provenance gates green after each cycle.
