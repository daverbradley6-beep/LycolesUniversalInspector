# v108 runtime contracts and integrated artifacts

v108 adds deterministic planning and comparison around permitted client-observable evidence. It does not execute gameplay actions and does not convert caller-supplied observations into proof of source authenticity, Roblox-engine behavior, server authority, causality, action semantics, or gameplay success.

## Data flow

```text
v107-compatible inspection
        │
        ▼
strict v107 report, feature plan, quality, diagnostics, API contract, Luau
        │
        ├── optional 108.relationship-evidence.1
        ▼
108.system-interpretation.1
        │
        ▼
108.runtime-check-plan.1
        │
        ├── optional 108.runtime-observation.1
        ▼
108.runtime-comparison.1
        │
        ├── 108.system-plan.1
        ├── 108.feature-verification.1
        └── 108.unsupported-report.1
```

Every JSON artifact is canonical and linked to its exact source artifacts with SHA-256 digests. `108.integrated-manifest.1` hashes every included file. Verification independently regenerates the complete v107 base and every derived v108 artifact, rejects extra or missing files, rejects symlinks, and requires exact bytes and exact manifest fields.

## Runtime check plan

`108.runtime-check-plan.1` derives one expected check per v107 feature and links it to every inferred system containing that feature. Each check retains the full path, class-qualified identity, resolution mode, class, property, source object index, evidence digest, property value type, runtime checks, success condition, failures, and unknowns. The expected status is `resolved`; no expected property value is invented because the source report does not establish one.

System plans require all member features to resolve. They retain explicit unsupported capabilities and keep `runtimeVerified`, `causalityProven`, and `gameplayVerified` false.

## Permitted runtime observation

`108.runtime-observation.1` is optional caller-supplied evidence with these top-level fields:

- exact `placeId` and `sourceFeaturePlanSha256`;
- a bounded environment descriptor with `kind: permitted_client_observation`, capture ID, source artifact name, and source digest;
- canonical feature entries ordered by feature ID, each containing `featureId`, structured `status`, and scalar `value`;
- sorted unique `unsupportedApiUsages`;
- an explicit `observationComplete` boolean;
- `readOnly: true` and all verification claims false.

Accepted statuses are `resolved`, `place_mismatch`, `identity_mismatch`, `legacy_resolution_failed`, `property_unavailable`, and `unsupported_path_resolution`. Status is never inferred from display text, so legitimate string values can equal failure messages.

Complete observations must contain every planned feature exactly once. Partial observations may omit features only when `observationComplete` is false. Unknown, duplicate, noncanonical, oversized, non-finite, unsafe-integer, mismatched-place, mismatched-plan, extra-field, and claim-upgrading inputs fail closed.

## Comparison semantics

`108.runtime-comparison.1` reports each expected feature as:

- `matched`: an observation exists, its structured status is `resolved`, and its scalar type matches the supported property type;
- `drifted`: an observation has a failure status or a resolved value-type mismatch;
- `not_observed`: no observation was supplied for the feature.

Failure statuses map to explicit failed runtime checks and diagnostics such as `place_drift`, `identity_drift`, `legacy_resolution_drift`, and `property_drift`. Unsupported API usage is a global runtime-contract failure. System outcomes are derived only from member feature outcomes.

`comparisonComplete` means at least one expected feature exists and every expected feature was compared in a caller-declared complete observation. A supplied observation for a zero-feature plan fails closed with `empty_runtime_check_plan`; it cannot pass vacuously. Completeness does not mean the game, runtime source, system, or gameplay was verified. `comparisonPassed` is `null` when no observation was supplied, `true` only for a complete comparison with no feature drift or unsupported API usage, and `false` for any supplied incomplete or drifted comparison. `driftDetected` is false when evidence is absent because absence is represented separately as `not_observed`; it is not silently treated as success.

Property values are retained as observations. Resolved values are checked only against the deterministic supported-property scalar type (`typeCompared`); they are never compared against invented expected values. `valueComparisonAvailable` and every per-feature `valueCompared` field therefore remain false.

Generation with supplied evidence always writes and verifies the complete bundle. The CLI then exits nonzero when `comparisonPassed` is false, preserving failure evidence without reporting operational success. `--verify-only` checks artifact integrity and returns success for an internally consistent drift bundle because drift is evidence content, not artifact corruption.

## Integrated bundle

Generate a v108 bundle from the same inspection formats accepted by v107:

```sh
python3 tools/integrated_pipeline_v108.py \
  --source path/to/inspection.json \
  --place-id 123456 \
  --output build/v108
```

Optional evidence can be included without changing v107 source compatibility:

```sh
python3 tools/integrated_pipeline_v108.py \
  --source path/to/inspection.json \
  --place-id 123456 \
  --relationship-evidence path/to/108.relationship-evidence.json \
  --runtime-observation path/to/108.runtime-observation.json \
  --output build/v108
```

Verify without trusting generation-time state:

```sh
python3 tools/integrated_pipeline_v108.py \
  --verify-only \
  --output build/v108
```

The fixed bundle contains the six canonical v107 artifacts plus:

- `system-interpretation.json`
- `system-plan.json`
- `runtime-check-plan.json`
- `runtime-comparison.json`
- `feature-verification.json`
- `unsupported-report.json`
- `manifest.json`

`relationship-evidence.json` and `runtime-observation.json` are included only when supplied, and their presence must match exact manifest flags and hashes.

## Evidence boundaries

A fully matched comparison still retains these false claims:

- `sourceAuthenticityVerified`
- `runtimeVerified`
- `liveGameVerified`
- `serverAuthorityVerified`
- `causalityProven`
- `gameplayVerified`

The artifacts establish deterministic consistency between bounded inputs, plans, generated code, and supplied observations. They do not establish that a capture is authentic or current, that an observed change was caused by an interaction, that the server accepted anything, or that gameplay succeeded.
