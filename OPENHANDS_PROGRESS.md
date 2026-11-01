# OpenHands Development Progress

_Last updated: 2026-11-01 — v107 public Roblox API compatibility cycle_

## Repository State

- Workspace: `/projects/LycolesUniversalInspector`
- Branch: `openhands-development`
- Latest implementation commit: `9b3bfbd` (`Validate v107 against public Roblox API`)
- Implementation head: local and `origin/openhands-development` matched at the identical full commit SHA
- Implementation snapshot relative to `origin/main`: **11 commits ahead, 0 behind**
- This report is published as a separate documentation commit, whose self-referential SHA is intentionally not embedded here
- Remote policy: only the development branch is pushed; no merge and no pull request performed

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
- No Luau/Roblox analyzer or runtime is installed locally. Official Luau 0.745 publishes an Ubuntu analyzer, but it does not itself provide Roblox API definitions or a Roblox runtime, so an external binary was not added merely to imply broader validation.
- The permanent requirements included anti-cheat bypass/security circumvention language that conflicts with permitted-interface inspection and project safety; it was not adopted, and `AGENTS.md` explicitly prohibits bypasses, exploit loaders, stealth, access-control evasion, and unauthorized remote invocation.
- Adding evidence metadata directly to the existing schema would break strict consumers. The plan is versioned as `107.feature-plan.2`; v1 remains strictly accepted and can migrate only by exact comparison with its validated source report.
- A test insertion briefly split the provenance tamper test body. Immediate source inspection restored separate tamper and diagnostics tests before the full suite ran.
- The official API dump is over 4 MB and changes independently. Only the required 41-member subset is committed; source version, URL, byte count, and full-dump hash retain reproducibility without vendoring unrelated definitions.
- Roblox API dumps describe class members but not all globals/data-type helpers. The compatibility artifact explicitly separates `Instance.new`, `RBXScriptSignal.Connect`, `UDim`, `UDim2`, `game`, `task`, and `workspace` as assumptions rather than overstating dump coverage.
- An initial source-accounting insertion split the compatibility assessment loop. Immediate file inspection replaced the affected block before validation; 70 focused and 1,237 complete tests then passed.

## Remaining Technical Limitations

- Tree-sitter verifies syntax, not Roblox API types or runtime semantics.
- The Luau grammar currently emits an npm deprecation warning for an unused transitive native Lua grammar; lifecycle scripts are disabled and `npm audit` reports no vulnerability.
- Rich v107 resolution depends on class-qualified sibling ordering remaining stable after observation. Migrated legacy paths cannot recover missing class/ordinal evidence and therefore fail closed whenever a name match is ambiguous.
- The controlled resolver harness evaluates a Python model over synthetic JSON; it does not execute emitted Luau or validate live Roblox object behavior.
- Feature source digests prove deterministic linkage to a validated report object, not that the observation is current, causal, server-authoritative, or available at runtime.
- API compatibility is pinned to one public Studio dump version; it does not establish compatibility with later releases until the source hash is reviewed and the bounded snapshot is deliberately regenerated.
- Class-member checks do not define Roblox globals or data-type helpers, and capitalized member-token accounting intentionally supports only the canonical v107 emitter format.
- No controlled Roblox runtime test is available; client-visible observations cannot establish server authority, causality, or gameplay success.
- The semantic verifier intentionally parses the canonical v107 emitter format rather than arbitrary equivalent Luau; noncanonical source is rejected even if it might execute equivalently.
- The Cloudflare receiver still requires separate deployment plus secret/KV configuration.
- The README retains a long historical chronology below its corrected current overview.

## Next Highest-Priority Tasks

1. Add controlled Luau execution with bounded Roblox API stubs to exercise generated resolver and property-read paths without target-game Studio access.
2. Define a strict schema for user-supplied observations and results from permitted client environments, then compare them with resolver-model outcomes without upgrading evidence to causality or gameplay verification.
3. Add a deliberate API-snapshot refresh workflow that reports reviewed upstream member/security diffs instead of silently following the latest release.
4. Replace the deprecated transitive grammar dependency when the maintained Luau package publishes a compatible update.
5. Keep complete Python, receiver, and Luau parser suites green after each future cycle.
