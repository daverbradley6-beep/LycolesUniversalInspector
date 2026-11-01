"""Deterministic evidence-bounded gameplay-system interpretation for v108."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from feature_planner_v107 import plan
from release_pipeline_v104 import canonical

SCHEMA_VERSION = "108.system-interpretation.1"
RELATIONSHIP_SCHEMA_VERSION = "108.relationship-evidence.1"
MAX_RELATIONSHIPS = 500
MAX_OBSERVATIONS = 1_000_000
MAX_CAPTURES = 10_000
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,98}\.json$")
RELATIONSHIP_KINDS = frozenset({
    "co_visible",
    "interaction_followed_by_state_change",
    "state_and_feedback_changed_together",
})
EVIDENCE_FIELDS = {
    "schemaVersion", "placeId", "sourceFeaturePlanSha256", "relationships",
    "runtimeVerified", "causalityProven", "gameplayVerified",
}
RELATIONSHIP_FIELDS = {
    "kind", "sourceFeatureId", "targetFeatureId", "observations",
    "independentCaptures", "attributionStatus", "overlappingCandidates",
    "evidenceArtifact", "evidenceDigest",
}
ROLE_MAP = {
    "TextButton": ["interface", "interaction_affordance"],
    "ImageButton": ["interface", "interaction_affordance"],
    "TextLabel": ["feedback_surface_candidate", "interface"],
    "TextBox": ["feedback_surface_candidate", "interface"],
    "ScreenGui": ["feedback_surface_candidate", "interface"],
    "IntValue": ["observable_state"],
    "NumberValue": ["observable_state"],
    "BoolValue": ["observable_state"],
    "StringValue": ["observable_state"],
    "ProximityPrompt": ["interaction_affordance"],
    "ClickDetector": ["interaction_affordance"],
    "Tool": ["interaction_affordance"],
}
BASE_UNKNOWNS = [
    "server_authority",
    "gameplay_causality",
    "game_specific_action_semantics",
    "live_runtime_outcome",
]
UNSUPPORTED_CAPABILITIES = [
    "automatic_gameplay_action",
    "remote_invocation",
    "server_authority_claim",
]


def _sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _roles(feature):
    roles = ROLE_MAP.get(feature["className"])
    if roles is None:
        raise ValueError("unsupported feature class")
    return list(roles)


def _relationship_key(relationship):
    return (
        relationship["kind"],
        relationship["sourceFeatureId"],
        relationship["targetFeatureId"],
        relationship["evidenceArtifact"],
        relationship["evidenceDigest"],
    )


def _validate_relationship_role(relationship, feature_roles):
    source = set(feature_roles[relationship["sourceFeatureId"]])
    target = set(feature_roles[relationship["targetFeatureId"]])
    kind = relationship["kind"]
    valid = (
        kind == "interaction_followed_by_state_change"
        and "interaction_affordance" in source
        and "observable_state" in target
    ) or (
        kind == "state_and_feedback_changed_together"
        and "observable_state" in source
        and "feedback_surface_candidate" in target
    ) or (
        kind == "co_visible"
        and bool(source & {"interface", "interaction_affordance"})
        and bool(target & {"interface", "interaction_affordance"})
    )
    if not valid:
        raise ValueError("invalid relationship role semantics")


def _validate_relationship_evidence(evidence, feature_plan, feature_roles):
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_FIELDS:
        raise ValueError("invalid relationship evidence fields")
    if evidence.get("schemaVersion") != RELATIONSHIP_SCHEMA_VERSION:
        raise ValueError("invalid relationship evidence schema")
    if type(evidence.get("placeId")) is not int or evidence["placeId"] <= 0:
        raise ValueError("invalid relationship evidence place")
    if evidence["placeId"] != feature_plan["placeId"]:
        raise ValueError("relationship evidence place mismatch")
    if evidence.get("sourceFeaturePlanSha256") != _sha256(feature_plan):
        raise ValueError("feature plan digest mismatch")
    if any(evidence.get(field) is not False for field in (
        "runtimeVerified", "causalityProven", "gameplayVerified",
    )):
        raise ValueError("invalid relationship verification claim")
    relationships = evidence.get("relationships")
    if not isinstance(relationships, list) or len(relationships) > MAX_RELATIONSHIPS:
        raise ValueError("invalid relationships")
    feature_ids = set(feature_roles)
    artifact_digests = {}
    seen = set()
    for relationship in relationships:
        if not isinstance(relationship, dict) or set(relationship) != RELATIONSHIP_FIELDS:
            raise ValueError("invalid relationship fields")
        kind = relationship.get("kind")
        if not isinstance(kind, str) or kind not in RELATIONSHIP_KINDS:
            raise ValueError("unsupported relationship kind")
        source = relationship.get("sourceFeatureId")
        target = relationship.get("targetFeatureId")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("invalid relationship feature")
        if source not in feature_ids or target not in feature_ids:
            raise ValueError("unknown relationship feature")
        if source == target:
            raise ValueError("self relationship")
        observations = relationship.get("observations")
        captures = relationship.get("independentCaptures")
        if type(observations) is not int or not 1 <= observations <= MAX_OBSERVATIONS:
            raise ValueError("invalid relationship observations")
        if type(captures) is not int or not 1 <= captures <= min(observations, MAX_CAPTURES):
            raise ValueError("invalid relationship captures")
        attribution = relationship.get("attributionStatus")
        overlaps = relationship.get("overlappingCandidates")
        if type(overlaps) is not int or not 0 <= overlaps <= MAX_RELATIONSHIPS:
            raise ValueError("invalid overlapping candidates")
        if kind == "co_visible":
            if attribution != "not_temporal" or overlaps != 0:
                raise ValueError("invalid co-visible attribution")
            if source >= target:
                raise ValueError("noncanonical co-visible direction")
        elif attribution != "unambiguous" or overlaps != 0:
            raise ValueError("ambiguous relationship quarantined")
        artifact = relationship.get("evidenceArtifact")
        digest = relationship.get("evidenceDigest")
        if not isinstance(artifact, str) or ARTIFACT.fullmatch(artifact) is None:
            raise ValueError("invalid relationship artifact")
        if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
            raise ValueError("invalid relationship digest")
        previous_digest = artifact_digests.setdefault(artifact, digest)
        if previous_digest != digest:
            raise ValueError("artifact digest conflict")
        identity = (kind, source, target)
        if identity in seen:
            raise ValueError("duplicate relationship")
        seen.add(identity)
        _validate_relationship_role(relationship, feature_roles)
    if relationships != sorted(relationships, key=_relationship_key):
        raise ValueError("noncanonical relationship order")
    return relationships


def _feature_view(feature, roles):
    return {
        "id": feature["id"],
        "label": feature["label"],
        "className": feature["className"],
        "property": feature["property"],
        "path": feature["path"],
        "pathIdentity": feature["pathIdentity"],
        "roles": roles,
        "rolesClassification": "deterministic_inference",
        "sourceEvidenceClassification": feature["evidence"]["classification"],
        "sourceDigest": feature["evidence"]["sourceDigest"],
    }


def _components(feature_ids, relationships):
    parent = {identifier: identifier for identifier in feature_ids}

    def find(identifier):
        while parent[identifier] != identifier:
            parent[identifier] = parent[parent[identifier]]
            identifier = parent[identifier]
        return identifier

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            first, second = sorted((left_root, right_root))
            parent[second] = first

    for relationship in relationships:
        union(relationship["sourceFeatureId"], relationship["targetFeatureId"])
    grouped = {}
    for identifier in feature_ids:
        grouped.setdefault(find(identifier), []).append(identifier)
    return sorted((sorted(values) for values in grouped.values()), key=lambda values: values[0])


def _system_type(roles, relationships):
    kinds = {relationship["kind"] for relationship in relationships}
    if "interaction_followed_by_state_change" in kinds:
        if "feedback_surface_candidate" in roles:
            return "interaction_feedback_candidate"
        return "interaction_state_candidate"
    if "state_and_feedback_changed_together" in kinds:
        return "state_feedback_candidate"
    if "co_visible" in kinds:
        return "interface_cluster_candidate"
    if "interaction_affordance" in roles:
        return "interaction_affordance_observation"
    if "feedback_surface_candidate" in roles:
        return "feedback_surface_observation"
    if "observable_state" in roles:
        return "state_observation"
    return "interface_observation"


def _confidence(relationships):
    if not relationships:
        return {
            "level": "structural_only",
            "basis": ["client_visible_feature_structure"],
            "relationshipCount": 0,
            "minimumObservations": 0,
            "minimumIndependentCaptures": 0,
        }
    observations = min(item["observations"] for item in relationships)
    captures = min(item["independentCaptures"] for item in relationships)
    repeated = observations >= 3 and captures >= 2
    basis = ["client_visible_feature_structure", "supplied_relationship_evidence"]
    if repeated:
        basis.append("reported_repeated_independent_captures")
    return {
        "level": "reported_repeated_correlation" if repeated else "reported_correlation",
        "basis": basis,
        "relationshipCount": len(relationships),
        "minimumObservations": observations,
        "minimumIndependentCaptures": captures,
    }


def _unknowns(roles, relationships, confidence):
    values = list(BASE_UNKNOWNS)
    if relationships:
        values.extend((
            "relationship_evidence_authenticity",
            "relationship_persistence",
        ))
        if confidence["minimumIndependentCaptures"] < 2:
            values.append("insufficient_independent_captures")
    else:
        values.append("feature_relationships")
    if "interaction_affordance" in roles:
        values.append("interaction_execution_effect")
    if "observable_state" in roles:
        values.append("unobserved_state_variables")
    if "feedback_surface_candidate" in roles:
        values.append("feedback_semantics")
    return values


def interpret(report, feature_plan, relationship_evidence=None):
    """Interpret observable system candidates without causal or gameplay claims."""
    expected_plan = plan(report)
    if feature_plan != expected_plan:
        raise ValueError("feature plan mismatch")
    features = feature_plan["features"]
    feature_lookup = {feature["id"]: feature for feature in features}
    feature_roles = {
        identifier: _roles(feature)
        for identifier, feature in feature_lookup.items()
    }
    source_relationship_digest = None
    relationships = []
    if relationship_evidence is not None:
        relationships = _validate_relationship_evidence(
            relationship_evidence, feature_plan, feature_roles
        )
        source_relationship_digest = _sha256(relationship_evidence)
    rendered_relationships = [
        {
            "id": f"relationship_{index:04d}",
            **relationship,
            "classification": "caller_supplied_correlation",
            "causalityProven": False,
        }
        for index, relationship in enumerate(relationships)
    ]
    relation_by_id = {
        relationship["id"]: relationship for relationship in rendered_relationships
    }
    systems = []
    for index, feature_ids in enumerate(_components(sorted(feature_lookup), relationships)):
        feature_id_set = set(feature_ids)
        system_relationships = [
            relationship for relationship in rendered_relationships
            if relationship["sourceFeatureId"] in feature_id_set
            and relationship["targetFeatureId"] in feature_id_set
        ]
        roles = sorted({role for identifier in feature_ids for role in feature_roles[identifier]})
        confidence = _confidence(system_relationships)
        systems.append({
            "id": f"system_{index:04d}",
            "label": f"Inferred observable system candidate {index + 1}",
            "interpretationClassification": "deterministic_inference",
            "type": _system_type(roles, system_relationships),
            "featureIds": feature_ids,
            "features": [
                _feature_view(feature_lookup[identifier], feature_roles[identifier])
                for identifier in feature_ids
            ],
            "relationshipIds": [
                relationship["id"] for relationship in system_relationships
            ],
            "relationshipKinds": sorted({
                relationship["kind"] for relationship in system_relationships
            }),
            "confidence": confidence,
            "unknowns": _unknowns(roles, system_relationships, confidence),
            "unsupportedCapabilities": list(UNSUPPORTED_CAPABILITIES),
            "systemVerified": False,
            "causalityProven": False,
            "gameplayVerified": False,
        })
    confidence_counts = Counter(
        system["confidence"]["level"] for system in systems
    )
    type_counts = Counter(system["type"] for system in systems)
    role_counts = Counter(
        role for system in systems for feature in system["features"]
        for role in feature["roles"]
    )
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "placeId": feature_plan["placeId"],
        "sourceReportSha256": _sha256(report),
        "sourceFeaturePlanSha256": _sha256(feature_plan),
        "sourceRelationshipEvidenceSha256": source_relationship_digest,
        "systems": systems,
        "relationships": [relation_by_id[item["id"]] for item in rendered_relationships],
        "summary": {
            "featureCount": len(features),
            "systemCount": len(systems),
            "relationshipCount": len(rendered_relationships),
            "standaloneSystems": sum(not system["relationshipIds"] for system in systems),
            "correlatedSystems": sum(bool(system["relationshipIds"]) for system in systems),
            "featureRoles": dict(sorted(role_counts.items())),
            "systemTypes": dict(sorted(type_counts.items())),
            "confidenceLevels": dict(sorted(confidence_counts.items())),
        },
        "readOnly": True,
        "runtimeVerified": False,
        "liveGameVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }
    return result


def validate_interpretation(value, report, feature_plan, relationship_evidence=None):
    """Require byte-semantic equivalence with deterministic reconstruction."""
    if value != interpret(report, feature_plan, relationship_evidence):
        raise ValueError("interpretation mismatch")
    return value


def _load_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 20_000_000:
        raise ValueError("invalid interpreter input")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("interpreter input must be an object")
    return value


def _reject_output_alias(output, inputs):
    output = Path(output)
    resolved_output = output.resolve()
    for source in (Path(path) for path in inputs if path is not None):
        if resolved_output == source.resolve():
            raise ValueError("output aliases interpreter input")
        if output.exists() and output.samefile(source):
            raise ValueError("output aliases interpreter input")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--feature-plan", type=Path, required=True)
    parser.add_argument("--relationship-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _reject_output_alias(
        args.output, (args.report, args.feature_plan, args.relationship_evidence)
    )
    report = _load_json(args.report)
    feature_plan = _load_json(args.feature_plan)
    evidence = _load_json(args.relationship_evidence) if args.relationship_evidence else None
    result = interpret(report, feature_plan, evidence)
    if args.output.is_symlink():
        raise ValueError("symlink output forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps({
        "ok": True,
        "systems": result["summary"]["systemCount"],
        "relationships": result["summary"]["relationshipCount"],
        "readOnly": True,
        "causalityProven": False,
        "gameplayVerified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
