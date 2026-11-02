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

Current v109 manifest contract: `tools/manifest_readiness_v109.py` analyzes a local manifest without treating it as the numbered multipart report. Legacy `uploadedParts: 0` is an unknown pre-upload snapshot, not transport failure. New manifests expose the generated multipart `scanId`, and local-manifest identity/counts must match numbered parts. Explicit ACK state still does not establish receiver integrity or downstream availability. A separately validated direct Worker `/integrity` response may establish receiver-stored report availability, but not local payload equivalence without matching hashes. Manifest-only input must keep v107/v108 script generation blocked because canonical object parts and reviewed contracts are absent. `tools/fetch_receiver_scan.py` is the network boundary: keep read keys environment-only, require HTTPS, reject redirects, use constant-cost receiver metadata rather than the O(part-count) Worker integrity route, validate every part before atomic publication, and leave `tools/build_release.py` offline.

Current v30.2 transport contract: the Worker hashes exact accepted request bodies, persists per-part SHA-256 sidecars, and returns them in ACKs and numbered-part headers. The inspector requires and records digest-bearing ACKs. The importer must fail closed on missing/mismatched persisted digests and may compare a supplied local ACK manifest. Optional resume state must stay outside output, contain no read key, bind to receiver origin plus canonical metadata, retain only digest-verified parts through atomic checkpoint updates, revalidate every cached part before final atomic publication, and remain explicitly unauthenticated. `receiverStoredPayloadDigestsVerified`, `receiverAcknowledgementDigestEquivalent`, and resume checks do not authenticate either party or establish locally computed original-byte equivalence. Production Worker deployment remains separately authorized.

Current release provenance contract: `tools/compile_scan.py` must distinguish ordinary local manifests from `30.2.receiver-import.2`, require its exact schema, reconcile every identity/accounting field, and recompute each current raw part digest before emitting normalized `30.2.source-provenance.1`. Direct multipart input must report receiver checks unavailable. `source-provenance.json`, release manifests, documentation, and generated UI may surface retrieval integrity, ACK equivalence, and resume reuse only while checkpoint authentication, receiver-response/source authenticity, original local payload equivalence, causality, authority, replayability, gameplay, and action outcomes remain false or unverified.

Current v30.3 capability-request contract: the in-game Generated Script tab stages one bounded client-visible request and triggers a complete evidence scan. The request may be carried through metadata-bearing parts, lifecycle manifests, capability plans, release manifests, and generated read-only Luau only as user intent and evidence-review context. `PRODUCE SCRIPT` does not imply in-game generation, runtime installation, action support, causality, replayability, authority, or gameplay success; those remain offline-validated or unverified as explicitly reported.

Current dynamic-overlay provenance contract: each complete observation scan must carry compiler-normalized source provenance whose scan/place/part identity matches that overlay and whose unsupported trust claims remain false. `source-provenance.json` describes only the baseline; overlay records stay separate in `capability-plan.json` and `evidence-overlay-provenance.json`, with a digest-linked release-manifest summary. Mixed source modes never imply source authenticity, causality, server authority, replayability, gameplay verification, or action-outcome verification.

## Generated features

Each generated feature must define:

- Evidence source and stable provenance.
- Evidence classification and unknown boundaries.
- Implementation strategy.
- Runtime checks.
- Success conditions.
- Failure conditions.
- Accurate verification status.

Generate complete functional read-only/client-local behavior when evidence supports it. Fail closed instead of fabricating game-specific functionality when evidence is insufficient.

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
- Controlled Luau success is simulated, read-only evidence only; it never upgrades Roblox runtime, live-game, server-authority, causality, or gameplay verification claims.
