# v108 evidence-bounded system interpretation

The v108 interpreter groups canonical v107 read-only features into observable system candidates. It classifies only structure supported by validated client-visible evidence: interface elements, interaction affordances, observable state, and candidate feedback surfaces. It does not generate gameplay actions or claim that a supplied relationship is authentic or causal.

## Inputs

The interpreter requires a canonical `107.release` report and the exact deterministic `107.feature-plan.2` reconstructed from that report. A mismatched or modified plan is rejected.

Relationship evidence is optional. Without it, every feature remains a standalone structural observation. Optional evidence uses `108.relationship-evidence.1`:

```json
{
  "schemaVersion": "108.relationship-evidence.1",
  "placeId": 123456,
  "sourceFeaturePlanSha256": "<canonical feature-plan SHA-256>",
  "relationships": [
    {
      "kind": "interaction_followed_by_state_change",
      "sourceFeatureId": "observe_0000",
      "targetFeatureId": "observe_0002",
      "observations": 6,
      "independentCaptures": 2,
      "attributionStatus": "unambiguous",
      "overlappingCandidates": 0,
      "evidenceArtifact": "relationship-capture.json",
      "evidenceDigest": "<64 lowercase hexadecimal characters>"
    }
  ],
  "runtimeVerified": false,
  "causalityProven": false,
  "gameplayVerified": false
}
```

Relationships must be canonical and ordered lexically by kind, source feature, target feature, artifact, and digest. Each artifact basename must map to exactly one digest throughout the document. Artifact basenames and digests are strict provenance references, but this interpreter does not load, authenticate, or independently reconstruct those source artifacts; relationship-evidence authenticity remains explicit uncertainty. The supported kinds and role constraints are:

- `co_visible`: interface or interaction-affordance features reported together. It requires `attributionStatus: "not_temporal"`, zero overlaps, and lexically ordered feature IDs because the edge is symmetric.
- `interaction_followed_by_state_change`: interaction affordance to observable state.
- `state_and_feedback_changed_together`: observable state to candidate feedback surface.

Both temporal kinds require `attributionStatus: "unambiguous"` and `overlappingCandidates: 0`. Ambiguous or overlapping outcomes are quarantined by rejection rather than emitted as weak links. Unknown features, self-links, duplicate edges, unsupported kinds, invalid role directions, path-like artifact names, noncanonical order, and upgraded verification claims also fail closed. The current limit is 500 relationships, one million observations per relationship, and 10,000 independent captures.

## Output and confidence

`108.system-interpretation.1` contains canonical source hashes, feature roles, connected observable system candidates, relationship provenance, explicit unknowns, unsupported capabilities, and deterministic summary counts. Every feature preserves the v107 observed classification in `sourceEvidenceClassification`, while its roles use `rolesClassification: "deterministic_inference"`. Systems use `interpretationClassification: "deterministic_inference"`; relationship edges use `classification: "caller_supplied_correlation"`.

An interaction-to-state edge is an `interaction_state_candidate` unless its connected component also contains a candidate feedback surface, in which case it may be an `interaction_feedback_candidate`. This prevents state-only evidence from being relabeled as feedback.

Confidence is categorical metadata derived from validated feature structure and caller-supplied counts; it is not probability or independent authentication:

- `structural_only`: client-visible feature structure with no supplied relationship evidence.
- `reported_correlation`: supplied relationship evidence that does not meet both thresholds of three reported observations and two reported independent captures.
- `reported_repeated_correlation`: every relationship in the candidate reports at least three observations across at least two independent captures.

A reported repeated correlation still does not prove causality or authenticate its source. Every system retains unknown boundaries for server authority, gameplay causality, game-specific action semantics, and live runtime outcomes. Depending on its roles and evidence, it also retains unknown relationship-evidence authenticity, relationship persistence, interaction effects, unobserved state, or feedback semantics.

Automatic gameplay actions, remote invocation, and server-authority claims are always listed as unsupported capabilities.

## Run

```bash
python tools/system_interpreter_v108.py \
  --report build/v107/inspection-report.json \
  --feature-plan build/v107/feature-plan.json \
  --relationship-evidence path/to/108.relationship-evidence.json \
  --output build/v108/system-interpretation.json
```

Omit `--relationship-evidence` for structure-only interpretation. Inputs are limited to 20 MB and symlinks are rejected. The output may not resolve to or share an existing file identity with the report, feature plan, or relationship-evidence input. Output is canonical UTF-8 JSON.

## Verification claims

The interpreter reports `readOnly: true`. `runtimeVerified`, `liveGameVerified`, `causalityProven`, `serverAuthorityVerified`, `gameplayVerified`, and each system's verification claims are always `false`.

The output is deterministic evidence interpretation only. It is not controlled-Luau evidence, Roblox-engine evidence, live-game verification, or permission to invoke game remotes. Controlled Luau results remain separately described as read-only simulation evidence in `v108-controlled-luau.md`.
