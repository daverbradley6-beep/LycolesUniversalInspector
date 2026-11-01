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
